"""Fill the manufacturer field on EPDs that have none, from a reviewed CSV.

Why this exists: 3,080 of BEAT's 3,620 manufacturer-specific EPDs carry no
manufacturer, so the material picker cannot find them by maker. The UltraTech
cement EPD (environdec epd5019) is in BEAT under four names, none of which
contains the word "UltraTech", which is how this surfaced.

The command deliberately does NOT work out who the maker is. It reads a CSV in
which every row already carries a manufacturer and the source it came from, so
the judgement is reviewable before it is written and auditable afterwards. A
maker inferred from a product name is indistinguishable from a sourced one once
saved, which is the same trap the BoQ density fallback fell into.

Two refusals, both deliberate:

  * a row with an empty manufacturer is skipped, never filled with a guess
  * an EPD that ALREADY has a manufacturer is never overwritten, even if the
    CSV disagrees. It is reported instead, so a real conflict is visible
    rather than silently resolved.

Dry run by default. Nothing is written without --apply.

    python manage.py backfill_epd_manufacturer --csv proposal.csv
    python manage.py backfill_epd_manufacturer --csv proposal.csv --apply
"""
import csv
import io

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pages.models.epd import EPD

REQUIRED = {"epd_id", "proposed_manufacturer", "sourced_from"}


class Command(BaseCommand):
    help = "Fill EPD.manufacturer from a reviewed CSV. Dry run unless --apply."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True,
                            help="Reviewed CSV: epd_id, proposed_manufacturer, "
                                 "sourced_from.")
        parser.add_argument("--apply", action="store_true",
                            help="Write the changes. Without this, nothing is saved.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after N rows (0 = all).")

    def handle(self, *args, **options):
        rows = list(csv.DictReader(
            io.open(options["csv"], encoding="utf-8-sig")))
        if not rows:
            raise CommandError("%s is empty" % options["csv"])
        missing = REQUIRED - set(rows[0])
        if missing:
            raise CommandError("CSV is missing column(s): %s"
                               % ", ".join(sorted(missing)))
        if options["limit"]:
            rows = rows[:options["limit"]]

        to_write = []
        to_rename = []
        no_source = conflicts = not_found = 0

        for r in rows:
            mfr = (r.get("proposed_manufacturer") or "").strip()
            if not mfr:
                no_source += 1
                continue
            epd = EPD.objects.filter(pk=r["epd_id"]).first()
            if epd is None:
                not_found += 1
                self.stderr.write("  not in this database: %s (%s)"
                                  % (r["epd_id"], r.get("name", "")))
                continue
            existing = (epd.manufacturer or "").strip()
            if existing:
                if existing != mfr:
                    conflicts += 1
                    self.stderr.write(
                        "  CONFLICT, left alone: %s has %r, CSV says %r"
                        % (epd.name[:48], existing, mfr))
                continue
            to_write.append((epd, mfr, r.get("sourced_from", "")))

        # Renames are opt-in per row and separate from the manufacturer fill:
        # a title is what people see in saved buildings and past exports, so it
        # moves only when the CSV explicitly asks for a different one.
        for r in rows:
            new_name = (r.get("proposed_name") or "").strip()
            if not new_name:
                continue
            epd = EPD.objects.filter(pk=r["epd_id"]).first()
            if epd is None:
                continue
            # material_name is what display_name actually composes from, so a
            # rename that moves only `name` never reaches the picker.
            if epd.name == new_name and (epd.material_name or "") == new_name:
                continue
            to_rename.append((epd, new_name))

        # Blast radius, before and after, as the project rules require.
        blank_before = EPD.objects.filter(manufacturer__isnull=True).count() \
            + EPD.objects.filter(manufacturer="").count()

        self.stdout.write("rows in CSV                 : %d" % len(rows))
        self.stdout.write("  no manufacturer given     : %d (skipped)" % no_source)
        self.stdout.write("  EPD not in this database  : %d" % not_found)
        self.stdout.write("  already set, left alone   : %d" % conflicts)
        self.stdout.write("  would be written          : %d" % len(to_write))
        self.stdout.write("  would be renamed          : %d" % len(to_rename))
        self.stdout.write("EPDs with no manufacturer now: %d" % blank_before)

        for epd, new_name in to_rename:
            self.stdout.write("    RENAME %-44s -> %s"
                              % (epd.name[:44], new_name))
        for epd, mfr, how in to_write[:15]:
            self.stdout.write("    %-50s -> %-36s [%s]"
                              % (epd.name[:50], mfr[:36], how[:30]))
        if len(to_write) > 15:
            self.stdout.write("    ... and %d more" % (len(to_write) - 15))

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "\nDRY RUN. Nothing written. Re-run with --apply to save."))
            return

        with transaction.atomic():
            for epd, mfr, _how in to_write:
                epd.manufacturer = mfr
                epd.save(update_fields=["manufacturer"])
            for epd, new_name in to_rename:
                # Keep the title the figure was published under, so the number
                # can still be traced back after the display name changes.
                original = epd.name
                fields = ["name"]
                if not (epd.source_name or "").strip():
                    epd.source_name = original
                    fields.append("source_name")
                # Move material_name as well, but ONLY where it was mirroring
                # the title. A material_name somebody split out by hand says
                # something the title does not, and is left alone.
                if (epd.material_name or "") in {original, epd.source_name or "", ""}:
                    epd.material_name = new_name
                    fields.append("material_name")
                epd.name = new_name
                epd.save(update_fields=fields)

        blank_after = EPD.objects.filter(manufacturer__isnull=True).count() \
            + EPD.objects.filter(manufacturer="").count()
        moved = blank_before - blank_after
        self.stdout.write(self.style.SUCCESS(
            "\nwrote %d manufacturer(s), renamed %d. EPDs with no manufacturer: "
            "%d -> %d (moved %d)."
            % (len(to_write), len(to_rename), blank_before, blank_after, moved)))
        if moved != len(to_write):
            self.stdout.write(self.style.ERROR(
                "Expected the blank count to fall by %d but it fell by %d. "
                "Check before trusting this run." % (len(to_write), moved)))
