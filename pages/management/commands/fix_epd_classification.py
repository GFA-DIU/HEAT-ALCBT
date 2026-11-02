"""Fill a missing category or a missing declared amount, from a reviewed CSV.

Two separate holes, both of which make a material quietly contribute nothing
or sit in the wrong bar of every breakdown chart:

  * category "Unknown" - 139 records across the five ALCBT countries, 12 of
    them already used in real buildings. TMT Bars and GGBS were sitting in
    "Others".

  * declared_amount 0 - nine records whose GWP figures are fine but whose
    divisor is missing, so `get_gwp_impact_sum` returns None and the material
    contributes no carbon at all. The source datasets publish the zero
    themselves; BEAT imported a publisher's defect faithfully.

Like the manufacturer backfill, this command does NOT work out the answers.
It applies a CSV that a human has already reviewed, so the judgement is
checkable before it is written and auditable afterwards.

Three refusals:

  * a row with neither a category nor an amount is skipped
  * a record that already has a real category is never recategorised, only
    reported - a category somebody chose deliberately outranks a rule
  * a record whose declared_amount is already non-zero is never changed. That
    number is a divisor on every figure the record produces.

Dry run by default.

    python manage.py fix_epd_classification --csv proposal.csv
    python manage.py fix_epd_classification --csv proposal.csv --apply
"""
import csv
import io
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pages.models.epd import EPD, MaterialCategory

UNKNOWN = "unknown"


class Command(BaseCommand):
    help = ("Fill EPD.category and EPD.declared_amount from a reviewed CSV. "
            "Dry run unless --apply.")

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--recategorise-coarse", action="store_true",
            help="Also replace a category that is a top-level node rather "
                 "than a leaf. Off by default: a category somebody chose "
                 "deliberately outranks a rule, and only a vague one is "
                 "safe to overwrite.")

    def handle(self, *args, **options):
        rows = list(csv.DictReader(
            io.open(options["csv"], encoding="utf-8-sig")))
        if not rows:
            raise CommandError("%s is empty" % options["csv"])
        if "epd_id" not in rows[0]:
            raise CommandError("CSV has no epd_id column")

        cats = {}
        recategorise, reamount = [], []
        skipped = already_set = not_found = bad_category = 0

        for r in rows:
            epd = EPD.objects.filter(pk=r["epd_id"]).select_related(
                "category").first()
            if epd is None:
                not_found += 1
                continue

            cid = (r.get("proposed_category_id") or "").strip()
            amount = (r.get("proposed_declared_amount") or "").strip()
            if not cid and not amount:
                skipped += 1
                continue

            if cid:
                current = (epd.category.name_en.strip().lower()
                           if epd.category else "")
                # A top-level node such as "Coverings" or "Mineral building
                # products" says almost nothing: the record cannot be found
                # by browsing and its carbon lands in a vague bar on every
                # breakdown chart. With the flag set, those count as fillable
                # alongside "Unknown". A real leaf never does.
                coarse = (epd.category is not None
                          and epd.category.level is not None
                          and epd.category.level <= 1
                          and options["recategorise_coarse"])
                if (epd.category is not None and current != UNKNOWN
                        and not coarse):
                    already_set += 1
                    self.stderr.write(
                        "  has a category already, left alone: %s is %r"
                        % (epd.name[:44], str(epd.category)))
                else:
                    if cid not in cats:
                        found = MaterialCategory.objects.filter(
                            category_id=cid).first()
                        if found is None:
                            bad_category += 1
                            self.stderr.write(
                                "  no such category %r for %s"
                                % (cid, epd.name[:44]))
                            cats[cid] = None
                        else:
                            cats[cid] = found
                    if cats[cid] is not None:
                        recategorise.append((epd, cats[cid]))

            if amount:
                try:
                    value = Decimal(amount)
                except (InvalidOperation, ValueError):
                    self.stderr.write("  %r is not a number for %s"
                                      % (amount, epd.name[:44]))
                    continue
                if value <= 0:
                    self.stderr.write("  refusing amount %s for %s"
                                      % (value, epd.name[:44]))
                    continue
                if epd.declared_amount and epd.declared_amount != 0:
                    already_set += 1
                    self.stderr.write(
                        "  declared_amount already %s, left alone: %s"
                        % (epd.declared_amount, epd.name[:44]))
                else:
                    reamount.append((epd, value))

        unknown_before = EPD.objects.filter(
            category__name_en__iexact="Unknown").count()
        zero_before = EPD.objects.filter(declared_amount=0).count()

        self.stdout.write("rows in CSV                 : %d" % len(rows))
        self.stdout.write("  nothing proposed          : %d" % skipped)
        self.stdout.write("  EPD not in this database  : %d" % not_found)
        self.stdout.write("  already set, left alone   : %d" % already_set)
        self.stdout.write("  category id not found     : %d" % bad_category)
        self.stdout.write("  would be recategorised    : %d" % len(recategorise))
        self.stdout.write("  would get a declared amount: %d" % len(reamount))
        self.stdout.write('EPDs filed "Unknown" now    : %d' % unknown_before)
        self.stdout.write("EPDs with amount 0 now      : %d" % zero_before)

        for epd, cat in recategorise[:12]:
            self.stdout.write("    %-46s -> %s" % (epd.name[:46], cat.name_en))
        if len(recategorise) > 12:
            self.stdout.write("    ... and %d more" % (len(recategorise) - 12))
        for epd, value in reamount:
            self.stdout.write("    AMOUNT %-42s 0 -> %s %s"
                              % (epd.name[:42], value, epd.declared_unit))

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "\nDRY RUN. Nothing written. Re-run with --apply to save."))
            return

        with transaction.atomic():
            for epd, cat in recategorise:
                epd.category = cat
                epd.save(update_fields=["category"])
            for epd, value in reamount:
                epd.declared_amount = value
                epd.save(update_fields=["declared_amount"])

        unknown_after = EPD.objects.filter(
            category__name_en__iexact="Unknown").count()
        zero_after = EPD.objects.filter(declared_amount=0).count()
        self.stdout.write(self.style.SUCCESS(
            '\nrecategorised %d, amounts set %d. "Unknown": %d -> %d. '
            "amount 0: %d -> %d."
            % (len(recategorise), len(reamount), unknown_before,
               unknown_after, zero_before, zero_after)))

        moved = unknown_before - unknown_after
        if moved != len(recategorise):
            self.stdout.write(self.style.ERROR(
                'Expected "Unknown" to fall by %d but it fell by %d. Check '
                "before trusting this run." % (len(recategorise), moved)))
