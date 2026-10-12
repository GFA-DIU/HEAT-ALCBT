"""Move EPDs off top-level category nodes onto a real leaf.

Why
---
A category is only ever used for filtering and for the material picker tree -
it does not enter any carbon calculation. But since the nomenclature backfill
it also supplies `material_name` for records whose own name carries no material
word, and a record parked on a top-level node then produces a label like
"Coverings - Jotamastic 85" instead of "Protective coating for metal".

Of 2,559 ALCBT EPDs, 1,543 sit on a top-level node rather than a leaf. Most are
harmless: their names already read as a material, so the backfill never
consulted the category. This command fixes only the two sets where it actually
shows:

  156  records whose material_name came out as a bare top-level word
  191  Holcim ready-mix concrete filed under 1.1.01 "Cement" - a genuinely
       wrong leaf, which is why a search for "cement" returned concrete

Nothing here changes a GWP figure, a declared unit or a quantity. The only
observable effects are the label, the picker tree and search.

Anything the table does not cover is reported, not guessed - the brass
fittings and valves have no sensible leaf in this tree, so they stay where
they are and are listed at the end.

    python manage.py recategorise_epds --dry-run
    python manage.py recategorise_epds
"""
import re
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.epd import EPD, MaterialCategory

# (regex on the EPD name, target leaf category_id, why)
# Order matters - the first match wins, so the specific patterns come first.
RULES = [
    # --- protective coatings for steel: Jotun's marine/industrial range ------
    (r"jotamastic|hardtop|penguard|tankguard|anti.?corrosion|rust preventive",
     "5.6.04", "protective coating for metal"),
    # --- primers --------------------------------------------------------------
    (r"\bprimer\b", "5.1.01", "primer"),
    # --- facade / exterior masonry paint ---------------------------------------
    (r"jotashield|jotun facade|jotun super durable|jotun durasol|jotatough|"
     r"\bfacade\b|weatherguard|exterior",
     "5.4.01", "facade paint"),
    # --- interior paint and emulsions -------------------------------------------
    (r"fenomastic|majestic|interior|emulsion|\bmatt\b|semigloss|\bsheen\b",
     "5.5.02", "interior paint"),
    (r"bitumin", "5.3.01", "bituminous paint"),
    # --- boards -----------------------------------------------------------------
    (r"gyproc|plasterboard|gypsum board", "1.3.13", "gypsum plasterboard"),
    # --- light-gauge steel framing for drywall ------------------------------------
    (r"metal framing|metal profiles|ultraframe", "4.1.03", "steel framing profile"),
    # --- renders, grouts, concrete -------------------------------------------------
    (r"polymeric render|\brender\b", "1.4.04", "render"),
    (r"non.?shrink grout|\bgrout\b", "1.4.02", "grout / masonry mortar"),
    (r"^bua\.|lean concrete|\blean\b", "1.4.01", "ready-mixed concrete"),
    (r"precast .*(lintel|fence)", "1.3.05", "precast concrete element"),
    # --- electrical conduit ----------------------------------------------------------
    (r"electrical and communication conduit", "8.8.01", "cable / duct conduit"),
    # --- insulation ---------------------------------------------------------------------
    (r"cellulose fiber|cellulose fibre", "2.11.01", "cellulose insulation"),
]

# The 191 German Holcim ready-mix records filed as Cement. Matched separately
# because the fix is keyed on the current (wrong) category, not on the name.
HOLCIM_FROM, HOLCIM_TO = "1.1.01", "1.4.01"
HOLCIM_NAME = re.compile(r"^beton\b", re.I)

VAGUE = [
    "Coverings", "Mineral building products", "Insulation materials", "Plastics",
    "Metals", "Building service engineering", "Wood", "Others", "Composites",
    "Components for windows and curtain walls", "Unknown",
]


class Command(BaseCommand):
    help = "Re-file EPDs parked on a top-level category onto a proper leaf."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would move and roll back.")

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

    def _resolve(self):
        """category_id -> MaterialCategory, failing loudly on a typo in RULES."""
        wanted = {cid for _, cid, _ in RULES} | {HOLCIM_TO}
        found = {c.category_id: c for c in
                 MaterialCategory.objects.filter(category_id__in=wanted)}
        missing = wanted - set(found)
        if missing:
            raise RuntimeError("RULES reference categories that do not exist: %s"
                               % ", ".join(sorted(missing)))
        return found

    def _run(self):
        cats = self._resolve()
        moved = Counter()
        unmatched = []

        # --- 1. the records whose label came out as a bare top-level word -----
        vague = EPD.objects.filter(material_name__in=VAGUE).select_related("category")
        self.stdout.write("records with a vague label: %d" % vague.count())
        for e in vague:
            name = e.name or ""
            hit = next(((cid, why) for rx, cid, why in RULES
                        if re.search(rx, name, re.I)), None)
            if not hit:
                unmatched.append((e.material_name, name))
                continue
            cid, why = hit
            target = cats[cid]
            e.category = target
            # the label is derived from the category, so refresh it too
            e.material_name = target.name_en
            e.save(update_fields=["category", "material_name"])
            moved["%s  (%s)" % (cid, why)] += 1

        # --- 2. Holcim ready-mix filed as Cement --------------------------------
        holcim = [e for e in EPD.objects.filter(category__category_id=HOLCIM_FROM)
                  if HOLCIM_NAME.match((e.name or "").strip())]
        for e in holcim:
            e.category = cats[HOLCIM_TO]
            if e.material_name == "Cement":
                e.material_name = cats[HOLCIM_TO].name_en
            e.save(update_fields=["category", "material_name"])
        self.stdout.write("\nHolcim ready-mix moved %s -> %s: %d records"
                          % (HOLCIM_FROM, HOLCIM_TO, len(holcim)))

        self.stdout.write("\nre-filed by rule:")
        for k, v in moved.most_common():
            self.stdout.write("   %4d  %s" % (v, k))

        if unmatched:
            self.stdout.write("\nleft where they are - no sensible leaf in this tree:")
            for label, name in unmatched[:40]:
                self.stdout.write("   [%s] %s" % (label[:22], name[:60]))
            self.stdout.write("   ... %d total" % len(unmatched))


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
