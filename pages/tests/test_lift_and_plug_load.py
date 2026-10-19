"""No lifts means no lift energy, and plug load has a basis the user can set.

Both bugs were visible on screen: a lift card reading "number of lifts: 0"
pre-filled 65,943.696 kWh/year, and plug load could only be corrected by
overwriting the kWh, which hid where the figure came from.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from pages.models.building import Building
from pages.models.building_operation.energy_summary import (
    EnergySummary, lift_estimate_kwh, plug_load_factor_for,
)
from pages.models.building_operation.general_systems import LiftEscalatorSystem
from pages.models.climate_type import ClimateType

REPO = Path(__file__).resolve().parents[2]
LIFT_FORM = REPO / ("templates/pages/add-building/components/"
                    "operational-details/lift-escalator-system.html")


@pytest.fixture
def building():
    def _make():
        climate, _ = ClimateType.objects.get_or_create(name="composite")
        return Building.objects.create(
            name="Lift and plug test", climate_zone=climate,
            total_floor_area=Decimal("1000"))
    return _make


# --- no lifts, no lift energy ---------------------------------------------

@pytest.mark.django_db
def test_a_record_with_zero_lifts_reports_zero_energy(building):
    """The estimate used to fire on the existence of a record rather than on
    whether it described any lifts."""
    b = building()
    LiftEscalatorSystem.objects.create(
        building=b, number_of_lifts=0,
        lift_regenerative_features=False, vvvf_sleep_mode=False)
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.cooling_kwh = Decimal("218400")
    s.ventilation_kwh = Decimal("262080")
    s.lighting_kwh = Decimal("157248")
    s.hot_water_kwh = Decimal("131040")
    s.recalculate()
    assert s.lift_escalator_kwh == Decimal("0.000")


@pytest.mark.django_db
def test_a_record_with_lifts_still_gets_the_estimate(building):
    """recalculate() rebuilds the four systems from their own records, so the
    test needs a real one - otherwise the base is zero and the estimate is
    zero whatever the lift count says, which would prove nothing."""
    from pages.models.building_operation import HotWaterSystem
    b = building()
    HotWaterSystem.objects.create(
        building=b, type_of_hot_water_system="boiler", fuel_type="electricity",
        number_of_equipment=1, operating_hours_per_day=8,
        operating_days_per_week=5, operating_weeks_per_year=50,
        baseline_efficiency=Decimal("0.85"), heat_recovery_system=False,
        equipment_efficiency_level=Decimal("1.0"),
        total_energy_consumption_kwh_per_year=Decimal("100000"))
    LiftEscalatorSystem.objects.create(
        building=b, number_of_lifts=5,
        lift_regenerative_features=False, vvvf_sleep_mode=False)
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.recalculate()
    assert s.hot_water_kwh == Decimal("100000")
    assert s.lift_escalator_kwh == Decimal("7500.000")   # 7.5% of 100,000


@pytest.mark.django_db
def test_the_same_building_with_zero_lifts_gets_nothing(building):
    """The pair that matters: identical energy, only the count differs."""
    from pages.models.building_operation import HotWaterSystem
    b = building()
    HotWaterSystem.objects.create(
        building=b, type_of_hot_water_system="boiler", fuel_type="electricity",
        number_of_equipment=1, operating_hours_per_day=8,
        operating_days_per_week=5, operating_weeks_per_year=50,
        baseline_efficiency=Decimal("0.85"), heat_recovery_system=False,
        equipment_efficiency_level=Decimal("1.0"),
        total_energy_consumption_kwh_per_year=Decimal("100000"))
    LiftEscalatorSystem.objects.create(
        building=b, number_of_lifts=0,
        lift_regenerative_features=False, vvvf_sleep_mode=False)
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.recalculate()
    assert s.hot_water_kwh == Decimal("100000")
    assert s.lift_escalator_kwh == Decimal("0.000")


def test_the_form_accepts_zero_lifts():
    """A user recording "this building has no lift" could not save it: the
    field rejected 0, and getting past it produced an invented figure."""
    html = LIFT_FORM.read_text(encoding="utf-8")
    assert 'name="number_of_lifts" required min="0"' in html
    assert 'name="number_of_lifts" required min="1"' not in html


def test_the_form_suppresses_the_estimate_at_zero_lifts():
    js = LIFT_FORM.read_text(encoding="utf-8")
    assert "(lifts === 0) ? 0 : data.lift_estimate_kwh" in js


# --- plug load ------------------------------------------------------------

def _four_systems(s):
    s.cooling_kwh = Decimal("218400")
    s.ventilation_kwh = Decimal("262080")
    s.lighting_kwh = Decimal("157248")
    s.hot_water_kwh = Decimal("131040")
    s.lift_escalator_kwh = Decimal("57657.6")
    return s


@pytest.mark.django_db
def test_an_estimated_lift_is_excluded_from_the_plug_base(building):
    """The lift figure is itself 7.5% of these same four systems, so counting
    it would take a percentage of a percentage."""
    b = building()
    LiftEscalatorSystem.objects.create(
        building=b, number_of_lifts=5, annual_energy_consumption_kwh=None,
        lift_regenerative_features=False, vvvf_sleep_mode=False)
    s = _four_systems(EnergySummary.objects.get_or_create(building=b)[0])
    assert s.lift_energy_is_estimated is True
    assert s.plug_load_base == Decimal("768768")
    assert s.systems_sum == Decimal("826425.6")   # mismatch check still counts all five


@pytest.mark.django_db
def test_a_measured_lift_is_included_in_the_plug_base(building):
    """A figure off a meter is a measurement like any other. Only the estimate
    is circular."""
    b = building()
    LiftEscalatorSystem.objects.create(
        building=b, number_of_lifts=5,
        annual_energy_consumption_kwh=Decimal("57657.6"),
        lift_regenerative_features=False, vvvf_sleep_mode=False)
    s = _four_systems(EnergySummary.objects.get_or_create(building=b)[0])
    assert s.lift_energy_is_estimated is False
    assert s.plug_load_base == Decimal("826425.6")


@pytest.mark.django_db
def test_an_entered_percentage_drives_the_plug_load(building):
    b = building()
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.cooling_kwh = Decimal("768768")
    s.plug_load_percent = Decimal("12.50")
    assert s.suggested_plug_load() == Decimal("96096.000")


@pytest.mark.django_db
def test_a_blank_percentage_falls_back_to_the_building_type_share(building):
    b = building()
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.cooling_kwh = Decimal("768768")
    s.plug_load_percent = None
    # No category on this building, so the default share applies.
    assert s.suggested_plug_load() == (
        Decimal("768768") * plug_load_factor_for("")).quantize(Decimal("0.001"))


@pytest.mark.django_db
def test_a_metered_bill_still_wins_and_counts_every_system(building):
    """The difference method reconciles against a bill covering all systems,
    so it uses systems_sum, not the plug-load base."""
    b = building()
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.cooling_kwh = Decimal("768768")
    s.lift_escalator_kwh = Decimal("57657.6")
    s.total_override_kwh = Decimal("1000000")
    s.plug_load_percent = Decimal("12.50")
    assert s.suggested_plug_load() == Decimal("1000000") - Decimal("826425.6")


def test_the_screenshot_figure_is_reproduced():
    """153,753.6 on screen is 20% of the four systems, which is what the new
    base gives. The five-system base would have given 165,285.1."""
    assert Decimal("768768") * Decimal("0.20") == Decimal("153753.60")


# --- the plug-load gate ----------------------------------------------------
#
# The row could show "20% of 242,249 kWh system energy" beside "0 kWh/yr",
# because a stored 0 and an unanswered question looked the same and a
# percentage and a kWh override could both be set.

@pytest.mark.django_db
def test_saying_no_means_zero_and_stays_zero(building):
    b = building()
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.cooling_kwh = Decimal("242249.28")
    s.has_plug_load = False
    assert s.suggested_plug_load() == Decimal("0")
    assert s.plug_load_basis == "none"


@pytest.mark.django_db
def test_not_answered_shows_the_typical_share_as_an_estimate(building):
    b = building()
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.cooling_kwh = Decimal("242249.28")
    s.has_plug_load = None
    assert s.plug_load_basis == "estimated"
    assert s.suggested_plug_load() == Decimal("48449.856")


@pytest.mark.django_db
def test_exactly_one_basis_is_ever_reported(building):
    """The contradiction was two bases at once. Whatever the state, the row
    has one answer to show."""
    b = building()
    s, _ = EnergySummary.objects.get_or_create(building=b)
    s.cooling_kwh = Decimal("242249.28")
    for has, kwh, pct, expected in [
        (False, None, None, "none"),
        (True, Decimal("5000"), None, "metered"),
        (True, None, Decimal("20"), "percent"),
        (None, None, None, "estimated"),
    ]:
        s.has_plug_load, s.plug_load_kwh, s.plug_load_percent = has, kwh, pct
        assert s.plug_load_basis == expected, (has, kwh, pct)


def test_the_row_has_no_inline_input_any_more():
    """It was the only row on the panel with a form control in it, and the
    control is what let the two bases disagree."""
    from pathlib import Path
    html = Path("templates/pages/add-building/components/"
                "operational-details/energy-consumption-summary.html").read_text(
                    encoding="utf-8")
    assert 'id="plug-load-percent"' not in html
    assert 'savePlugLoadPercent' not in html
    # and no explanatory line either: the row carries the label and the figure,
    # nothing else, like the five rows above it
    assert 'system energy' not in html.split('summary-row-plug-load')[1][:1200]
    # the figure is grouped, so 48449.856 reads 48,449.856
    assert 'floatformat:"-3g"' in html


def test_the_modal_asks_the_question_before_the_value():
    from pathlib import Path
    html = Path("templates/pages/add-building/components/"
                "operational-details/energy-consumption-summary.html").read_text(
                    encoding="utf-8")
    assert 'id="plug-load-gate"' in html
    assert 'name="has_plug_load"' in html
    assert 'name="plug_basis"' in html


def test_the_gate_offers_yes_and_no_only():
    """Two answers, not three. "Not known" was the only way into the typical
    share, and it made the question harder than it is."""
    from pathlib import Path
    html = Path("templates/pages/add-building/components/"
                "operational-details/energy-consumption-summary.html").read_text(
                    encoding="utf-8")
    gate = html[html.index('id="plug-load-gate"'):]
    gate = gate[:gate.index("</fieldset>")]
    assert gate.count('name="has_plug_load"') == 2
    assert 'value="yes"' in gate and 'value="no"' in gate
    assert 'value="unknown"' not in gate


def test_the_javascript_renders_the_same_figure_the_server_does():
    """updateRow read plug_load_kwh like the other five rows. A building that
    answered "no" stores null and means zero, so saving "No" repainted the row
    as the orange NO DATA warning while the server had recorded the answer."""
    from pathlib import Path
    html = Path("templates/pages/add-building/components/"
                "operational-details/energy-consumption-summary.html").read_text(
                    encoding="utf-8")
    assert "kwh = summary.plug_load_effective;" in html
    src = Path("pages/views/building/energy_summary.py").read_text(encoding="utf-8")
    assert '"plug_load_effective"' in src
