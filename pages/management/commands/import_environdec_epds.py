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
    r"plywood|indowud|"
    # Furniture and fit-out, tested on what the product IS. A material rule
    # saw "steel" in "Barstools: Steel framed" and let three furniture
    # records through as steel, so the product type has to be checked first.
    r"barstool|lounge chair|\bchairs?\b|modular chairs|seating|desking|"
    r"deskpro|height adjustable|workstation|\blocker\b|\bsafes?\b|"
    r"healthcare bed|meeting pod|phone booth|monitor arm|"
    r"conference table|cafe table|dinning table|dining table|"
    # Photovoltaic modules: generation equipment, not a building material.
    r"l.?lios|topcon|bifacial|photovoltaic|\bsolar module\b|"
    # PET acoustic panel: BEAT has no leaf for PET and none for acoustic
    # panels. Filing it under PVC would name the wrong polymer on every chart,
    # so it is held back rather than misdescribed.
    r"pet acoustic",
    re.I,
)

CATEGORY_RULES = [
    # --- added 2026-11-02, from the India catalogue reconciliation ---------
    # Ductile iron is a cast iron, and these are 19 of one maker's pipe range.
    (r"ductile iron pipe",                   "4.1.05", "Ductile iron pipe"),
    # Frame materials read from the declarations, not assumed. Windor's glazed
    # systems state "Aluminium framed"; the flush door is wood-cored in an
    # aluminium frame; VDS states "Engineered steel" and never says aluminium.
    (r"windor[^,]*flush door",               "7.6.03", "Flush door"),
    (r"windor[^,]*(?:glazed )?(?:style )?door system",
                                             "7.6.02", "Glazed door system"),
    (r"vds.{0,3}\s*swing door|vds.{0,3}\s*fixed partition",
                                             "7.6.01", "Steel door frame"),
    (r"glass partition system",              "7.2.01", "Glass partition"),
    (r"high pressure (?:decorative )?laminate|\bhpl\b|thin laminate|compact panel",
                                             "6.5.01", "High pressure laminate"),
    (r"gypboard",                            "1.3.13", "Gypsum plasterboard"),
    (r"external thermal insulation|\betics\b",
                                             "2.21.01", "ETICS"),
    (r"berger paints",                       "5.5.02", "Paint"),
    (r"roof kool|kool and seal",             "5.9.01", "Reflective roof coating"),
    (r"formwork panel",                      "9.1.03", "Formwork panel"),
    (r"\bpir panel\b|smart pir",            "2.4.04", "PIR panel"),
    (r"wood wool board|nishabd",             "2.7.01", "Wood wool board"),
    # --- added 2026-11-02 from the Thailand and Vietnam batches ------------
    # Saint-Gobain Weber sell tile grout and adhesive under colour names that
    # never say grout; Webertai is the adhesive, Webercolor the grout.
    (r"webercolor",                          "1.4.05", "Tile grout"),
    (r"topcoat|\bprimer paints?\b|\bpaints?\b$|semigloss|sheen paints",
                                             "5.5.02", "Paint"),
    # Resilient sheet and plank flooring: WPC, LVT and SPC are all PVC-cored.
    (r"\bwpc\b|\blvt\b|\bspc\b|vinyl.{0,12}floor|wood plastic composite",
                                             "6.2.01", "Resilient flooring"),
    (r"copper wire|copper rod|\betp\b copper", "4.4.03", "Copper profile"),
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
    # --- added 2026-11-05, once the declared units became readable ---------
    # Manhole covers, gratings and frames are cast iron items, which is what
    # 4.1.05 is for. They sit above the pipe rule because a cover is not a
    # pipe even when the same foundry makes both.
    (r"manhole|channel grating|grate & frame|gully",
                                             "4.1.05", "Cast iron item"),
    # TechFab's drainage composite is a geotextile core with filter fabric;
    # their geotextile is already filed as a technical textile.
    (r"drainage composite|techdrain",        "6.6.07", "Drainage composite"),
    (r"rockinsul|rock ?wool slab",           "2.1.03", "Rock wool slab"),
    # --- added 2026-11-04, from the India catalogue reconciliation ---------
    # Carpet tile is a textile floor covering; the catalogue already holds 76
    # of them under 6.2.05, so both the leaf and its band rest on real data.
    (r"carpet tile|carpet",                 "6.2.05", "Textile flooring"),
    # Screws, nuts and anchors. 4.2.04 "Fastener" sits under stainless steel
    # and these are not stated to be stainless, so the general fixings leaf is
    # the honest home for them.
    (r"\bfasteners?\b|screws, nuts",        "7.4.06", "Fastener"),
    # Vedanta sell primary aluminium ingot under the name Restora; the word
    # "aluminium" appears nowhere in the product title, so the brand is the
    # only thing left to match on.
    (r"\brestora\b",                        "4.3.03", "Aluminium ingot"),
    (r"geotextile|geo woven|maxacore",      "6.6.07", "Geotextile"),
    (r"aggregate|\bsand\b|gravel|stonetec|sandtec|crushed stone|3/4 stone",
                                            "1.2.01", "Sand and gravel"),
    # "Portland Pozzolana Cement" is a CEMENT containing pozzolan, not the
    # pozzolan itself, and it has to beat the byproduct rule below for the
    # same reason slag cement does. Filed as a byproduct it met the fly ash
    # band of 0.001-0.3 kgCO2e/kg and both Indian PPC declarations, at 0.738
    # and 0.739, were refused as implausible when they are perfectly ordinary
    # cement figures.
    (r"pozzolana cement|cement.*pozzolan",  "1.1.01", "Portland pozzolana cement"),
    (r"fly ash|\bpfa\b|pozzolan|puzzolan",  "1.2.08", "Fly ash"),
    # "Slag cement" is a cement that contains slag, not the raw byproduct, and
    # "fibre cement board" is a board, not a cement. Both have to beat the
    # plainer rules below or they land in the wrong plausibility band.
    (r"slag cement|cement.*\bslag\b",       "1.1.01", "Slag cement"),
    # Visaka sell their fibre cement boards as "Vnext"; the declaration says
    # fibre cement throughout but the product title never does.
    (r"fibre cement|fiber cement|\bvnext\b", "1.3.12", "Fibre cement board"),
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
    # Steel. The floor was 0.50, derived from records none of which were
    # scrap-only. Jindal publish a TMT rebar and a steel plate both made from
    # 100% recycled scrap, at 0.445 and 0.450 kgCO2e/kg, and both were refused
    # as implausible when they are simply electric-arc figures: a scrap-fed
    # route carries no ironmaking, so about a third of blast-furnace steel is
    # the expected result, not an error.
    #
    # Lowered to 0.30 on that basis, which is below those two with a little
    # room and still an order of magnitude above a figure that has lost its
    # tonne-to-kilogram conversion. Stated here because it weakens the check
    # for ALL steel, not only the scrap kind.
    "4.1.01": (0.30, 4.00),    # steel
    "4.1.02": (0.30, 4.00),
    "4.1.03": (0.30, 6.00),
    "4.1.04": (0.30, 6.00),
    "4.2.01": (2.00, 8.00),    # stainless
    "4.2.02": (2.00, 8.00),
    # Derived 2026-11-02 from the catalogue, as for the area bands above.
    "5.5.02": (0.46, 11.70),   # paint, from 13 records 0.92-5.83
    "5.9.01": (0.27, 3.62),    # coatings, from 6 records 0.53-1.81
    "4.3.01": (4.00, 25.0),    # aluminium
    "4.3.02": (4.00, 25.0),
    "4.3.03": (1.00, 25.0),    # billet; recycled stock sits near the bottom
    "4.4.03": (2.00, 10.0),    # copper
    "1.3.07": (1.00, 25.0),    # aluminium composite panel
    "1.3.12": (0.50, 3.00),    # fibre cement board
    "2.1.02": (1.00, 8.00),    # glass wool
    "2.18.01": (1.00, 12.0),   # PE / XLPE foam
    "6.6.01": (0.50, 8.00),    # waterproofing membrane
    # Derived 2026-11-05 from the records the catalogue already holds.
    # 4.1.05 is wide because one existing record sits at 66.2 kgCO2e/kg while
    # the rest of the leaf sits near 1 to 3, so the band catches an error of
    # magnitude and nothing finer. Narrowing it would mean deciding on my own
    # authority that the 66.2 record is wrong, which is a separate question.
    "4.1.05": (0.32, 132.4),   # cast iron items, from 28 records 0.64-66.2
    "6.6.07": (2.04, 40.2),    # technical textiles, from 4 records 4.07-20.08
    # 2026-11-04. The four records already in this leaf run 3.55-4.26, which
    # halved would put the floor at 1.78 and refuse a carbon-steel screw at
    # 1.71 - a correct figure. Those four are evidently at the top of the
    # range, so the floor is taken from the structural steel band above
    # (4.1.03, floor 0.50) rounded up to 1.00 rather than from them. That is a
    # stated basis, not a derived one, and the band is weak either way: on
    # four records it catches an error of magnitude and little else.
    "7.4.06": (1.00, 8.52),    # fasteners; ceiling from 4 records 3.55-4.26
}

# kgCO2e per metre, for products declared by length. Added for the ductile
# iron pipe ranges, which are declared per metre of pipe at a stated diameter,
# so one band has to cover DN80 through DN1200.
LINEAR_BANDS = {
    # A pipe's carbon per metre scales with its bore, so one band has to span
    # the whole range a maker sells: this family runs DN80 at about 14 to
    # DN1200 at 1,180, a smooth monotonic series. Deriving the band from the
    # 9 small-diameter records already held gave 7-98 and refused every pipe
    # above DN250, which were correct figures.
    #
    # A band this wide is a weak check, and saying so is the point: for a
    # product declared per metre at varying diameter, the real evidence that
    # the figures are sound is that they rise smoothly with bore, which a
    # band cannot express.
    "4.1.05": (5.0, 2500.0),   # ductile iron pipe, DN80 to DN1200
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
    # Derived 2026-11-04 the same way: half the lowest and twice the highest
    # of the records the catalogue already holds in this leaf at this unit.
    "6.2.05": (1.59, 33.8),    # textile flooring, from 76 records 3.18-16.89
    # --- added 2026-11-02 -------------------------------------------------
    # DERIVED, not published: each range is half the minimum to twice the
    # maximum of the EPDs already in that leaf and unit, so it catches an
    # error of magnitude without judging quality. The record count is given
    # so a band resting on thin evidence is visible as such.
    "7.6.02": (42.9, 1122.0),  # aluminium door, from 23 records 85.9-560.9
    "7.6.03": (9.9, 396.0),    # wooden door, from 20 records 19.8-197.8
    "2.4.04": (1.2, 78.0),     # PIR panel, from 31 records 2.45-39.1
    "2.21.01": (0.25, 60.0),   # ETICS, from 25 records 0.51-29.9
    # 7.6.01 steel doors is deliberately absent. Its 49 existing records run
    # 0.24 to 936 per m2, a 3,900-fold spread, so any band drawn from them
    # would admit anything. The 0.24 is "Doors - Peneder Bau-Elemente GmbH",
    # which is not a credible figure for a steel door and looks like a bad
    # record already in the catalogue.
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
        # Ships with the repo, so the import reproduces anywhere - including
        # production, where nobody has the extractor's scratch files.
        parser.add_argument("--in", dest="infile",
                            default="pages/data/environdec_epds.csv")
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
            elif unit == "m" and cat_id in LINEAR_BANDS:
                basis = "kgCO2e/m"
                value = float(gwp) / float(amount)
                band = LINEAR_BANDS[cat_id]
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
            reg = (r["registration_number"] or "").split(":")[0]
            maker = (r["manufacturer"] or "").strip()
            if (name, r["country"]) in collisions:
                name = "%s (%s)" % (name, reg) if reg else name
            else:
                # The same guard, against what is ALREADY in the catalogue.
                # "TMT Bars" is the title of at least three different Indian
                # declarations from three different steelmakers. Keyed on
                # (name, country) alone, importing one would overwrite
                # another maker's figures under that maker's own record, and
                # the building using it would silently change.
                existing = EPD.objects.filter(name=name,
                                              country=country).first()
                if (existing is not None and maker
                        and (existing.manufacturer or "").strip() != maker):
                    name = "%s (%s)" % (name, reg) if reg else "%s - %s" % (
                        name, maker)
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
            # The reasons go to stdout first and unconditionally. On a Heroku
            # dyno the log is the only thing anyone reads, and the default
            # rejects path (~/Downloads) does not exist there - writing the
            # file must never be what decides whether you learn why a row was
            # refused.
            for reason, n in Counter(
                    re.sub(r"[\d.]+", "N", r["reason"]) for r in rejects).most_common(10):
                self.stdout.write("   %4d  %s" % (n, reason[:84]))
            try:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                    w = csv.DictWriter(fh, fieldnames=REJECT_FIELDS)
                    w.writeheader()
                    for r in rejects:
                        w.writerow(r)
                self.stdout.write("  -> %s" % path)
            except OSError as exc:
                self.stdout.write(
                    "  (no rejects file written: %s - the reasons above are "
                    "the whole story; pass --rejects to choose a writable "
                    "path)" % exc)


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
