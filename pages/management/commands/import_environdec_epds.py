"""Load the extracted environdec EPDs into the catalogue.

Reads the CSV produced by `extract_environdec_epds` and creates one EPD per row
that clears three gates. Anything that does not clear them is written to a
rejects CSV with the reason, never imported on a guess.

    1. a declared unit was captured
       Without it the GWP figure has no basis and `calculate_impacts` cannot
       convert it.

    2. the implied kgCO2e per kg sits inside a band for its material
       This is the gate that catches extraction errors the parser could not.
       A legend line in one declaration produced 5.0 kgCO2e/tonne for a CEM
       III/A cement - about 1/70th of the real figure, and entirely plausible
       looking in a spreadsheet. The parser now refuses that line, but the
       band is what catches the next one.

    3. the product name maps to a real leaf category
       The shortlist's own material_group cannot be trusted: it files sand,
       aggregates and fly ash under "cement". The name is matched instead, and
       a row that cannot be placed is rejected rather than parked on a vague
       top-level node.

Idempotent, keyed on (name, country) like the other loaders, so a re-run
updates rather than duplicates.

    python manage.py import_environdec_epds --dry-run
    python manage.py import_environdec_epds
"""
import csv
import os
import re
from collections import Counter
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.epd import EPD, EPDImpact, EPDType, Impact, MaterialCategory
from pages.scripts.csv_import.utils import get_country, get_superuser

SOURCE_LABEL = "EPD International (environdec.com)"

# Product name -> (leaf category_id, material name for the label).
# First match wins, so the specific patterns come first: "cement mortar" is a
# mortar, and "aggregate" beats the material_group that calls it cement.
# Products that are not building materials and must never be offered as one.
# The semi-finished steel becomes the rebar and sections already in the
# catalogue, so carrying it invites double counting; the control room is a
# whole assembly; the CEM III/A figure is the known bad extraction.
EXCLUDE = re.compile(
    r"^(?:billet|bloom|slab)\b|coal.based direct reduced|"
    r"acoustic modular|blast furnace cement cem iii/a|"
    # plywood: A1-A3 is negative because sequestration is declared in A1, and
    # BEAT sums A1-A3 straight into the building total. Held back pending a
    # methodology decision rather than quietly crediting timber buildings.
    r"plywood|indowud",
    re.I,
)

CATEGORY_RULES = [
    (r"\bclinker\b",                        "1.1.01", "Cement clinker"),
    # --- named board ranges, before the generic board rules -----------------
    # The Siam Gypsum (Saraburi) and Knauf Indonesia ranges are gypsum
    # plasterboard sold under product names that never say so.
    (r"standard board|standardshield|multiwall|moistbloc|glassbloc|"
     r"easy finish|flex board|fire\s?shield|sound\s?shield|moist\s?shield|standard\s?shield",
                                            "1.3.13", "Gypsum plasterboard"),
    (r"calcium silicate|hilux|greencor|heavy duty board|multiproa",
                                            "1.3.12", "Fibre cement board"),
    (r"\bacp\b|aluminium composite pan|composite panel",
                                            "1.3.07", "Aluminium composite panel"),
    # --- BUMATECH (Vietnam): one maker's tile-fixing and waterproofing range
    (r"bumalastic|ceralastic|proof 668",     "6.6.01", "Waterproofing membrane"),
    (r"bumalevel",                           "1.4.03", "Levelling screed"),
    (r"bumaskim",                            "1.4.04", "Skim coat"),
    (r"bumabond|bumafix|bumaflex|bumaset|bumaeco|ceracolor",
                                            "1.4.05", "Tile adhesive"),
    # --- insulation ranges ---------------------------------------------------
    (r"green batts|cylence|blanket insulation|board insulation|"
     r"pipe insulation|encapsulated insulation",
                                            "2.1.02", "Glass wool insulation"),
    (r"xlpe|aeroflex|aerolam|aerofoam",     "2.18.01", "Polyethylene foam insulation"),
    # --- metals, by product form ----------------------------------------------
    (r"prestressed concrete steel wire|\bpc wire\b|\bpc strand\b|lrpc",
                                            "4.1.01", "Prestressing steel strand"),
    (r"hot roll|hot-roll|sheet coil|plate mill|magnelis|nexalume|nexium|"
     r"satin silver|metallic coated sheet",
                                            "4.1.04", "Steel sheet"),
    (r"wire rod|welded pipe|\bcra\b",       "4.1.03", "Steel long product"),
    (r"alumini?um billet",                  "4.3.03", "Aluminium billet"),
    (r"copper rod",                         "4.4.03", "Copper rod"),
    # --- glazed facade systems, matched on the maker --------------------------
    # Complete aluminium-framed assemblies, declared per m2 of facade.
    (r"glass wall systems|curtain wall|store front|window wall|punched window",
                                            "7.1.05", "Aluminium curtain wall system"),
    # --- remaining named ranges ------------------------------------------------
    (r"insee eco",                          "1.1.01", "Cement"),
    (r"scg bulk type",                      "1.1.01", "Cement"),
    (r"easy mix|terrazzo|pebble washed",    "1.4.02", "Decorative mortar"),
    (r"raised access floor",                "6.2.06", "Raised access floor panel"),
    (r"geotextile|geo woven|maxacore",      "6.6.07", "Geotextile"),
    (r"aggregate|\bsand\b|gravel|stonetec|sandtec|crushed stone|3/4 stone",
                                            "1.2.01", "Sand and gravel"),
    (r"fly ash|\bpfa\b|pozzolan|puzzolan",  "1.2.08", "Fly ash"),
    # "Slag cement" is a cement that contains slag, not the raw byproduct, and
    # "fibre cement board" is a board, not a cement. Both have to beat the
    # plainer rules below or they land in the wrong plausibility band.
    (r"slag cement|cement.*\bslag\b",       "1.1.01", "Slag cement"),
    (r"fibre cement|fiber cement",          "1.3.12", "Fibre cement board"),
    (r"\bslag\b|ggbs|ggbfs",                "1.2.08", "Ground granulated blast furnace slag"),
    (r"skim coat|plastering mortar|masonry mortar|mortar",
                                            "1.4.02", "Mortar"),
    (r"screed",                             "1.4.03", "Screed"),
    (r"render|plaster(?!board)",            "1.4.04", "Render"),
    (r"tile adhesive|adhesive|keraflex|keraset|webertai",
                                            "1.4.05", "Tile adhesive"),
    (r"admix|superplasticis|plasticiz|polycarboxylate",
                                            "1.4.06", "Concrete admixture"),
    (r"ready.?mix|\bconcrete\b|\bc\d{2}/\d{2}\b",
                                            "1.4.01", "Ready mixed concrete"),
    (r"\bcement\b",                         "1.1.01", "Cement"),
    # Most of the Thai and Vietnamese cements are named by grade alone, with
    # no word "cement" anywhere: OPC (ordinary Portland), PCC/PCB (Portland
    # composite), PPC (Portland pozzolana), PSC (Portland slag), and the
    # EN CEM I/II/III designations.
    (r"\b(?:opc|ppc|pcc|psc)\b|\bpcb\s?\d{2}\b|\bpc\s?\d{2}\b|\bcem\s?i{1,3}\b",
                                            "1.1.01", "Cement"),
    (r"\blime\b",                           "1.1.02", "Lime"),
    # --- glazing -------------------------------------------------------------
    (r"float glass|laminated glass|tinted glass|frosted glass|coated glass|"
     r"heat treated glass|ceramic frit|insulated glass|glass unit|\bigu\b|"
     r"fire resistant glass",               "7.2.01", "Glass"),
    # --- waterproofing --------------------------------------------------------
    (r"mapelastic|polyurea|waterproof|\blastic\b",
                                            "6.6.01", "Waterproofing membrane"),
    (r"fire ?bloc|fire protection board",   "1.3.18", "Fire protection board"),
    # --- boards ------------------------------------------------------------
    (r"plasterboard|gypsum board|jayaboard|gyproc|drywall",
                                            "1.3.13", "Gypsum plasterboard"),
    (r"ceiling (?:panel|tile)",             "1.3.15", "Ceiling panel"),
    (r"roof tile",                          "1.3.11", "Concrete roof tile"),
    (r"\bbrick\b",                          "1.3.02", "Fired brick"),
    (r"aerated concrete|\baac\b",           "1.3.03", "Aerated concrete"),
    (r"precast|spun pile|\bpile\b|lintel",  "1.3.05", "Precast concrete element"),
    # --- metals --------------------------------------------------------------
    (r"rebar|reinforc(?:ing|ement) bar|deformed bar|tmt",
                                            "4.1.01", "Steel reinforcing bar"),
    (r"reinforcement mesh|welded mesh",     "4.1.02", "Steel reinforcement mesh"),
    (r"stainless.*(?:profile|section)",     "4.2.02", "Stainless steel profile"),
    (r"stainless.*sheet",                   "4.2.01", "Stainless steel sheet"),
    (r"steel (?:sheet|coil)|cold rolled|hot rolled|galvani",
                                            "4.1.04", "Steel sheet"),
    (r"steel (?:section|profile|tube|pipe)|hollow section|\bh.?beam\b",
                                            "4.1.03", "Structural steel profile"),
    (r"alumini?um.*(?:profile|extrus)",     "4.3.02", "Aluminium profile"),
    (r"alumini?um.*sheet",                  "4.3.01", "Aluminium sheet"),
    (r"\bsteel\b",                          "4.1.03", "Structural steel"),
    # --- insulation ------------------------------------------------------------
    (r"glass wool",                         "2.1.02", "Glass wool insulation"),
    (r"rock ?wool|stone wool",              "2.1.03", "Rock wool insulation"),
    (r"mineral wool",                       "2.1.01", "Mineral wool insulation"),
]

# kgCO2e per kg of material. Deliberately generous - this is a sanity gate, not
# a benchmark. Keyed on the leaf category the name resolved to.
#
# A category with no band here cannot be sanity-checked, so a row that resolves
# to one is rejected rather than imported unchecked. That is the point of the
# gate: an unverifiable number is not better than a missing one.
MASS_BANDS = {
    "1.1.01": (0.10, 1.20),    # cement and clinker
    "1.1.02": (0.50, 1.50),    # lime
    "1.2.01": (0.001, 0.05),   # sand and gravel
    "1.2.08": (0.001, 0.30),   # fly ash, slag - byproducts
    "1.4.01": (0.02, 0.60),    # ready-mix concrete, by mass
    "1.4.02": (0.05, 0.80),    # mortar
    "1.4.03": (0.05, 0.80),
    "1.4.04": (0.05, 1.00),
    "1.4.05": (0.10, 2.00),    # adhesives
    "1.4.06": (0.30, 6.00),    # concrete admixture
    "1.3.13": (0.10, 2.00),    # plasterboard
    "1.3.05": (0.05, 0.60),
    "1.3.02": (0.04, 0.80),    # brick, low-carbon types run to 0.08
    "1.3.12": (0.50, 3.00),    # fibre cement board
    "6.6.01": (0.50, 8.00),    # waterproofing membrane
    "4.1.01": (0.50, 4.00),    # steel
    "4.1.02": (0.50, 4.00),
    "4.1.03": (0.50, 6.00),
    "4.1.04": (0.50, 6.00),
    "4.2.01": (2.00, 8.00),    # stainless
    "4.2.02": (2.00, 8.00),
    "4.3.01": (4.00, 25.0),    # aluminium
    "4.3.02": (4.00, 25.0),
    "4.3.03": (1.00, 25.0),    # billet; recycled stock sits near the bottom
    "4.4.03": (2.00, 10.0),    # copper
    "1.3.07": (1.00, 25.0),    # aluminium composite panel
    "1.3.12": (0.50, 3.00),    # fibre cement board
    "2.1.02": (1.00, 8.00),    # glass wool
    "2.18.01": (1.00, 12.0),   # PE / XLPE foam
    "6.6.01": (0.50, 8.00),    # waterproofing membrane
    "6.6.07": (1.00, 12.0),    # geotextile
}

# kgCO2e per m2, for the products declared by area rather than by mass.
AREA_BANDS = {
    "7.2.01": (5.0, 120.0),    # glazing, single pane to an insulated unit
    "1.3.13": (0.5, 20.0),     # plasterboard; 9mm standard runs to 0.88
    "1.3.18": (1.0, 30.0),     # fire protection board
    "1.3.15": (1.0, 30.0),     # ceiling panel
    "6.6.01": (0.2, 20.0),     # waterproofing membrane
    "1.3.12": (2.0, 40.0),     # fibre cement board
    "2.1.02": (0.3, 12.0),     # glass wool batts and blanket
    "1.3.07": (5.0, 80.0),     # aluminium composite panel
    "7.1.05": (20.0, 200.0),   # glazed facade system, per m2 of facade
    "6.2.06": (10.0, 120.0),   # raised access floor panel
}


def infer_mass_unit(gwp, band):
    """Guess 'kg' or 'tonne' for a row whose declared unit was not captured.

    Six rows lost their unit to the PDF layout, but their magnitude settles it:
    nothing is declared at 2,724 kgCO2e per kilogram. The guess is only made
    when exactly one basis lands inside the band - if both or neither do, the
    row is ambiguous and is rejected instead.
    """
    fits = [u for u, factor in (("kg", 1.0), ("tonne", 1000.0))
            if band[0] <= gwp / factor <= band[1]]
    return fits[0] if len(fits) == 1 else None

# Ready-mix is usually declared per m3; ~2400 kg/m3 converts the mass band.
CONCRETE_DENSITY = 2400.0

MASS_UNITS = {"kg": 1.0, "kilogram": 1.0, "tonne": 1000.0, "ton": 1000.0}

REJECT_FIELDS = ["reason", "country", "product", "manufacturer", "gwp_a1a3",
                 "declared_amount", "declared_unit", "url"]


def classify(product, manufacturer=""):
    """(category_id, material) for a product, or (None, None).

    The product name is tried alone first. Only if that says nothing is the
    manufacturer consulted, for the few products named purely by range -
    "Thermal Insulation Products", "Store Front SF-102".

    The order matters. Matching both together put every Tiger and SCG cement
    into "sand and gravel", because their maker is "The Concrete Products and
    Aggregate Co., Ltd." and the aggregate rule sits above the cement one.
    """
    for text in (product or "", "%s %s" % (product or "", manufacturer or "")):
        hit = _match(text.lower())
        if hit != (None, None):
            return hit
    return None, None


def _match(name):
    for pattern, cat, material in CATEGORY_RULES:
        if re.search(pattern, name):
            return cat, material
    return None, None


class Command(BaseCommand):
    help = "Import extracted environdec EPDs that pass the plausibility gates."

    def add_arguments(self, parser):
        parser.add_argument("--in", dest="infile", default=os.path.expanduser(
            "~/Downloads/environdec_parsed_404.csv"))
        parser.add_argument("--rejects", default=os.path.expanduser(
            "~/Downloads/environdec_rejected.csv"))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        rows = [r for r in csv.DictReader(open(o["infile"], encoding="utf-8-sig"))
                if r["status"] == "OK"]
        self.stdout.write("parsed rows available: %d" % len(rows))

        try:
            with transaction.atomic():
                created, updated, rejects = self._run(rows)
                self._report(created, updated, rejects, o["rejects"])
                if o["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                "\nDry run - rolled back, nothing written."))
            return
        self.stdout.write(self.style.SUCCESS("\nDone."))

    # ------------------------------------------------------------------
    def _run(self, rows):
        superuser = get_superuser()
        cats = {c.category_id: c for c in MaterialCategory.objects.filter(
            category_id__in={c for _, c, _ in CATEGORY_RULES})}
        gwp_impact, _ = Impact.objects.get_or_create(
            impact_category="gwp", life_cycle_stage="a1a3")

        created = updated = 0
        rejects = []

        # Three Siam Gypsum boards are published twice under the same name with
        # different registration numbers and different figures - Standard Board
        # 9mm is 0.876 in one declaration and 1.33 in another. Keyed on
        # (name, country) the second would silently overwrite the first, so the
        # registration number is appended to tell them apart. Dropping one
        # would mean discarding a published declaration on our own authority.
        seen = Counter((r["product"].strip(), r["country"]) for r in rows)
        collisions = {k for k, n in seen.items() if n > 1}

        for r in rows:
            reject = lambda why: rejects.append(
                dict({k: r.get(k, "") for k in REJECT_FIELDS if k != "reason"},
                     reason=why))

            if EXCLUDE.search(r["product"] or ""):
                reject("not a building material, or held back by decision")
                continue

            unit = (r["declared_unit"] or "").lower()
            try:
                gwp = Decimal(str(r["gwp_a1a3"]))
                amount = Decimal(str(r["declared_amount"] or 1))
            except Exception:
                reject("unreadable amount or GWP"); continue
            if amount <= 0:
                reject("declared amount is zero"); continue

            cat_id, material = classify(r["product"], r.get("manufacturer"))
            if not cat_id or cat_id not in cats:
                reject("product name does not map to a leaf category"); continue

            # A row whose unit the PDF layout swallowed can still be placed
            # when only one mass basis is plausible for its material.
            if not unit:
                guess = infer_mass_unit(float(gwp), MASS_BANDS[cat_id]) \
                    if cat_id in MASS_BANDS else None
                if not guess:
                    reject("no declared unit captured, and the value does not "
                           "settle it"); continue
                unit, amount = guess, Decimal("1")

            # --- plausibility ------------------------------------------------
            # Pick the band that matches how the product is declared. A row
            # with no applicable band is rejected, not waved through.
            if unit in MASS_UNITS and cat_id in MASS_BANDS:
                basis = "kgCO2e/kg"
                value = float(gwp) / (float(amount) * MASS_UNITS[unit])
                band = MASS_BANDS[cat_id]
            elif unit in ("m3", "m³") and cat_id in MASS_BANDS:
                basis = "kgCO2e/kg via %g kg/m3" % CONCRETE_DENSITY
                value = float(gwp) / (float(amount) * CONCRETE_DENSITY)
                band = MASS_BANDS[cat_id]
            elif unit in ("m2", "m²") and cat_id in AREA_BANDS:
                basis = "kgCO2e/m2"
                value = float(gwp) / float(amount)
                band = AREA_BANDS[cat_id]
            else:
                reject("declared per %s - no plausibility band for category %s"
                       % (unit, cat_id))
                continue

            if not (band[0] <= value <= band[1]):
                reject("implausible: %.4g %s, expected %g-%g"
                       % (value, basis, band[0], band[1]))
                continue

            # --- country -----------------------------------------------------
            cname = {"Viet Nam": "Vietnam"}.get(r["country"], r["country"])
            try:
                country = get_country(cname)
            except Exception:
                reject("unknown country %r" % r["country"]); continue

            # BEAT stores the declared amount in the declared unit's base
            # (1000 for a per-tonne declaration) and divides by it on read.
            if unit in MASS_UNITS:
                declared_unit, declared_amount = "kg", amount * Decimal(
                    str(MASS_UNITS[unit]))
            else:
                declared_unit = "m3" if unit in ("m3", "m³") else (
                    "m2" if unit in ("m2", "m²") else unit)
                declared_amount = amount

            name = (r["product"] or "").strip()
            if (name, r["country"]) in collisions:
                reg = (r["registration_number"] or "").split(":")[0]
                name = "%s (%s)" % (name, reg) if reg else name
            name = name[:255]
            epd, was_created = EPD.objects.update_or_create(
                name=name, country=country,
                defaults={
                    "type": EPDType.OFFICIAL,
                    "declared_unit": declared_unit,
                    "declared_amount": declared_amount,
                    "source": r["url"],
                    "created_by": superuser,
                    "public": True,
                    "category": cats[cat_id],
                    "UUID": (r["registration_number"] or name)[:255],
                    "names": [{"lang": "en", "value": name}],
                    "conversions": [],
                    # filled properly at import, as agreed, rather than being
                    # backfilled by guesswork later
                    "material_name": material,
                    "product_name": name,
                    "manufacturer": (r["manufacturer"] or "").strip()[:255] or None,
                    "source_name": name,
                },
            )
            EPDImpact.objects.update_or_create(
                epd=epd, impact=gwp_impact, defaults={"value": gwp})
            created += was_created
            updated += not was_created

        return created, updated, rejects

    # ------------------------------------------------------------------
    def _report(self, created, updated, rejects, path):
        self.stdout.write("\nimported: %d created, %d updated" % (created, updated))
        self.stdout.write("rejected: %d" % len(rejects))
        if rejects:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.DictWriter(fh, fieldnames=REJECT_FIELDS)
                w.writeheader()
                for r in rejects:
                    w.writerow(r)
            self.stdout.write("  -> %s" % path)
            for reason, n in Counter(
                    re.sub(r"[\d.]+", "N", r["reason"]) for r in rejects).most_common(10):
                self.stdout.write("   %4d  %s" % (n, reason[:84]))


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
