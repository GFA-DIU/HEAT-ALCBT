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
CATEGORY_RULES = [
    (r"\bclinker\b",                        "1.1.01", "Cement clinker"),
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
    (r"admixture|superplasticis|plasticiz|polycarboxylate",
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
}

# kgCO2e per m2, for the products declared by area rather than by mass.
AREA_BANDS = {
    "7.2.01": (5.0, 120.0),    # glazing, single pane to an insulated unit
    "1.3.13": (1.0, 20.0),     # plasterboard
    "1.3.18": (1.0, 30.0),     # fire protection board
    "1.3.15": (1.0, 30.0),     # ceiling panel
    "6.6.01": (0.2, 20.0),     # waterproofing membrane
    "1.3.12": (2.0, 40.0),     # fibre cement board
}

# Ready-mix is usually declared per m3; ~2400 kg/m3 converts the mass band.
CONCRETE_DENSITY = 2400.0

MASS_UNITS = {"kg": 1.0, "kilogram": 1.0, "tonne": 1000.0, "ton": 1000.0}

REJECT_FIELDS = ["reason", "country", "product", "manufacturer", "gwp_a1a3",
                 "declared_amount", "declared_unit", "url"]


def classify(product):
    """(category_id, material) for a product name, or (None, None)."""
    name = (product or "").lower()
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

        for r in rows:
            reject = lambda why: rejects.append(
                dict({k: r.get(k, "") for k in REJECT_FIELDS if k != "reason"},
                     reason=why))

            unit = (r["declared_unit"] or "").lower()
            if not unit:
                reject("no declared unit captured"); continue
            try:
                amount = Decimal(str(r["declared_amount"]))
                gwp = Decimal(str(r["gwp_a1a3"]))
            except Exception:
                reject("unreadable amount or GWP"); continue
            if amount <= 0:
                reject("declared amount is zero"); continue

            cat_id, material = classify(r["product"])
            if not cat_id or cat_id not in cats:
                reject("product name does not map to a leaf category"); continue

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

            name = (r["product"] or "").strip()[:255]
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
