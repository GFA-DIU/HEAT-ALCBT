import re
import uuid as uuid_lib
import logging

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from cities_light.models import Country

from pages.scripts.oekobaudat.oekobaudat_loader import parse_epd
from pages.scripts.ecoplatform.ecoplatform_loader import (
    get_all_uuids_ecoplatform,
    get_full_epd,
)

from pages.models.epd import (
    EPD,
    EPDType,
    MaterialCategory,
    EPDImpact,
    Impact,
)
from pages.models.assembly import StructuralProduct
from pages.models.building import OperationalProduct, SimulatedOperationalProduct

logger = logging.getLogger(__name__)

User = get_user_model()

# Suffix appended to a COPY created when a building-referenced ("used") EPD has
# changed in the source portal — so the original (still referenced by buildings)
# is preserved untouched while the refreshed data is available as a new record.
UPDATE_MARKER = " (Eco-platform update)"

# Product-name keyword -> MaterialCategory name_en (first match wins). Used when the
# source dataset's classification id doesn't map to an Ökobaudat category — common for
# the distributed ECO-Platform nodes. This replaces the old hardcoded default of
# "Primer for paints and plasters", which mislabelled the large majority of imports.
_NAME_CATEGORY_RULES = [
    (r"reinforc\w* bar|deformed bar|round(ed)? bar|\brebar\b|reinforc\w* mesh|wire mesh", "Steel reinforing bar"),
    (r"stainless steel|structural steel|galvalume|alu[- ]?zinc|galvani[sz]ed steel|steel (sheet|coil|plate|pipe|product|bar|section|rod)|hot[- ]?rolled|cold[- ]?rolled|\bpurlin\b|\bsteel\b", "Steel"),
    (r"alumin(i)?um|copper|\bbrass\b|\bzinc\b|\blead\b|metal", "Metals"),
    (r"insulation|glass ?wool|rock ?wool|mineral wool|\beps\b|\bxps\b|acoustic|cellulose fib", "Insulation materials"),
    (r"paint|primer|coating|enamel|varnish|lacquer|jotafloor|majestic|jotun|penguard|jotamastic|jotashield|hardtop", "Coverings"),
    (r"waterproof|membrane|bitumen|sealant|adhesive|grout", "Coverings"),
    (r"tile|floor|ceiling|gyp(sum|board|roc)|plaster ?board|\bpanel\b|\bboard\b|fascia|fa[cç]ade|laminate|wallpaper|vinyl", "Coverings"),
    (r"concrete|cement|\bmortar\b|screed|\blean\b|aggregate|clinker", "Mineral building products"),
    (r"brick|\bblock\b|masonry|\baac\b|ceramic|clay", "Mineral building products"),
    (r"\bwood\b|timber|plywood|\bmdf\b|particle ?board|\bosb\b|bamboo", "Wood"),
    (r"\bu?pvc\b|\bcpvc\b|\bppr\b|hdpe|plastic|polymer|polyethylene|polypropylene", "Plastics"),
    (r"pipe|\bvalve\b|\bduct\b|fitting|hvac|plumb", "Building service engineering"),
    (r"window|\bdoor\b|glazing|glass|curtain wall", "Components for windows and curtain walls"),
]
_NAME_CATEGORY_RULES = [(re.compile(p, re.I), name) for p, name in _NAME_CATEGORY_RULES]

_category_cache = {}


def _category_by_name(name_en):
    if name_en not in _category_cache:
        _category_cache[name_en] = (
            MaterialCategory.objects.filter(name_en=name_en).order_by("level").first()
        )
    return _category_cache.get(name_en)


def resolve_category(classification_id, name):
    """Resolve an EPD to a MaterialCategory: exact classification-id match first,
    then a product-name keyword match, else 'Unknown'. Never guesses 'Primer'."""
    if classification_id:
        cat = MaterialCategory.objects.filter(category_id=classification_id).first()
        if cat:
            return cat
    for rx, cname in _NAME_CATEGORY_RULES:
        if rx.search(name or ""):
            return _category_by_name(cname)
    return _category_by_name("Unknown")


def _used_epd_ids():
    """EPD ids referenced by any building material. These must never be modified
    or deleted (the FK cascades, which would corrupt existing user buildings)."""
    ids = set()
    for Model in (StructuralProduct, OperationalProduct, SimulatedOperationalProduct):
        ids.update(Model.objects.values_list("epd_id", flat=True))
    return ids


def _impacts_match(epd, epd_data):
    """True if every gwp_/penrt_ value in the freshly parsed data equals what is
    already stored for this EPD (used to decide whether an in-use EPD changed)."""
    for key, value in epd_data.items():
        if (key.startswith("gwp") or key.startswith("penrt")) and value is not None:
            category, stage = key.split("_")[0], key.split("_")[1]
            imp = EPDImpact.objects.filter(
                epd=epd,
                impact__impact_category=category,
                impact__life_cycle_stage=stage,
            ).first()
            if imp is None or abs(imp.value - float(value)) > 1e-9:
                return False
    return True


def _values_match(existing, epd_data):
    """Whether the stored EPD already matches the source (unit + version + impacts)."""
    return (
        existing.declared_unit == epd_data["declared_unit"]
        and existing.version == epd_data.get("version")
        and _impacts_match(existing, epd_data)
    )


class Command(BaseCommand):
    help = (
        "Load / refresh EPDs from the ECO-Platform API for the ALCBT countries. "
        "New EPDs are created; existing ones are updated in place UNLESS they are "
        "referenced by a building, in which case the original is preserved and a "
        "dated copy carries the refreshed values."
    )

    def handle(self, *args, **options):
        superuser = User.objects.filter(is_superuser=True).first()

        # 1) All ALCBT-country EPD metadata from the portal (uuid -> {uri, geo, ...}).
        epd_info = get_all_uuids_ecoplatform()
        uuids = list(epd_info.keys())
        self.stdout.write(
            self.style.HTTP_INFO(f"Found {len(uuids)} ALCBT-country ECO-Platform EPDs.")
        )

        used_ids = _used_epd_ids()

        created = updated = matched = copied = failure = 0
        uri_issue_list = []

        for uid in uuids:
            uri = epd_info[uid]["uri"]
            geo = epd_info[uid]["geo"]
            try:
                country = Country.objects.get(code2=geo)

                data = get_full_epd(uri)
                epd_data = parse_epd(data)

                existing = EPD.objects.filter(UUID=epd_data["uuid"]).first()

                if existing is None:
                    store_epd(epd_data, country, data, superuser)
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"created  {uri}"))

                elif existing.id in used_ids:
                    # Referenced by a building -> never touch. Copy only if changed.
                    if _values_match(existing, epd_data):
                        matched += 1
                        self.stdout.write(f"in-use, unchanged  {uri}")
                    else:
                        copy_data = dict(epd_data)
                        copy_data["uuid"] = str(uuid_lib.uuid4())
                        copy_data["name"] = f"{epd_data['name']}{UPDATE_MARKER}"
                        store_epd(copy_data, country, data, superuser)
                        copied += 1
                        self.stdout.write(
                            self.style.WARNING(f"in-use, changed -> copy  {uri}")
                        )

                else:
                    # Not referenced by any building -> refresh in place.
                    store_epd(epd_data, country, data, superuser)
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f"updated  {uri}"))

            except Country.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Country with code2={geo} does not exist ({uri}).")
                )
                uri_issue_list.append(uri)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as e:
                # Catch BaseException (not just Exception): the lcax Rust parser
                # raises pyo3_runtime.PanicException on malformed source datasets,
                # and that subclasses BaseException. Without this, a single bad EPD
                # aborts the whole run instead of being skipped.
                logger.exception("Failed to process EPD %s", uri)
                self.stdout.write(self.style.ERROR(f"error on {uri}: {e!r}"))
                uri_issue_list.append(uri)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("ECO-Platform EPD refresh complete.")
        self.stdout.write(f"  New EPDs created:               {created}")
        self.stdout.write(f"  Unused EPDs updated in place:   {updated}")
        self.stdout.write(f"  In-use EPDs unchanged (kept):   {matched}")
        self.stdout.write(f"  In-use EPDs changed -> copy:    {copied}")
        self.stdout.write(f"  Failed URIs:                    {len(uri_issue_list)}")
        self.stdout.write("=" * 60 + "\n")
        if uri_issue_list:
            self.stdout.write(self.style.ERROR(f"Problem uris: {uri_issue_list}"))


def store_epd(epd_data: dict, country: Country, data: dict, superuser):
    """
    Parse the EPD data and link it to the correct material categories and impacts.
    """
    # Some source datasets pad the id / name with stray whitespace (even tabs) —
    # strip so UUIDs stay clean and matchable and names display correctly.
    uuid_val = str(epd_data["uuid"]).strip()
    name_val = (epd_data.get("name") or "").strip()

    classification = resolve_category(epd_data.get("classification"), name_val)

    # Step 2: Create or update the EPD record
    epd, created = EPD.objects.update_or_create(
        UUID=uuid_val,
        defaults={
            "name": name_val,
            "names": epd_data.get("names"),
            "declared_unit": epd_data["declared_unit"],
            "conversions": epd_data["conversions"],
            "category": classification,
            "source": epd_data["source"],
            "type": EPDType.OFFICIAL,
            "country": country,
            "declared_amount": epd_data["declared_amount"],
            "version": epd_data["version"],
            # from base
            "created_by": superuser,
            "public": True,
            "draft": False,
        },
    )

    # Step 3: Parse and link environmental impacts
    for key, value in epd_data.items():
        if key.startswith("gwp") or key.startswith("penrt"):
            if value is not None:
                # Extract impact category and life cycle stage
                impact_category_key = key.split("_")[0]  # e.g., 'gwp'
                life_cycle_stage_key = key.split("_")[1]  # e.g., 'a1a3'

                # Retrieve or create the Impact instance
                impact, _ = Impact.objects.get_or_create(
                    impact_category=impact_category_key,
                    life_cycle_stage=life_cycle_stage_key,
                )

                # Create or update the EPDImpact linking table
                EPDImpact.objects.update_or_create(
                    epd=epd, impact=impact, defaults={"value": value}
                )
    return epd
