"""Layer 2 applied to a building: what replacing its equipment would save.

Every test here exists because the first working version got the answer wrong
on real data, not because the code looked risky.
"""
from decimal import Decimal

import pytest

from pages.models.building import Building
from pages.models.building_operation.air_conditioning import CoolingSystemAirConditioner
from pages.models.building_operation.ventilation import VentilationSystem
from pages.models.climate_type import ClimateType
from pages.views.building.equipment_savings import (
    AC_TYPE_TO_BENCHMARK, SFP_PLAUSIBLE, _within,
    get_equipment_efficiency_savings,
)
from pages.views.building.system_efficiency_data import (
    HIGHER_IS_BETTER, LOWER_IS_BETTER,
)

# The AC model requires refrigerant data regardless of what is being tested.
AC_REQUIRED = {
    "year_of_installation": 2020,
    "refrigerant_type": "R-410A",
    "refrigerant_quantity_kg": Decimal("1.0"),
    "baseline_leakage_factor_percent": Decimal("5.0"),
}

VENT_FORM = "templates/pages/add-building/components/operational-details/ventilation-system.html"


@pytest.fixture
def india():
    """Factory, not a database fixture - the repo's existing pattern, so the
    tests carry the django_db marker themselves."""
    def _make():
        from cities_light.models import Country
        climate, _ = ClimateType.objects.get_or_create(name="composite")
        country, _ = Country.objects.get_or_create(
            name="India", defaults={"code2": "IN"})
        return Building.objects.create(
            name="Layer 2 test", climate_zone=climate, country=country,
            total_floor_area=Decimal("1000"),
        )
    return _make


# --- the guard that stops a false saving ----------------------------------

def test_an_implausibly_bad_fan_power_is_refused():
    """60 W/CMH against a 0.25 benchmark reads as a 99.6% saving. It happened
    on a real building before this guard existed."""
    assert _within(Decimal("60"), SFP_PLAUSIBLE, LOWER_IS_BETTER) is False


def test_an_efficient_unit_below_the_typical_band_is_still_benchmarked():
    """A 5-star Indian split at ISEER 5.3 is 0.66 kW/RT, under the 0.75 the
    cooling form calls typical. Refusing it would mean declining to benchmark
    the best equipment in the database. It cannot produce a false saving: it
    is already past the target, so the fraction is zero anyway."""
    assert _within(Decimal("0.66"), (Decimal("0.75"), Decimal("1.80")),
                   LOWER_IS_BETTER) is True


def test_the_guard_is_directional_not_a_window():
    """Higher-is-better metrics fail at the low end instead."""
    assert _within(Decimal("0.5"), (Decimal("1"), Decimal("10")), HIGHER_IS_BETTER) is False
    assert _within(Decimal("12"), (Decimal("1"), Decimal("10")), HIGHER_IS_BETTER) is True


def test_the_fan_power_band_still_matches_what_the_form_tells_users():
    """The guard borrows the form's own advice rather than inventing a range.
    If the tooltip changes, this fails and the guard is revisited."""
    from pathlib import Path
    html = Path(VENT_FORM).read_text(encoding="utf-8")
    assert "typical range 0.30 to 1.20 W/CMH" in html
    assert SFP_PLAUSIBLE == (Decimal("0.30"), Decimal("1.20"))


@pytest.mark.django_db
def test_a_cassette_with_a_nonsense_fan_power_yields_no_saving(india):
    india = india()
    VentilationSystem.objects.create(
        building=india, ventilation_type="CASSETTE_AC",
        baseline_efficiency_w_cmh=Decimal("60.00"),
        number_of_units_installed=1, total_power_input_kw=Decimal("5"),
        total_energy_consumption_kwh_per_year=Decimal("10000"),
    )
    vent = next(s for s in get_equipment_efficiency_savings(india)["systems"]
                if s["key"] == "ventilation")
    assert vent["no_benchmark"] == 1
    assert vent["saving_kwh"] == 0.0


# --- weighting -------------------------------------------------------------

@pytest.mark.django_db
def test_the_system_fraction_is_weighted_by_energy_not_by_record_count(india):
    """One efficient small unit and one poor large unit is not half-way
    efficient. The fraction must follow the kWh."""
    india = india()
    CoolingSystemAirConditioner.objects.create(
        building=india, ac_type="split", efficiency_metric="cop",
        **AC_REQUIRED,
        eer_iseer_cop=Decimal("5.0"), number_of_units=1,          # already good
        total_energy_consumption_kwh_per_year=Decimal("500"))
    CoolingSystemAirConditioner.objects.create(
        building=india, ac_type="split", efficiency_metric="cop",
        **AC_REQUIRED,
        eer_iseer_cop=Decimal("2.5"), number_of_units=1,          # poor
        total_energy_consumption_kwh_per_year=Decimal("50000"))
    cooling = next(s for s in get_equipment_efficiency_savings(india)["systems"]
                   if s["key"] == "cooling")
    assert cooling["records"] == 2
    assert cooling["benchmarked"] == 1
    assert cooling["already_better"] == 1
    # The poor unit carries 99% of the energy, so the fraction sits near its
    # own saving rather than halfway between the two.
    assert cooling["saving_fraction"] > 0.3


@pytest.mark.django_db
def test_a_window_unit_reports_no_benchmark_rather_than_borrowing_the_split(india):
    """The workbook publishes no window row. 20 units in production."""
    india = india()
    assert "window" not in AC_TYPE_TO_BENCHMARK
    CoolingSystemAirConditioner.objects.create(
        building=india, ac_type="window", efficiency_metric="cop",
        **AC_REQUIRED,
        eer_iseer_cop=Decimal("2.5"), number_of_units=1,
        total_energy_consumption_kwh_per_year=Decimal("5000"))
    cooling = next(s for s in get_equipment_efficiency_savings(india)["systems"]
                   if s["key"] == "cooling")
    assert cooling["no_benchmark"] == 1
    assert cooling["saving_kwh"] == 0.0


@pytest.mark.django_db
def test_coverage_counts_are_reported_so_a_small_saving_can_be_read(india):
    """"Little to gain" and "we could only look at one of your three units"
    are different answers and must not look the same."""
    india = india()
    r = get_equipment_efficiency_savings(india)
    assert set(r["coverage"]) == {"records", "with_saving", "already_better", "no_benchmark"}


# --- reuse rather than a second taxonomy ----------------------------------

def test_lighting_defers_to_layer_1s_category_resolver():
    """A building must not be an Office for its EPI benchmark and a Hotel for
    its lighting one."""
    import inspect
    from pages.views.building import equipment_savings as es
    src = inspect.getsource(es._lpd_type)
    assert "_resolve_epi_type" in src


def test_lighting_does_not_trust_the_stored_power_density_column():
    """baseline_lighting_power_density is not W/m2: all 491 production rows
    are between 0.00 and 2.00 with a median of 0.00. Using it made every
    building "already better than best practice" on a lighting load of zero."""
    import inspect
    from pages.views.building import equipment_savings as es
    src = inspect.getsource(es.get_equipment_efficiency_savings)
    lighting = src[src.index("lpd_type = _lpd_type"):]
    assert "total_lighting_power_kw" in lighting
    assert "_dec(l.baseline_lighting_power_density)" not in lighting


# --- provenance ------------------------------------------------------------
#
# The India lighting values were wrong for months in a way no plausibility
# check caught: real ECBC numbers attached to the wrong building types. Only
# opening the code found it. A benchmark that cannot say where it came from is
# one nobody can audit.

def test_india_lighting_reports_its_code_and_is_marked_verified():
    from pages.views.building.system_efficiency_data import benchmark_source
    citation, status = benchmark_source("lighting", "India")
    assert "ECSBC 2024" in citation
    assert status == "verified"


def test_everything_else_is_marked_unverified_against_the_workbook():
    """Four countries still rest on the spreadsheet alone. Saying so is the
    worklist for replacing them."""
    from pages.views.building.system_efficiency_data import benchmark_source
    for key, country in [("lighting", "Thailand"), ("split", "India"),
                         ("ventilation", "Vietnam"), ("air_cooled_chiller", "Cambodia")]:
        citation, status = benchmark_source(key, country)
        assert status == "unverified", (key, country)
        assert "xlsx" in citation


def test_a_resolved_benchmark_carries_its_source(india):
    from pages.views.building.system_efficiency_data import resolve_system_benchmark
    r = resolve_system_benchmark("air_cooled_chiller", "India")
    assert r["source"]
    assert r["verified"] is False


@pytest.mark.django_db
def test_a_system_with_no_benchmark_is_distinguishable_from_one_with_no_saving(india):
    """A flat bar must not read as "nothing to gain here" when it means "not
    assessed". The chart hatches one and not the other."""
    india = india()
    CoolingSystemAirConditioner.objects.create(
        building=india, ac_type="window", efficiency_metric="cop",
        **AC_REQUIRED, eer_iseer_cop=Decimal("2.5"), number_of_units=1,
        total_energy_consumption_kwh_per_year=Decimal("5000"))
    cooling = next(s for s in get_equipment_efficiency_savings(india)["systems"]
                   if s["key"] == "cooling")
    assert cooling["has_benchmark"] is False
    assert cooling["energy_kwh"] == 5000.0      # the energy is still real
    assert cooling["saving_kwh"] == 0.0


@pytest.mark.django_db
def test_a_system_keeps_its_target_even_when_no_record_can_use_it(india):
    """Ventilation is the real case: India publishes 0.42 W/CMH, but most
    stored specific fan powers are outside the range the form itself declares,
    so every record is refused. The row must still say what the target is -
    "has a benchmark" and "Target None" cannot both be true."""
    india = india()
    VentilationSystem.objects.create(
        building=india, ventilation_type="CASSETTE_AC",
        baseline_efficiency_w_cmh=Decimal("60.00"),   # refused by the guard
        number_of_units_installed=1, total_power_input_kw=Decimal("5"),
        total_energy_consumption_kwh_per_year=Decimal("10000"))
    vent = next(s for s in get_equipment_efficiency_savings(india)["systems"]
                if s["key"] == "ventilation")
    assert vent["has_benchmark"] is True
    # India ventilation: national 0.42, LEED 0.31, EDGE 0.25 - EDGE wins
    assert vent["target"] == 0.25
    assert vent["unit"] == "W/CMH"
    assert vent["no_benchmark"] == 1
    assert vent["saving_kwh"] == 0.0
