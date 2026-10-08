"""Strip the workaround whitespace from EPD names.

Why the spaces are there
------------------------
EPD uniqueness used to be keyed on (UUID, name). 966 generic EPDs carry a
placeholder UUID - two distinct values across all of them - so for those rows
the rule collapsed to "unique on name", with no country. The same material
therefore could not exist for two countries, and the workaround was a trailing
space:

    "Steel reinforcement (steel rebar) "   India
    "Steel reinforcement (steel rebar)"    Cambodia

Any lookup by name then picked whichever row it met first. That is how an
import resolved 1,398 rebar lines to India's factor (2.60) rather than
Cambodia's (2.4247), and how an `Aluminum ingot` record carrying no density
conversion was silently valued at zero.

Migration 0055 adds country to the uniqueness key, so the workaround is no
longer needed and the names can be made honest.

Safety
------
- Materials reference EPDs by id, so this is a display change. Nothing
  re-points, and the ~7,300 materials on affected records keep their EPD.
- No stray-space row has a trimmed twin in its own country, so nothing merges.
- One genuine clash exists and is renamed rather than merged: India has two
  different materials both called "Cement mortar", a GFA-HEAT generic declared
  per m3 (236 uses) and an IFC-India record declared per kg (91 uses). The
  latter is given a qualified name so both survive.

    python manage.py normalise_epd_names --dry-run
    python manage.py normalise_epd_names
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, F
from django.db.models.functions import Trim

from pages.models.epd import EPD

# (current name, country name, new name) - applied before trimming so the two
# India "Cement mortar" records do not collide once the spaces are gone.
MANUAL_RENAMES = [
    ("Cement mortar ", "India", "Cement mortar (IFC India, per kg)"),
]


class Command(BaseCommand):
    help = "Trim whitespace from EPD names left over from the old uniqueness rule."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change and roll back.")

    def handle(self, *args, **opts):
        try:
            with transaction.atomic():
                self._run()
                if opts["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                "\nDry run - rolled back, nothing written."))
            return
        self.stdout.write(self.style.SUCCESS("\nDone."))

    def _run(self):
        untidy = EPD.objects.exclude(name=Trim("name"))
        total = untidy.count()
        self.stdout.write(f"EPDs with leading/trailing whitespace: {total}")

        by_country = (untidy.values("country__name")
                      .order_by("country__name").annotate(n=Count("id")))
        for row in by_country:
            self.stdout.write(f"    {row['country__name'] or '(none)':12s} {row['n']}")

        # --- resolve genuine same-country clashes first ---------------------
        for old_name, country, new_name in MANUAL_RENAMES:
            qs = EPD.objects.filter(name=old_name, country__name=country)
            n = qs.count()
            if n:
                used = sum(e.structuralproduct_set.count() for e in qs)
                qs.update(name=new_name)
                self.stdout.write(
                    f'\n  renamed {n} record(s) "{old_name.strip()}" ({country}) '
                    f'-> "{new_name}"  [{used} materials keep pointing at it]')

        # --- trim the rest ---------------------------------------------------
        remaining = EPD.objects.exclude(name=Trim("name"))
        affected_materials = sum(
            e.structuralproduct_set.count()
            for e in remaining.only("id").prefetch_related("structuralproduct_set")
        )
        trimmed = remaining.update(name=Trim(F("name")))
        self.stdout.write(
            f"\n  trimmed {trimmed} name(s); {affected_materials} materials unaffected "
            f"(they reference the EPD by id)")

        # --- prove the result -------------------------------------------------
        left = EPD.objects.exclude(name=Trim("name")).count()
        dupes = (EPD.objects.values("UUID", "name", "country")
                 .annotate(n=Count("id"))
                 .filter(n__gt=1).count())
        self.stdout.write(f"\n  remaining untidy names: {left}")
        self.stdout.write(f"  (UUID, name, country) collisions: {dupes}")
        if left or dupes:
            raise RuntimeError(
                "normalisation left the table inconsistent - rolling back")


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
