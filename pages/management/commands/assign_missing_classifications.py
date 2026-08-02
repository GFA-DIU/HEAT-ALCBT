"""Assign a category classification to structural products that have none
("No category"), by mapping the imported BOQ assembly name to one of the 14
assembly categories.

Why
---
Imported (IFC/BOQ) buildings often leave StructuralProduct.classification NULL,
so the editor shows "No category". Classification is optional labelling (it does
NOT affect the carbon number) but a missing category is untidy. The imported
assemblies use BOQ vocabulary (Superstructure, Openings, ...) that doesn't map
1:1 to the 14 assembly categories, so this command applies an explicit mapping.

Mapping (assembly name -> category tag). "Openings" is refined per product EPD
(window -> Windows, door/plywood -> Doors) since it mixes both:

    finishes -> 120   substructure -> 010   superstructure -> 040
    roofing/roof works -> 060   site works/joints/railings/waterproofing -> 140
    openings -> per-EPD: window 100 / door 110 / else 140

A category-only classification (AssemblyCategoryTechnique with technique=NULL) is
get-or-created per category and reused.

Safety
------
  * Only touches products whose classification IS NULL. Never overwrites an
    existing classification. Idempotent. Transactional. --dry-run writes nothing.
  * Unknown assembly names are skipped and logged (never mis-assigned).
  * --building <id-prefix> limits to one building; default is all buildings.

Usage:
    python manage.py assign_missing_classifications --building acc4eedc --dry-run
    python manage.py assign_missing_classifications --building acc4eedc
    python manage.py assign_missing_classifications            # all buildings
"""

from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.assembly import (AssemblyCategory, AssemblyCategoryTechnique,
                                    StructuralProduct)
from pages.models.building import Building, BuildingAssembly

# assembly name (lower) -> category tag
_NAME_TO_TAG = {
    "finishes": "120",
    "substructure": "010",
    "foundation": "010",
    "pcc for footings": "010",       # plain-cement-concrete footings = foundation work
    "wall below ffl rcc": "010",     # RCC wall below finished-floor-level = substructure
    "superstructure": "040",
    "roofing": "060",
    "roof works": "060",
    "site works": "140",
    "joints": "140",
    "railings": "140",
    "waterproofing": "140",
    # "openings" handled per-EPD below
}


# Keyword fallback for free-text BOQ names that don't exactly match a key above.
# Checked ONLY after exact match misses. First hit wins, so order = priority
# (most specific first). Classification is display-only (does NOT affect carbon),
# so a best-effort keyword tag is strictly better than leaving "No category".
# Deliberately conservative: obvious test rows ("Test", "Hello World", "????")
# match nothing and stay skipped rather than being mis-assigned.
_KEYWORD_RULES = [
    ("roof", "060"),                                             # 060 Roof
    ("railing", "140"), ("balustrade", "140"), ("handrail", "140"),  # 140 Misc
    ("white wash", "120"), ("whitewash", "120"), ("paint", "120"),   # 120 Finishes
    ("plaster", "120"), ("render", "120"), ("mortar", "120"),
    ("ceramic", "120"), ("tile", "120"), ("floor finish", "120"),
    ("gypsum", "120"), ("screed", "120"),
    ("floor construction", "040"),                              # 040 Beams & Slabs
    ("weld mesh", "040"), ("reinforc", "040"), ("rebar", "040"),
    ("lintel", "040"), ("concrete", "040"), ("rcc", "040"),
    ("m20", "040"), ("m25", "040"), ("m30", "040"),
    ("slab", "040"), ("beam", "040"), ("column", "040"),
]


def _tag_for(assembly_name, epd_name):
    name = (assembly_name or "").strip().lower()
    if name == "openings":
        e = (epd_name or "").lower()
        if "window" in e:
            return "100"
        if "door" in e or "plywood" in e:
            return "110"
        return "140"
    tag = _NAME_TO_TAG.get(name)
    if tag is not None:
        return tag
    for kw, kw_tag in _KEYWORD_RULES:      # keyword fallback (substring, priority order)
        if kw in name:
            return kw_tag
    return None


class Command(BaseCommand):
    help = "Assign category classification to 'No category' products via a BOQ-name mapping."

    def add_arguments(self, parser):
        parser.add_argument("--building", help="Limit to this building (id or id prefix).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change; write nothing.")

    def handle(self, *args, **options):
        dry = options["dry_run"]

        cats = {c.tag: c for c in AssemblyCategory.objects.all()}
        act_cache = {}  # tag -> category-only AssemblyCategoryTechnique

        def act_for(tag):
            if tag not in act_cache:
                cat = cats[tag]
                act, _ = AssemblyCategoryTechnique.objects.get_or_create(
                    category=cat, technique=None)
                act_cache[tag] = act
            return act_cache[tag]

        # Iterate the null-classification products DIRECTLY (not via the building
        # walk) so we cover assemblies attached through a regular building, a
        # simulated building, or none at all — uniformly.
        qs = (StructuralProduct.objects
              .filter(classification__isnull=True)
              .select_related("assembly", "epd"))
        if options["building"]:
            aids = set(BuildingAssembly.objects
                       .filter(building__id__startswith=options["building"])
                       .values_list("assembly_id", flat=True))
            try:
                from pages.models.building import BuildingAssemblySimulated
                aids |= set(BuildingAssemblySimulated.objects
                            .filter(building__id__startswith=options["building"])
                            .values_list("assembly_id", flat=True))
            except Exception:
                pass
            qs = qs.filter(assembly_id__in=aids)

        assigned = 0
        skipped_unknown = Counter()
        by_cat = Counter()

        with transaction.atomic():
            for sp in qs:
                aname = sp.assembly.name if sp.assembly else ""
                tag = _tag_for(aname, sp.epd.name if sp.epd else "")
                if tag is None or tag not in cats:
                    skipped_unknown[aname] += 1
                    continue
                if not dry:
                    sp.classification = act_for(tag)
                    sp.save(update_fields=["classification"])
                assigned += 1
                by_cat[f"{tag} {cats[tag].name}"] += 1

            if dry:
                transaction.set_rollback(True)

        head = "[DRY RUN] would assign" if dry else "Assigned"
        self.stdout.write(self.style.SUCCESS(f"\n{head} {assigned} classification(s)."))
        for k, n in by_cat.most_common():
            self.stdout.write(f"   {n:4}  -> {k}")
        if skipped_unknown:
            self.stdout.write(self.style.WARNING(
                f"Skipped {sum(skipped_unknown.values())} product(s) with unmapped "
                f"(free-text) assembly names — {len(skipped_unknown)} distinct name(s):"))
            for k, n in skipped_unknown.most_common():
                # console-safe: assembly names can contain non-cp1252 characters
                safe = (k or "").encode("ascii", "replace").decode("ascii")
                self.stdout.write(f"   {n:4}  {safe!r}")
