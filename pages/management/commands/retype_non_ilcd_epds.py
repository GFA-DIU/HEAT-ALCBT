"""Stop EPDs that are not ILCD+EPD from claiming they are.

The picker's EPD Type filter offers "From a verified ILCD+EPD source". That
label means the record came through an ILCD+EPD data node - an ECO Platform
member or EPD International - where a third party verified it and published it
in a machine-readable format. Two groups were carrying that label without
qualifying for it:

1. 99 records from the EDGE / IFC-India Construction Materials Database.
   That is a methodology report published as a PDF by IFC, not an EPD
   programme. The figures are usable and sourced, but nobody verified them as
   an EPD. `import_edge_handbook_epds.py` hard-coded EPDType.OFFICIAL, so the
   label returned on every re-import; that loader is corrected in the same
   commit as this command.

2. The two Glass Fiber Reinforced Gypsum (GFRG) panel records.
   Their source is a peer-reviewed journal paper, not an EPD programme at all.
   They also disagreed with each other - one was 'official', the other
   'custom' - so the same material claimed two different provenances.

Both move to EPDType.OFFICIAL_NON_STANDARD, "Official from non ILCD + EPD
format": the figures are from a named, citable source, just not in the ILCD+EPD
format and not third-party verified as an EPD. The `source` field is not
touched, so every record keeps pointing at exactly where its number came from.

Deliberately NOT changed: the 392 "IFC-India (grid-localized)" records. Those
are derived from the same EDGE data by applying a country grid factor, so they
are not the published figures. They stay EPDType.GENERIC, "Representative EPD
for a country", which is the honest label for a derived number.

Also not changed: manufacturer EPD PDFs (AENOR, Vetrotech, Armstrong and
similar). Those ARE third-party verified under EN 15804; they are simply
published as a PDF rather than through a data node. Re-labelling them is a
separate decision and is not taken here.

Idempotent - a second run reports zero to change.

    python manage.py retype_non_ilcd_epds --dry-run
    python manage.py retype_non_ilcd_epds
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.epd import EPD, EPDType

# Matched on `source`, which is the only field that records where a figure came
# from. Matching on name would catch records that merely mention the material.
EDGE_HANDBOOK_SOURCE = (
    "https://edgebuildings.com/wp-content/uploads/2022/04/"
    "IFC-India-Construction-Materials-Database-Methodology-Report.pdf"
)
GFRG_PAPER_SOURCE = (
    "https://www.sciencedirect.com/science/article/abs/pii/S0378778819339854"
)

GROUPS = [
    ("EDGE / IFC-India handbook", {"source": EDGE_HANDBOOK_SOURCE}),
    ("GFRG panels (journal paper)", {"source": GFRG_PAPER_SOURCE}),
]


class Command(BaseCommand):
    help = "Retype EDGE and GFRG EPDs as 'Official from non ILCD + EPD format'."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change and write nothing.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        total = 0

        for label, lookup in GROUPS:
            qs = EPD.objects.filter(**lookup)
            found = qs.count()
            stale = qs.exclude(type=EPDType.OFFICIAL_NON_STANDARD)
            to_change = stale.count()

            was = sorted({t for t in stale.values_list("type", flat=True)})
            self.stdout.write(
                "%-32s %4d found, %4d to change%s"
                % (label, found, to_change,
                   (" (was: %s)" % ", ".join(was)) if was else ""))

            if found == 0:
                self.stdout.write(self.style.WARNING(
                    "  nothing matched - has the source URL changed?"))

            if to_change and not dry:
                with transaction.atomic():
                    stale.update(type=EPDType.OFFICIAL_NON_STANDARD)
            total += to_change

        if dry:
            self.stdout.write(self.style.WARNING(
                "\nDry run: %d records would change, nothing written." % total))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n%d records retyped as '%s'."
                % (total, EPDType.OFFICIAL_NON_STANDARD.label)))

        # State the result against the whole library, so a partial run is visible.
        remaining = EPD.objects.filter(
            type=EPDType.OFFICIAL, source__in=[EDGE_HANDBOOK_SOURCE, GFRG_PAPER_SOURCE]
        ).count()
        if remaining:
            self.stdout.write(self.style.ERROR(
                "%d of these records still claim a verified ILCD+EPD source."
                % remaining))
