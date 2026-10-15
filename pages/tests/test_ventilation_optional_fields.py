"""Fields that were required on forms that never read them, and a column too
coarse to hold the equipment it describes.

The FCU, cassette and fan forms compute energy from power x units x hours.
They never look at airflow or baseline efficiency, yet both carried a red
asterisk: 149 of the 152 stored rows are on those three forms, so almost
every value in that column was invented to get past a validator.

Separately, total_power_input_kw was numeric(10,2). A chilled-water fan coil
is tens of watts, 84 of the 152 rows are under 1 kW, and one record - seven
fans at 300 CMH each - stored 0.00 kW and reported 0 kWh a year.
"""
import re
from decimal import Decimal
from pathlib import Path

import pytest

from pages.forms.ventilation_system_form import VentilationSystemForm
from pages.models.building import Building
from pages.models.building_operation.ventilation import VentilationSystem
from pages.models.climate_type import ClimateType

REPO = Path(__file__).resolve().parents[2]
VENT_FORM = REPO / ("templates/pages/add-building/components/"
                    "operational-details/ventilation-system.html")

@pytest.fixture
def building():
    climate, _ = ClimateType.objects.get_or_create(name="cold")
    return Building.objects.create(
        name="Ventilation field test", climate_zone=climate,
        total_floor_area=Decimal("100"),
    )


SIMPLE = ("fcu-template", "cassette-template", "fan-template")
DERIVED = ("ahu-template", "doas-template")


def _template(name):
    src = VENT_FORM.read_text(encoding="utf-8")
    start = src.index('<template id="%s">' % name)
    return src[start:src.index("</template>", start)]


def _field(block, field_name):
    m = re.search(r'<input[^>]*name="%s"[^>]*>' % field_name, block)
    assert m, "%s not found" % field_name
    return m.group(0)


# --- 1. the three forms that ignore these fields no longer demand them ------

@pytest.mark.parametrize("template", SIMPLE)
@pytest.mark.parametrize("field", ["baseline_efficiency", "airflow_rate"])
def test_a_form_that_ignores_a_field_does_not_require_it(template, field):
    assert "required" not in _field(_template(template), field)


@pytest.mark.parametrize("template", SIMPLE)
@pytest.mark.parametrize("field", ["Baseline efficiency", "Air flow rate per unit"])
def test_the_optional_fields_say_so_and_say_why(template, field):
    """An asterisk that is not enforced is worse than none: it still reads as
    an instruction. The label says Optional and the note says the number does
    not reach the calculation."""
    block = _template(template)
    legend = next(l for l in block.splitlines() if field in l and "legend" in l)
    assert "Optional" in legend, legend
    assert 'text-[var(--state--error--base)]">*' not in legend, legend
    assert "Reference only" in block


@pytest.mark.parametrize("template", DERIVED)
@pytest.mark.parametrize("field", ["baseline_efficiency", "airflow_rate"])
def test_the_forms_that_use_these_fields_still_require_them(template, field):
    """AHU and DOAS derive power from airflow x efficiency. Without both there
    is no figure at all, so there the asterisk is honest."""
    assert "required" in _field(_template(template), field)


# --- 2. and the database lets them be absent -------------------------------

@pytest.mark.django_db
def test_a_fan_saves_without_an_airflow_or_an_efficiency(building):
    system = VentilationSystem.objects.create(
        building=building,
        ventilation_type="FAN",
        number_of_units_installed=7,
        total_power_input_kw=Decimal("0.3500"),
        total_energy_consumption_kwh_per_year=Decimal("1274.0"),
    )
    system.refresh_from_db()
    assert system.baseline_efficiency_w_cmh is None
    assert system.air_flow_rate is None


@pytest.mark.django_db
def test_the_form_accepts_a_blank_efficiency():
    form = VentilationSystemForm(data={
        "ventilation_type": "FCU",
        "number_of_units": "2",
        "baseline_efficiency": "",
        "airflow_rate": "",
        "power_input": "0.1260",
        "operating_hours_per_day": "10",
        "operating_days_per_week": "5",
        "operating_weeks_per_year": "52",
        "annual_energy_consumption": "327.6",
    })
    assert form.is_valid(), form.errors


# --- 3. power is entered in the unit the equipment is nameplated in ---------

@pytest.mark.parametrize("template", SIMPLE)
def test_power_can_be_entered_in_watts(template):
    block = _template(template)
    select = re.search(r'<select[^>]*name="power_input_unit"[\s\S]*?</select>', block)
    assert select, "no unit selector"
    assert '<option value="W" selected>' in select.group(0)
    assert '<option value="kW">' in select.group(0)


@pytest.mark.parametrize("template", SIMPLE)
def test_the_power_example_is_a_plausible_figure_in_the_chosen_unit(template):
    """"e.g. 8" beside kW read like a cooling capacity and invited an entry
    three orders of magnitude out."""
    field = _field(_template(template), "power_input_per_unit")
    m = re.search(r'placeholder="e\.g\. ([\d.]+)"', field)
    assert m, field
    assert 10 <= float(m.group(1)) <= 1000, field


def test_watts_are_converted_before_the_total_is_formed():
    src = VENT_FORM.read_text(encoding="utf-8")
    body = src[src.index("window.recalcVentSimpleEnergy"):]
    body = body[:body.index("window.recalcVentSimpleEnergy") + 2000]
    assert "perUnit = perUnit / 1000" in body
    # the division must come before the multiplication, or the total is 1000x
    assert body.index("perUnit / 1000") < body.index("perUnit * units")


# --- 4. the column is wide enough for the equipment ------------------------

@pytest.mark.django_db
def test_a_sixty_three_watt_fan_coil_survives_being_stored(building):
    """At two decimal places 0.0630 became 0.06 and the year came out 120 kWh
    instead of 126. At zero decimal places it became nothing at all."""
    system = VentilationSystem.objects.create(
        building=building,
        ventilation_type="FCU",
        number_of_units_installed=1,
        total_power_input_kw=Decimal("0.0630"),
        total_energy_consumption_kwh_per_year=Decimal("126.0"),
    )
    system.refresh_from_db()
    assert system.total_power_input_kw == Decimal("0.0630")


def test_the_stored_power_keeps_four_decimal_places():
    field = VentilationSystem._meta.get_field("total_power_input_kw")
    assert field.decimal_places == 4


def test_reopening_a_record_does_not_round_a_small_fan_away():
    """The editable field is derived from the stored total on every reopen. A
    toFixed(2) there put 0.06 back in the box, and the next save wrote it."""
    src = VENT_FORM.read_text(encoding="utf-8")
    block = src[src.index("// Stored value is the total"):]
    block = block[:block.index("sf('airflow_rate'")]
    code = [l for l in block.splitlines()
            if not l.strip().startswith("//")]
    assert not any("toFixed(2)" in l for l in code)
    assert "perUnitKw * 1000" in block
