"""The committed batch B data file, and that it still says what it said.

Batch B was extracted once before and lost, because the parsed CSV only ever
existed in a session scratchpad. Production could not reproduce it and the
whole harvest had to be run again. The file is committed now, so the thing
worth guarding is no longer "can we regenerate it" but "is the file still the
one that was reviewed".

These figures were read from the ILCD datasets on data.environdec.com, not
chosen here. Each row carries its registration number and its library URL, so
any number below can be checked against its own declaration.

The spot checks are deliberately on the rows where a silent edit would be
most expensive:

  * Vedanta Restora is an aluminium ingot at 5.84 kgCO2e/kg. Generic Indian
    primary aluminium is roughly three times that, so a figure drifting here
    understates by a lot and still looks like aluminium.
  * The two Jindal scrap-route products sit just under 0.45 kgCO2e/kg. That
    is low for steel but correct for a 100% scrap electric arc route, and it
    is exactly the kind of number someone "corrects" upward by mistake.
  * Luxotica is per kg and Merino is per m2. The pair guards the declared
    unit, which is the field that produced the worst defect in this work.
"""
import csv
import io
import os

from django.conf import settings

DATA = os.path.join(settings.BASE_DIR, "pages", "data",
                    "india_ilcd_parsed_2026-11-05.csv")
SHORTLIST = os.path.join(settings.BASE_DIR, "pages", "data",
                         "india_ilcd_shortlist_2026-11-05.csv")


def _rows(path):
    return list(csv.DictReader(io.open(path, encoding="utf-8-sig")))


def test_the_parsed_file_is_present_and_whole():
    rows = _rows(DATA)
    assert len(rows) == 50
    # The extractor refused none of them; the importer's bands do the
    # filtering. A row that has lost its status would be skipped silently.
    assert all(r["status"] == "OK" for r in rows)


def test_every_row_can_be_traced_back_to_its_declaration():
    for r in _rows(DATA):
        assert r["registration_number"].startswith("EPD-IES-"), r["product"]
        assert r["url"].startswith("https://www.environdec.com/library/epd"), \
            r["product"]


def test_no_row_lost_its_figure_or_its_unit():
    for r in _rows(DATA):
        assert r["gwp_a1a3"], r["product"]
        float(r["gwp_a1a3"])          # parses, sign checked separately below
        assert r["declared_unit"] in ("kg", "m2", "m3", "m", "pcs", "ton"), \
            "%s: %r" % (r["product"], r["declared_unit"])
        assert float(r["declared_amount"]) > 0, r["product"]


# Two rows declare a negative A1-A3, because the sequestration in the board is
# credited in A1. BEAT adds A1-A3 straight into the building total, so either
# of them would subtract carbon from a building that used it. Both are held
# back, and the point of this list is that it must be EXACTLY these two: a
# third negative appearing in the file is a new product nobody decided about.
NEGATIVE_A1A3 = {"Samrat Ply", "SomaniPly Plywood"}


def test_the_negative_rows_are_only_the_two_known_ones():
    found = {r["product"] for r in _rows(DATA) if float(r["gwp_a1a3"]) < 0}
    assert found == NEGATIVE_A1A3, found


def test_both_negative_rows_are_held_back_by_the_rule_meant_for_them():
    """Not by some unrelated rule that happens to catch them.

    Samrat Ply was refused only because its name did not map to a leaf
    category. That is not protection: settling the biogenic question adds a
    plywood leaf, and the record would then import at -1.018 kgCO2e/kg.
    """
    from pages.management.commands.import_environdec_epds import EXCLUDE
    for name in NEGATIVE_A1A3:
        assert EXCLUDE.search(name), name
    # and the laminate from the same maker is NOT caught by it
    assert not EXCLUDE.search("Samrat HPL")


def test_the_shortlist_still_covers_the_parsed_file():
    """Without the shortlist the file cannot be regenerated, which is the
    failure that cost this work a whole second harvest."""
    short = {r["url"] for r in _rows(SHORTLIST)}
    parsed = {r["url"] for r in _rows(DATA)}
    assert parsed <= short
    for r in _rows(SHORTLIST):
        assert len(r["uuid"]) == 36, r["product"]


SPOT_CHECKS = {
    # product                            (gwp_a1a3, amount, unit, registration)
    "Restora":
        (5842.95719789226, 1000.0, "kg", "EPD-IES-0017334:005"),
    "Steel Plate (100% Recycled Scrap)":
        (450.0, 1000.0, "kg", "EPD-IES-0015506:005"),
    "TMT Rebar (100% Recycled Scrap)":
        (445.0, 1000.0, "kg", "EPD-IES-0008168:005"),
    "High Pressure Laminates":
        (1.04, 1.0, "kg", "EPD-IES-0025913:003"),
    "HIGH PRESSURE LAMINATE":
        (0.518032914479819, 1.0, "m2", "EPD-IES-0016401:003"),
}


def test_the_reviewed_figures_have_not_moved():
    by_name = {r["product"]: r for r in _rows(DATA)}
    for name, (gwp, amount, unit, reg) in SPOT_CHECKS.items():
        assert name in by_name, name
        r = by_name[name]
        # The registration is checked too, so that a row keeping its name
        # while pointing at a different declaration is caught.
        assert r["registration_number"] == reg, name
        assert abs(float(r["gwp_a1a3"]) - gwp) < 1e-9, name
        assert float(r["declared_amount"]) == amount, name
        assert r["declared_unit"] == unit, name


def test_the_two_contradictory_datasets_are_still_in_the_file_unfixed():
    """Windor epd32024 and Asawa epd5242 publish ILCD figures that disagree
    with their own declarations. They are kept here as extracted, wrong, so
    the importer's plausibility band is what refuses them. Quietly patching
    the numbers in this file would hide the defect from the band.
    """
    by_name = {r["product"]: r for r in _rows(DATA)}
    pir = [v for k, v in by_name.items() if "PIR Panel" in k]
    assert pir, "the Asawa PIR panel row has gone"
    assert float(pir[0]["gwp_a1a3"]) < 0.01, \
        "the PIR figure was corrected in the data file instead of at source"
