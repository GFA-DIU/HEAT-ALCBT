"""Populate the split EPD name fields from what is already known.

`name` arrived from a dozen importers and carries whatever the source document
was titled - the material, a trade name alone, the maker buried mid-string, or
a specification dump. Migration 0056 adds material_name, product_name,
manufacturer and source_name so the label can be composed; this fills them in
where that can be done safely, and reports the rest rather than guessing.

What it derives
---------------
source_name   every record. A verbatim copy of the current name, so a figure
              can be traced back to its document after the label changes.

manufacturer  only where the name follows the Okobaudat "Type - Company GmbH -
              Product" shape and the middle segment carries a recognised
              company suffix. Roughly 370 records. Anything less certain is
              left blank rather than guessed.

product_name  the remaining segment of those same dash-separated names.

material_name three routes, in order: a curated table of brand families that
              carry no material word and sit in the "Unknown" category (SGG
              glass, INSEE cement, the MU- mortars, the Vietnamese gypsum
              boards); then the name itself when it already reads as a
              material; then the assigned MaterialCategory. About 11 records
              are left blank and listed at the end of the run - they need a
              human to say what they are.

Nothing is overwritten: a field already set by an importer is left alone, so
this can be re-run safely and new imports take precedence.

    python manage.py backfill_epd_nomenclature --dry-run
    python manage.py backfill_epd_nomenclature
"""
import re
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.epd import EPD

# Legal-form suffixes that mark a segment as a company rather than a product.
COMPANY = re.compile(
    r"\b(GmbH|mbH|AG|Ltd|Limited|Pvt|Private|Inc|Corp|Corporation|PLC|Plc|Tbk|"
    r"S\.?A\.?|SpA|B\.?V\.?|N\.?V\.?|A/S|Oy|AB|Sdn\.?\s*Bhd|Co\.?,?\s*Ltd|KG|SE)\b"
)
DASH = re.compile(r"\s+[-–—]\s+")

# Words that mean the name already says what the product is, so the category
# would only add noise.
MATERIAL_WORD = re.compile(
    r"cement|concrete|steel|rebar|brick|block|glass|timber|wood|ply|insulat|gypsum|"
    r"board|mortar|tile|alumin|plaster|paint|coat|membrane|sand|aggregate|lime|"
    r"clinker|bars?\b|rod|sheet|plate|panel|pipe|roof|door|window|parquet|floor|wire|mesh|"
    r"stone|marble|granite|adobe|iron|wool|laminate|screed|bitumen|asphalt|mortar",
    re.I,
)

# Brand families that carry no material word and whose category is "Unknown",
# so neither automatic route can place them. Each entry is a case-insensitive
# prefix of the existing name -> (material, manufacturer or None). Identified by
# hand from the source EPDs; a blank manufacturer means the maker was not
# certain enough to record. Anything not listed here stays flagged rather than
# guessed - see the report at the end of the run.
MANUAL = [
    # --- glass, Saint-Gobain India ------------------------------------------
    ("SGG REFLECTASOL", "Reflective glass", "Saint-Gobain Glass India"),
    ("SGG Mirror",      "Mirror glass",     "Saint-Gobain Glass India"),
    ("SGG PARSOL",      "Tinted float glass", "Saint-Gobain Glass India"),
    ("SGG PLANILUX",    "Clear float glass", "Saint-Gobain Glass India"),
    ("SGG Planilux",    "Clear float glass", "Saint-Gobain Glass India"),
    ("PLANILAQUE",      "Lacquered glass",  "Saint-Gobain Glass India"),
    ("Colormaxx",       "Lacquered glass",  "Saint-Gobain Glass India"),
    ("ORA",             "Low-carbon float glass", "Saint-Gobain Glass India"),
    ("MIRA ",           "Mirror glass",     None),
    # --- cement and cementitious, Vietnam / Indonesia -----------------------
    ("INSEE",           "Cement",           "INSEE Vietnam"),
    ("MU-",             "Dry-mix mortar",   "PT Cipta Mortar Utama"),
    ("Webertai",        "Tile adhesive",    "Saint-Gobain Weber"),
    ("Keraflex",        "Tile adhesive",    "Mapei"),
    ("Mapelastic",      "Waterproofing membrane", "Mapei"),
    ("Penetron",        "Concrete waterproofing admixture", "Penetron"),
    ("Polycarboxylate Ether", "Concrete admixture", None),
    ("PFA stabilized soil block", "Stabilised soil block", None),
    ("PFA",             "Fly ash (PFA)",    None),
    ("Ground Granulated Blast Furnace Slag",
                        "Ground granulated blast furnace slag", None),
    ("PC Spun Piles",   "Precast concrete pile", None),
    ("Agrocrete",       "Agri-residue masonry block", "GreenJams"),
    # --- boards and partitions, Vietnam -------------------------------------
    ("FireShield",      "Gypsum board",     None),
    ("StandardShield",  "Gypsum board",     None),
    ("UltraLight",      "Gypsum board",     None),
    ("Ultra MoistShield", "Gypsum board",   None),
    ("Suprawall Track", "Steel framing track", None),
    ("Knauf India All Purpose Joint Compound", "Jointing compound", "Knauf India"),
    ("Knauf India EASYJOINT", "Jointing compound", "Knauf India"),
    ("Knauf India EASYPLUS",  "Jointing compound", "Knauf India"),
    # --- insulation ----------------------------------------------------------
    ("Straw bale",      "Straw bale insulation", None),
    ("Rockinsul",       "Stone wool insulation", None),
    # --- metals ---------------------------------------------------------------
    ("ERW Precision Tube", "Steel tube",    None),
    ("CEW Precision Tube", "Steel tube",    None),
    ("Ferro Chrome",    "Ferrochrome",      None),
    # --- finishes --------------------------------------------------------------
    ("Dr. Schutz",      "Floor coating",    "Dr. Schutz GmbH"),
    ("Pro Emulsion Interior", "Interior paint", None),
    ("White wash",      "Limewash",         None),
    # --- components ------------------------------------------------------------
    ("Schindler",       "Lift",             "Schindler"),
    ("Elastomeric Bearing", "Elastomeric bearing", None),
    ("TECHLINK",        "Geogrid",          None),
    ("NTOPCON",         "Solar PV module",  None),
    ("Engineered Quartz Slabs", "Engineered quartz slab", "ARL Infratech Limited"),
    # --- furniture --------------------------------------------------------------
    ("Desking", "Furniture", None), ("Deskpro", "Furniture", None),
    ("Seating", "Furniture", None), ("Storage", "Furniture", None),
    ("Modular Chairs", "Furniture", None), ("Healthcare Beds", "Furniture", None),
    ("Height Adjustable Table", "Furniture", None),
    ("Flexivate", "Furniture", None), ("Smart Locker", "Furniture", None),
    ("Influence Partition", "Office partition", None),
    ("Sleek Partition", "Office partition", None),
    ("Ikkita Chair", "Furniture", None), ("Mesa Dinning Table", "Furniture", None),
]


class Command(BaseCommand):
    help = "Fill the split EPD name fields from the existing name and category."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change and roll back.")

    def handle(self, *args, **opts):
        try:
            with transaction.atomic():
                self._run()
                if opts["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING("\nDry run - rolled back, nothing written."))
            return
        self.stdout.write(self.style.SUCCESS("\nDone."))

    def _run(self):
        stats = Counter()
        examples = {"mfr": [], "cat": [], "unchanged": []}
        to_update = []

        for e in EPD.objects.select_related("category").iterator(chunk_size=500):
            name = (e.name or "").strip()
            if not name:
                stats["skipped: no name"] += 1
                continue

            changed = False

            # --- original title, always ----------------------------------
            if not e.source_name:
                e.source_name = name[:255]
                changed = True

            # --- manufacturer and product, only when the shape is clear ---
            if not e.manufacturer:
                segments = [s.strip() for s in DASH.split(name) if s.strip()]
                if len(segments) >= 2:
                    company = next((s for s in segments if COMPANY.search(s)), None)
                    if company:
                        rest = [s for s in segments if s is not company]
                        e.manufacturer = company[:255]
                        if not e.product_name and rest:
                            # last remaining segment is the product, the first
                            # is usually the material class
                            e.product_name = rest[-1][:255]
                        if not e.material_name and rest:
                            e.material_name = rest[0][:255]
                        changed = True
                        stats["manufacturer parsed from name"] += 1
                        if len(examples["mfr"]) < 5:
                            examples["mfr"].append((name[:46], company[:30]))

            # --- material name ---------------------------------------------
            if not e.material_name:
                hit = next((m for m in MANUAL
                            if name.lower().startswith(m[0].lower())), None)
                if hit:
                    _, material, maker = hit
                    e.material_name = material
                    if not e.product_name:
                        e.product_name = name[:255]
                    if maker and not e.manufacturer:
                        e.manufacturer = maker
                    stats["material from the curated brand table"] += 1
                    to_update.append(e)
                    continue
                if MATERIAL_WORD.search(name):
                    e.material_name = name[:255]          # already descriptive
                    stats["material from the name itself"] += 1
                elif e.category and e.category.name_en and e.category.name_en != "Unknown":
                    e.material_name = e.category.name_en[:255]
                    if not e.product_name:
                        e.product_name = name[:255]       # the name was the brand
                    stats["material from category, name kept as product"] += 1
                    if len(examples["cat"]) < 6:
                        examples["cat"].append((name[:30], e.category.name_en[:34]))
                else:
                    stats["left as-is: no material word, no usable category"] += 1
                    if len(examples["unchanged"]) < 5:
                        examples["unchanged"].append(name[:48])
                    if changed:
                        to_update.append(e)
                    continue
                changed = True

            if changed:
                to_update.append(e)

        EPD.objects.bulk_update(
            to_update,
            ["material_name", "product_name", "manufacturer", "source_name"],
            batch_size=500,
        )

        self.stdout.write(f"records updated: {len(to_update)}\n")
        for k, v in stats.most_common():
            self.stdout.write(f"   {v:5d}  {k}")

        self.stdout.write("\n-- manufacturer parsed out of the name --")
        for n, m in examples["mfr"]:
            self.stdout.write(f"   {n:48s} -> {m}")
        self.stdout.write("\n-- brand-only names rescued by their category --")
        for n, c in examples["cat"]:
            self.stdout.write(f"   {n:32s} -> material: {c}")
        if examples["unchanged"]:
            self.stdout.write("\n-- needs a human: no material word and no usable category --")
            for n in examples["unchanged"]:
                self.stdout.write(f"   {n}")


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
