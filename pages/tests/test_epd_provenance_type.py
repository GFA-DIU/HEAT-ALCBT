"""An EPD must not claim a provenance it does not have.

The picker's type filter offers "From a verified ILCD+EPD source", which means
the record came through an ILCD+EPD data node where a third party verified it.
Two groups carried that label without qualifying:

  99  EDGE / IFC-India handbook - a methodology report published as a PDF
   2  GFRG panels               - a peer-reviewed paper, and the pair disagreed
                                  with each other ('official' vs 'custom')

Both are now OFFICIAL_NON_STANDARD, "Official from non ILCD + EPD format".

The loader test matters most: import_edge_handbook_epds.py hard-coded
EPDType.OFFICIAL, so re-running it silently undid any manual correction. A data
fix without a loader fix lasts until the next import.
"""
import io
import re
from pathlib import Path

import pytest

from pages.models.epd import EPD, EPDType, MaterialCategory

pytestmark = pytest.mark.django_db

LOADER = Path("pages/scripts/csv_import/import_edge_handbook_epds.py")
EDGE_CSV = Path("pages/data/EDGE_HANDBOOK_EPDs.csv")

from pages.management.commands.retype_non_ilcd_epds import (  # noqa: E402
    EDGE_HANDBOOK_SOURCE, GFRG_PAPER_SOURCE)


def _epd(name, source, epd_type):
    return EPD.objects.create(
        names=[{"value": name, "lang": "en"}],
        type=epd_type, declared_amount=1,
        category=MaterialCategory.objects.first(),
        declared_unit="kg", conversions=[], source=source,
    )


# --- the loader ------------------------------------------------------------

def test_the_edge_loader_does_not_claim_ilcd_verification():
    """Without this the fix lasts until someone re-imports the handbook."""
    body = io.open(LOADER, encoding="utf-8").read()
    assigned = re.search(r"type=EPDType\.(\w+)", body)
    assert assigned, "the loader no longer sets a type"
    assert assigned.group(1) == "OFFICIAL_NON_STANDARD", (
        "the EDGE handbook is a PDF methodology report, not an ILCD+EPD node; "
        "it was assigned EPDType.%s" % assigned.group(1))


def test_the_loaders_source_column_still_matches_what_we_retype():
    """The command finds these records by source URL. If the CSV's URL ever
    changes, the command silently matches nothing - so tie them together."""
    header, first = io.open(EDGE_CSV, encoding="utf-8").read().splitlines()[:2]
    columns = header.split(";")
    source = first.split(";")[columns.index("source")]
    assert source == EDGE_HANDBOOK_SOURCE, (
        "the CSV's source URL and the retype command have drifted apart:\n"
        "  csv:     %s\n  command: %s" % (source, EDGE_HANDBOOK_SOURCE))


# --- the command -----------------------------------------------------------

def test_both_groups_are_retyped_whatever_they_started_as():
    edge = _epd("Fly ash", EDGE_HANDBOOK_SOURCE, EPDType.OFFICIAL)
    gfrg_a = _epd("GFRG panels (124 mm)", GFRG_PAPER_SOURCE, EPDType.OFFICIAL)
    gfrg_b = _epd("GFRG panels (174 mm)", GFRG_PAPER_SOURCE, EPDType.CUSTOM)

    from django.core.management import call_command
    call_command("retype_non_ilcd_epds", verbosity=0)

    for epd in (edge, gfrg_a, gfrg_b):
        epd.refresh_from_db()
        assert epd.type == EPDType.OFFICIAL_NON_STANDARD, epd.name


def test_a_genuine_ilcd_record_is_left_alone():
    """Scope is matched on source, never on name or category."""
    oeko = _epd(
        "Gypsum plaster",
        "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/x/processes/y",
        EPDType.OFFICIAL)
    environdec = _epd("Cement", "https://www.environdec.com/library/epd1418",
                      EPDType.OFFICIAL)

    from django.core.management import call_command
    call_command("retype_non_ilcd_epds", verbosity=0)

    for epd in (oeko, environdec):
        epd.refresh_from_db()
        assert epd.type == EPDType.OFFICIAL, epd.name


def test_the_grid_localized_records_stay_representative():
    """They are derived from the EDGE data by applying a country grid factor,
    so they are not the published figures. GENERIC is the honest label and the
    command must not sweep them up."""
    localized = _epd("Cement (India, localized)", "IFC-India (grid-localized)",
                     EPDType.GENERIC)

    from django.core.management import call_command
    call_command("retype_non_ilcd_epds", verbosity=0)

    localized.refresh_from_db()
    assert localized.type == EPDType.GENERIC


def test_running_it_twice_changes_nothing_the_second_time():
    _epd("Fly ash", EDGE_HANDBOOK_SOURCE, EPDType.OFFICIAL)
    from django.core.management import call_command

    call_command("retype_non_ilcd_epds", verbosity=0)
    before = list(EPD.objects.values_list("id", "type").order_by("id"))
    call_command("retype_non_ilcd_epds", verbosity=0)
    assert list(EPD.objects.values_list("id", "type").order_by("id")) == before


def test_the_source_url_is_never_rewritten():
    """The figure must keep pointing at where it came from."""
    edge = _epd("Fly ash", EDGE_HANDBOOK_SOURCE, EPDType.OFFICIAL)

    from django.core.management import call_command
    call_command("retype_non_ilcd_epds", verbosity=0)

    edge.refresh_from_db()
    assert edge.source == EDGE_HANDBOOK_SOURCE
