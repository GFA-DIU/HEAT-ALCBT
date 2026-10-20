"""Two importer faults that produced wrong carbon from a clean-looking import.

Both were found by running the importer against the real catalogue, not by
reading it.
"""
import pytest

from pages.views.building.import_building import (
    CROSS_COUNTRY, _efficiency_metric, _lookup_structural_epd,
)
from pages.models.building_operation.air_conditioning import EfficiencyMetric


# --- the efficiency metric -------------------------------------------------
#
# The template has ONE column headed "EER/ISEER/COP" and the importer never
# set efficiency_metric, so every imported air conditioner was stored as COP
# whatever the user had. All 351 air conditioners in production are on `cop`,
# which is the signature of that rather than of the stock.

@pytest.mark.parametrize("text,expected", [
    ("COP", "cop"), ("cop", "cop"),
    ("ISEER", "iseer"), ("CSPF", "cspf"), ("SEER", "seer"),
    ("EER", "eer"), ("EER Btu/h per W", "eer"),
    ("EER (W/W)", "eer_ww"), ("eer w/w", "eer_ww"),
    ("SEER Btu", "seer_btu"),
])
def test_the_metric_column_is_understood(text, expected):
    assert _efficiency_metric(text) == expected


@pytest.mark.parametrize("blank", ["", None, "   "])
def test_a_blank_metric_keeps_the_old_meaning(blank):
    """Every file that imported before this column existed must still import
    and still mean COP."""
    assert _efficiency_metric(blank) == "cop"


def test_an_unrecognised_metric_falls_back_rather_than_crashing(ical=None):
    assert _efficiency_metric("gibberish") == "cop"


def test_every_parsed_metric_is_a_real_model_choice():
    """A value the model rejects would fail the save with a validation error
    rather than a useful message."""
    valid = {v for v, _ in EfficiencyMetric.choices}
    for text in ("COP", "ISEER", "CSPF", "SEER", "EER", "EER (W/W)", "SEER Btu", ""):
        assert _efficiency_metric(text) in valid, text


def test_the_thai_case_that_motivated_this():
    """Thailand's EGAT No.5 label states EER in Btu/h per watt and its No.5
    threshold is >= 11.60. Stored as COP that machine looks 3.4 times more
    efficient than it is, so its energy comes out 3.4 times too low."""
    assert _efficiency_metric("EER") == "eer"
    assert _efficiency_metric("EER") != "cop"


# --- cross-country matching ------------------------------------------------

@pytest.mark.django_db
def test_a_cross_country_match_is_reported_not_hidden():
    """The catalogue carries localised GWP per country - steel rebar is India
    2.60 down to Thailand 2.37 - so matching another country's EPD uses the
    wrong factor. 37 of 100 plausible material names resolved across a border
    and every one of them imported silently."""
    epd, err = _lookup_structural_epd("Portland cement OPC 43", "India")
    if epd is None:
        pytest.skip("catalogue not loaded in this database")
    if epd.country and epd.country.name.lower() != "india":
        assert err is CROSS_COUNTRY, "a cross-border match must be reported"


@pytest.mark.django_db
def test_a_same_country_match_is_not_flagged():
    epd, err = _lookup_structural_epd("Sand", "Cambodia")
    if epd is None:
        pytest.skip("catalogue not loaded in this database")
    if epd.country and epd.country.name.lower() == "cambodia":
        assert err is None


def test_cross_country_is_a_warning_not_an_error_for_the_caller():
    """import_structural_components treats any error string as a failure. A
    sentinel that read as an error there would have rejected a third of every
    file instead of importing it with a note."""
    import inspect
    from pages.views.building import import_building as ib
    src = inspect.getsource(ib.import_structural_components)
    assert "cross_country = epd_error is CROSS_COUNTRY" in src
    assert "if epd_error and not cross_country:" in src
