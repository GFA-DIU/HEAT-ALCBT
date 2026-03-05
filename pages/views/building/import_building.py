import datetime
import logging
import uuid as uuid_lib
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.http import require_http_methods

from accounts.models import CustomCity, CustomRegion
from pages.models.base import ALCBTCountryManager
from pages.models.building import (
    Building,
    BuildingBoQFile,
    BuildingCategory,
    BuildingSubcategory,
    CategorySubcategory,
    ClimateZone,
)
from pages.models.epd import EPD, EPDType, Unit
from pages.models.building import OperationalProduct
from pages.models.assembly import (
    Assembly, AssemblyCategory, AssemblyDimension, AssemblyMode,
    AssemblyCategoryTechnique, StructuralProduct,
)
from pages.models.building_operation import CoolingSystemChiller, CoolingSystemAirConditioner
from pages.models.building_operation.ventilation import VentilationType, VentilationCapacity
from pages.models.building_operation.lighting import RoomType, LightingBulbType, EnergyEfficiencyLabelType
from pages.models.building_operation import HotWaterSystem, HotWaterSystemType, FuelType
from pages.forms.cooling_system_form import (
    CAPACITY_CONVERSION,
    CoolingSystemAirConditionerForm,
    CoolingSystemChillerForm,
)
from pages.forms.ventilation_system_form import VentilationSystemForm
from pages.forms.lighting_system_form import LightingSystemForm
from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm
from pages.forms.hot_water_system_form import HotWaterSystemForm

logger = logging.getLogger(__name__)

# ALCBT-supported country codes (same as ALCBTCountryManager)
ALCBT_COUNTRY_CODES = {"ID", "TH", "VN", "KH", "IN"}

# Map Excel climate type display labels → ClimateZone values
CLIMATE_LABEL_MAP = {
    "hot-dry": ClimateZone.HOT_DRY,
    "hot dry": ClimateZone.HOT_DRY,
    "warm-humid": ClimateZone.WARM_HUMID,
    "warm humid": ClimateZone.WARM_HUMID,
    "composite": ClimateZone.COMPOSITE,
    "temperate": ClimateZone.TEMPERATE,
    "cold": ClimateZone.COLD,
    "tropical-wet": ClimateZone.TROPICAL_WET,
    "tropical wet": ClimateZone.TROPICAL_WET,
}


# Helpers

def _str(value):
    """Return stripped string or empty string for None/blank."""
    if value is None:
        return ""
    return str(value).strip()


def _bool_from_excel(value):
    """Convert Excel Yes/No (or True/False) to Python bool."""
    if isinstance(value, bool):
        return value
    return _str(value).lower() in ("yes", "true", "1")


def _get_allowed_countries():
    """Return queryset of ALCBT countries."""
    return ALCBTCountryManager.get_alcbt_countries()


def _resolve_country(name):
    """
    Look up a Country by name from the ALCBT-allowed set.
    Returns (country, error_string).
    """
    name = _str(name)
    if not name:
        return None, "Country is required."

    qs = _get_allowed_countries()
    country = qs.filter(name__iexact=name).first()
    if country:
        return country, None

    allowed_names = ", ".join(sorted(qs.values_list("name", flat=True)))
    return None, (
        f"Country '{name}' is not supported. "
        f"Supported countries are: {allowed_names}."
    )


def _resolve_region(name, country):
    """Look up CustomRegion by name within a country. Returns (region, error_string)."""
    name = _str(name)
    if not name:
        return None, None  # optional field

    region = CustomRegion.objects.filter(
        name__iexact=name, country=country
    ).first()
    if region:
        return region, None

    return None, f"Region '{name}' was not found for country '{country.name}'."


def _resolve_city(name, country):
    """Look up CustomCity by name within a country. Returns (city, error_string)."""
    name = _str(name)
    if not name:
        return None, "City is required."

    city = CustomCity.objects.filter(
        name__iexact=name, country=country
    ).first()
    if city:
        return city, None

    return None, f"City '{name}' was not found for country '{country.name}'."


def _resolve_building_type(combined_name):
    """
    Parse a string like "Homes - middle income" or "Homes – middle income"
    into (BuildingCategory, BuildingSubcategory) and look up CategorySubcategory.
    Returns (category_subcat, error_string).
    """
    combined_name = _str(combined_name)
    if not combined_name:
        return None, "Building type is required."

    # Split on em-dash, en-dash, or hyphen surrounded by spaces
    for sep in [" – ", " — ", " - "]:
        if sep in combined_name:
            parts = combined_name.split(sep, 1)
            break
    else:
        # Try a plain hyphen split as last resort
        parts = combined_name.split("-", 1)

    if len(parts) != 2:
        return None, (
            f"Building type '{combined_name}' must be in the format "
            f"'<Building type> - <Apartment type>'."
        )

    cat_name = parts[0].strip()
    subcat_name = parts[1].strip()

    category = BuildingCategory.objects.filter(name__iexact=cat_name).first()
    if not category:
        return None, f"Building type '{cat_name}' was not found."

    subcategory = BuildingSubcategory.objects.filter(name__iexact=subcat_name).first()
    if not subcategory:
        return None, f"Apartment type '{subcat_name}' was not found."

    cat_subcat = CategorySubcategory.objects.filter(
        category=category, subcategory=subcategory
    ).first()
    if not cat_subcat:
        return None, (
            f"The combination '{cat_name} - {subcat_name}' is not a valid "
            f"building type. Check the List sheet in the template for valid options."
        )

    return cat_subcat, None


def _resolve_climate(value):
    """
    Map a climate display string to a ClimateZone value.
    Returns (climate_zone_value, error_string).
    """
    value = _str(value)
    if not value:
        return None, "Area climate type is required."

    zone = CLIMATE_LABEL_MAP.get(value.lower())
    if zone:
        return zone, None

    valid = ", ".join(sorted(set(CLIMATE_LABEL_MAP.keys())))
    return None, (
        f"Climate type '{value}' is not recognised. "
        f"Valid options are: {valid}."
    )


# Map Excel temperature unit label → Unit model value
TEMP_UNIT_MAP = {
    "celsius": Unit.CELSIUS,
    "fahrenheit": Unit.FAHRENHEIT,
}


def _resolve_temp_unit(value):
    """
    Map 'Celsius' / 'Fahrenheit' (case-insensitive) to the Unit enum value.
    Returns (unit_value, error_string).
    """
    value = _str(value)
    if not value:
        return None, None  # optional — allow blank
    unit = TEMP_UNIT_MAP.get(value.lower())
    if unit:
        return unit, None
    return None, (
        f"Temperature unit '{value}' is not recognised. Use 'Celsius' or 'Fahrenheit'."
    )


def _validate_int_range(raw, field_label, min_val, max_val, required=False):
    """
    Parse raw string as int and validate range.
    Returns (int_value_or_None, error_string_or_None).
    """
    raw = _str(raw)
    if not raw:
        if required:
            return None, f"{field_label} is required."
        return None, None
    try:
        val = int(float(raw))
    except (ValueError, TypeError):
        return None, f"{field_label} must be a whole number."
    if val < min_val or val > max_val:
        return None, f"{field_label} must be between {min_val} and {max_val}."
    return val, None


def _validate_decimal_range(raw, field_label, min_val, max_val, required=False):
    """
    Parse raw string as float and validate range.
    Returns (float_value_or_None, error_string_or_None).
    """
    raw = _str(raw)
    if not raw:
        if required:
            return None, f"{field_label} is required."
        return None, None
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return None, f"{field_label} must be a number."
    if val < min_val or val > max_val:
        return None, f"{field_label} must be between {min_val} and {max_val}."
    return val, None


# ---------------------------------------------------------------------------
# Tab 3 — Operational Schedule & Temperature
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def import_operational_schedule(request):
    """
    Process Tab 3 (Operational Schedule and Temperature) from the import template.

    Expects JSON with fields:
      building_uuid (required),
      num_residents, hours_per_workday, workdays_per_week, weeks_per_year,
      heating_temp, heating_temp_unit, cooling_temp, cooling_temp_unit,
      renewable_energy_percent, building_smart_system
    """
    import json
    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    errors = {}

    # Number of residents — optional, min 0
    num_residents, err = _validate_int_range(
        data.get("num_residents"), "Number of residents", 0, 999999
    )
    if err:
        errors["num_residents"] = err

    # Hours per workday — optional, 0–24
    hours_per_workday, err = _validate_int_range(
        data.get("hours_per_workday"), "Hours per day", 0, 24
    )
    if err:
        errors["hours_per_workday"] = err

    # Workdays per week — optional, 0–7
    workdays_per_week, err = _validate_int_range(
        data.get("workdays_per_week"), "Days per week", 0, 7
    )
    if err:
        errors["workdays_per_week"] = err

    # Weeks per year — optional, 0–52
    weeks_per_year, err = _validate_int_range(
        data.get("weeks_per_year"), "Weeks per year", 0, 52
    )
    if err:
        errors["weeks_per_year"] = err

    # Cross-field: hours × days × weeks should form a logical schedule
    # (no hard cap, but we still validate each field individually above)

    # Heating temperature — optional, 0–120
    heating_temp, err = _validate_decimal_range(
        data.get("heating_temp"), "Room heating temperature", 0, 120
    )
    if err:
        errors["heating_temp"] = err

    # Heating temperature unit
    heating_temp_unit, err = _resolve_temp_unit(data.get("heating_temp_unit"))
    if err:
        errors["heating_temp_unit"] = err

    # Cooling temperature — optional, 0–120
    cooling_temp, err = _validate_decimal_range(
        data.get("cooling_temp"), "Room cooling temperature", 0, 120
    )
    if err:
        errors["cooling_temp"] = err

    # Cooling temperature unit
    cooling_temp_unit, err = _resolve_temp_unit(data.get("cooling_temp_unit"))
    if err:
        errors["cooling_temp_unit"] = err

    # Renewable energy percent — optional, 0–100
    renewable_raw = _str(data.get("renewable_energy_percent"))
    renewable_energy_percent = None
    if renewable_raw:
        try:
            rval = float(renewable_raw)
            if rval < 0 or rval > 100:
                errors["renewable_energy_percent"] = "Renewable energy % must be between 0 and 100."
            else:
                renewable_energy_percent = rval
        except (ValueError, TypeError):
            errors["renewable_energy_percent"] = "Renewable energy % must be a number."

    # Building smart system — optional boolean
    building_smart_system = _bool_from_excel(data.get("building_smart_system", "no"))

    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    # --- Save ---
    if num_residents is not None:
        building.num_residents = num_residents
    if hours_per_workday is not None:
        building.hours_per_workday = hours_per_workday
    if workdays_per_week is not None:
        building.workdays_per_week = workdays_per_week
    if weeks_per_year is not None:
        building.weeks_per_year = weeks_per_year
    if heating_temp is not None:
        building.heating_temp = heating_temp
    if heating_temp_unit is not None:
        building.heating_temp_unit = heating_temp_unit
    if cooling_temp is not None:
        building.cooling_temp = cooling_temp
    if cooling_temp_unit is not None:
        building.cooling_temp_unit = cooling_temp_unit
    if renewable_energy_percent is not None:
        building.renewable_energy_percent = renewable_energy_percent
    building.building_smart_system = building_smart_system

    building.save()

    logger.info(f"Import Tab 3: operational schedule saved for building {building.uuid} by {request.user}")

    return JsonResponse({"success": True, "building_uuid": str(building.uuid)})


# ---------------------------------------------------------------------------
# Tab 4–9 — Cooling Systems
# ---------------------------------------------------------------------------

# Maps Excel tab name fragment → (cooling_system_type, ac_type, chiller_type, packaged_subtype)
# cooling_system_type: 'air_conditioner' | 'chiller'
# ac_type: 'window' | 'split' | 'vrv' | 'packaged' | None
# chiller_type: 'water_cooled' | 'air_cooled' | None
# packaged_subtype: resolved from column 0 of each row for Packaged tab, else None
COOLING_TAB_MAP = {
    'window ac':       ('air_conditioner', 'window',      None,          None),
    'split ac':        ('air_conditioner', 'split',       None,          None),
    'vrf':             ('air_conditioner', 'vrv',         None,          None),
    'packagedductab':  ('air_conditioner', 'packaged',    None,          'from_column'),
    'water cooled':    ('chiller',         None,          'water_cooled', None),
    'air cooled':      ('chiller',         None,          'air_cooled',  None),
}

# Packaged sub-type label → model value
PACKAGED_SUBTYPE_MAP = {
    'rooftop':        'rooftop',
    'floor standing': 'floor_standing',
    'floor-standing': 'floor_standing',
    'ductable':       'ductable',
    'cassette':       'cassette',
}

# Column index definitions per tab type (0-based, after stripping None columns)
# These match the exact header order read from the Excel file.

# AC tabs: Window, Split, VRF — 14 user columns + 1 auto-calculated (not read)
# 0:year  1:refrigerant_type  2:refrigerant_qty  3:cooling_capacity  4:capacity_unit
# 5:num_units  6:leakage_factor  7:hours/day  8:days/week  9:weeks/year
# 10:power_input_per_unit  11:eer_iseer_cop  12:energy_label  13:stars
# (col 14 in template = auto-calculated annual energy, ignored on import)

# Packaged tab — 16 user columns + 1 auto-calculated (not read)
# 0:subtype  1:year  2:refrigerant_type  3:refrigerant_qty  4:cooling_capacity  5:capacity_unit
# 6:num_units  7:leakage_factor  8:hours/day  9:days/week  10:weeks/year
# 11:power_input_per_unit  12:eer_iseer_cop  13:eer_formula_hint(ignored)  14:energy_label
# 15:stars  (col 16 in template = auto-calculated annual energy, ignored on import)

# Chiller Water tabs — 18 user columns + 1 auto-calculated (not read)
# 0:year  1:refrigerant_type  2:refrigerant_qty  3:total_cooling_load  4:num_units
# 5:leakage_factor  6:hours/day  7:days/week  8:weeks/year
# 9:baseline_efficiency  10:vsd  11:heat_recovery  12:iplv  13:load_factor
# 14:system_power_input  15:cop  16:energy_label  17:stars
# (col 18 in template = auto-calculated annual energy, ignored on import)

# Chiller Air tabs — 17 user columns + 1 auto-calculated (not read)
# 0:year  1:refrigerant_type  2:refrigerant_qty  3:total_cooling_load  4:num_units
# 5:leakage_factor  6:hours/day  7:days/week  8:weeks/year
# 9:baseline_efficiency  10:vsd  11:heat_recovery  12:iplv
# 13:system_power_input  14:cop  15:energy_label  16:stars
# (col 17 in template = auto-calculated annual energy, ignored on import)


# ---------------------------------------------------------------------------
# Auto-calculation helpers (mirror the frontend JS logic)
# ---------------------------------------------------------------------------

def _leakage_default(year_str):
    """
    Return year-based baseline leakage factor default:
    - system age ≥ 7 years → 10 %
    - otherwise            → 2 %
    Returns a string so it can be dropped into form data directly.
    """
    try:
        year = int(float(year_str))
        current_year = datetime.datetime.now().year
        return '10' if (current_year - year) >= 7 else '2'
    except (ValueError, TypeError):
        return '2'


def _capacity_to_kw(value_str, unit_str):
    """Convert cooling capacity value to kW using the same factors as the form."""
    try:
        val = Decimal(str(value_str))
    except (InvalidOperation, TypeError):
        return Decimal('0')
    unit = (unit_str or 'kw').strip().lower()
    factor = CAPACITY_CONVERSION.get(unit, Decimal('1'))
    return val * factor


def _calc_ac_energy(row_data):
    """
    Compute total_energy_consumption_annually (kWh/year) for AC systems.
    Mirrors recalcWindowAcEnergy from the frontend.

      If power_input_per_unit > 0:
        energy = power_input_per_unit × units × h × d × w
      Else:
        energy = (capacity_kw × units / EER) × h × d × w

    Returns a rounded string, or '' if inputs are insufficient.
    AC form uses hours_per_day / days_per_week / weeks_per_year keys.
    """
    def _f(key):
        try:
            return float(row_data.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    units = _f('number_of_units')
    hrs   = _f('hours_per_day')
    days  = _f('days_per_week')
    weeks = _f('weeks_per_year')
    power = _f('power_input_per_unit')

    if units <= 0 or hrs <= 0 or days <= 0 or weeks <= 0:
        return ''

    if power > 0:
        energy = power * units * hrs * days * weeks
    else:
        eer = _f('eer_iseer_cop')
        cap_kw = float(_capacity_to_kw(
            row_data.get('cooling_capacity_per_unit', '0'),
            row_data.get('cooling_capacity_unit', 'kw'),
        ))
        if cap_kw <= 0 or eer <= 0:
            return ''
        energy = (cap_kw * units / eer) * hrs * days * weeks

    return str(round(Decimal(str(energy)), 3))


def _calc_chiller_energy(row_data):
    """
    Compute total_energy_consumption_of_chiller_system_annually (kWh/year) for chillers.
    Mirrors recalcChillerEnergy from the frontend.

      energy = load × units × efficiency × h × d × w × vsd_factor × hr_factor
      vsd_factor = 0.80 if VSD=yes else 1.00
      hr_factor  = 0.70 if HR=yes  else 1.00

    Returns a rounded string, or '' if inputs are insufficient.
    """
    def _f(key):
        try:
            return float(row_data.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    def _yes(key):
        return str(row_data.get(key, '')).strip().lower() in ('yes', 'true', '1')

    load  = _f('total_cooling_load')
    units = _f('number_of_chillers')
    eff   = _f('baseline_cooling_efficiency')
    hrs   = _f('annual_operating_hours_per_day')
    days  = _f('annual_operating_days_per_week')
    weeks = _f('annual_operating_weeks_per_year')

    if load <= 0 or units <= 0 or eff <= 0 or hrs <= 0 or days <= 0 or weeks <= 0:
        return ''

    vsd_factor = 0.80 if _yes('installation_of_variable_speed_drives') else 1.00
    hr_factor  = 0.70 if _yes('installation_of_heat_recovery_systems') else 1.00

    energy = load * units * eff * hrs * days * weeks * vsd_factor * hr_factor
    return str(round(Decimal(str(energy)), 3))


def _parse_cooling_rows(sheet_key, raw_rows):
    """
    Parse all data rows from a cooling system Excel tab.
    Returns list of dicts ready to pass to the relevant form.
    Skips rows where year_of_installation is blank.

    sheet_key: lowercased, spaces-normalised tab name fragment used in COOLING_TAB_MAP
    raw_rows: list of lists (each inner list is one data row, already stripped of trailing Nones)

    Auto-calculated fields applied here (mirroring frontend JS):
    - baseline_leakage_factor: year-based default if blank (age ≥ 7 yrs → 10 %, else → 2 %)
    - total_energy_consumption_annually / total_energy_consumption_of_chiller_system_annually:
        always computed server-side; any value already in the template row is ignored.
    """
    entry = COOLING_TAB_MAP.get(sheet_key)
    if not entry:
        return []

    cooling_system_type, ac_type, chiller_type, packaged_subtype_flag = entry
    results = []

    for row in raw_rows:
        def cell(idx, default=''):
            val = row[idx] if idx < len(row) else None
            if val is None or str(val).strip().lower() == 'none':
                return default
            return str(val).strip()

        if cooling_system_type == 'air_conditioner':
            if sheet_key == 'packagedductab':
                # Col 0 = subtype, data starts at col 1
                subtype_raw = cell(0)
                subtype = PACKAGED_SUBTYPE_MAP.get(subtype_raw.lower(), '') or subtype_raw.lower()
                year = cell(1)
                if not year:
                    continue  # skip empty row
                leakage = cell(7) or _leakage_default(year)
                row_data = {
                    'cooling_system_type':    'air_conditioner',
                    'ac_type':                'packaged',
                    'packaged_subtype':       subtype,
                    'year_of_installation':   year,
                    'type_of_refrigerants':   cell(2),
                    'refrigerant_quantity':   cell(3),
                    'cooling_capacity_per_unit': cell(4),
                    'cooling_capacity_unit':  cell(5).lower() or 'kw',
                    'number_of_units':        cell(6),
                    'baseline_leakage_factor': leakage,
                    'hours_per_day':          cell(8),
                    'days_per_week':          cell(9),
                    'weeks_per_year':         cell(10),
                    'power_input_per_unit':   cell(11),
                    'eer_iseer_cop':          cell(12),
                    'energy_efficiency_label': cell(14),
                    'number_of_stars':        cell(15),
                }
            else:
                # Window / Split / VRF — col 0 = year
                year = cell(0)
                if not year:
                    continue  # skip empty row
                leakage = cell(6) or _leakage_default(year)
                row_data = {
                    'cooling_system_type':   'air_conditioner',
                    'ac_type':               ac_type,
                    'year_of_installation':  year,
                    'type_of_refrigerants':  cell(1),
                    'refrigerant_quantity':  cell(2),
                    'cooling_capacity_per_unit': cell(3),
                    'cooling_capacity_unit': cell(4).lower() or 'kw',
                    'number_of_units':       cell(5),
                    'baseline_leakage_factor': leakage,
                    'hours_per_day':         cell(7),
                    'days_per_week':         cell(8),
                    'weeks_per_year':        cell(9),
                    'power_input_per_unit':  cell(10),
                    'eer_iseer_cop':         cell(11),
                    'energy_efficiency_label': cell(12),
                    'number_of_stars':       cell(13),
                }

            # Auto-calculate annual energy consumption
            row_data['total_energy_consumption_annually'] = _calc_ac_energy(row_data)
            results.append(row_data)

        else:  # chiller
            year = cell(0)
            if not year:
                continue  # skip empty row
            leakage = cell(5) or _leakage_default(year)

            if chiller_type == 'water_cooled':
                row_data = {
                    'cooling_system_type':                              'chiller',
                    'chiller_system':                                   'water_cooled',
                    'year_of_installation':                             year,
                    'type_of_refrigerants':                             cell(1),
                    'refrigerant_quantity':                             cell(2),
                    'total_cooling_load':                               cell(3),
                    'number_of_chillers':                               cell(4),
                    'baseline_leakage_factor':                          leakage,
                    'annual_operating_hours_per_day':                   cell(6),
                    'annual_operating_days_per_week':                   cell(7),
                    'annual_operating_weeks_per_year':                  cell(8),
                    'baseline_cooling_efficiency':                      cell(9),
                    'installation_of_variable_speed_drives':            cell(10),
                    'installation_of_heat_recovery_systems':            cell(11),
                    'ipvl':                                             cell(12),
                    'water_cooled_chiller_cooling_load_factor':         cell(13),
                    'total_chiller_system_power_input':                 cell(14),
                    'cop':                                              cell(15),
                    'energy_efficiency_label':                          cell(16),
                    'number_of_stars':                                  cell(17),
                }
            else:  # air_cooled
                row_data = {
                    'cooling_system_type':                              'chiller',
                    'chiller_system':                                   'air_cooled',
                    'year_of_installation':                             year,
                    'type_of_refrigerants':                             cell(1),
                    'refrigerant_quantity':                             cell(2),
                    'total_cooling_load':                               cell(3),
                    'number_of_chillers':                               cell(4),
                    'baseline_leakage_factor':                          leakage,
                    'annual_operating_hours_per_day':                   cell(6),
                    'annual_operating_days_per_week':                   cell(7),
                    'annual_operating_weeks_per_year':                  cell(8),
                    'baseline_cooling_efficiency':                      cell(9),
                    'installation_of_variable_speed_drives':            cell(10),
                    'installation_of_heat_recovery_systems':            cell(11),
                    'ipvl':                                             cell(12),
                    'total_chiller_system_power_input':                 cell(13),
                    'cop':                                              cell(14),
                    'energy_efficiency_label':                          cell(15),
                    'number_of_stars':                                  cell(16),
                }

            # Auto-calculate annual energy consumption
            row_data['total_energy_consumption_of_chiller_system_annually'] = _calc_chiller_energy(row_data)
            results.append(row_data)

    return results


@login_required
@require_http_methods(["POST"])
def import_cooling_systems(request):
    """
    Process all cooling system tabs from the import template.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {
                "tab": "window ac" | "split ac" | "vrf" | "packagedductab" |
                       "water cooled" | "air cooled",
                "rows": [ [col0, col1, ...], ... ]   // raw cell values, one list per data row
            },
            ...
        ]
    }

    Each row is validated through the same Django forms used by the normal UI.
    All errors are collected and returned together (no partial saves on error).
    If all tabs are empty, returns success immediately (cooling is optional).
    """
    import json
    from django.db import transaction

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    systems_payload = data.get("systems", [])

    # --- Parse all tabs into validated form data ---
    all_errors = {}   # tab_label -> {row_index -> {field: error}}
    to_save = []      # list of (form_instance, cooling_system_type)

    for tab_entry in systems_payload:
        tab_name = _str(tab_entry.get("tab", "")).lower().replace(" ", "")
        raw_rows = tab_entry.get("rows", [])

        # Normalise tab key for lookup
        tab_key = None
        for key in COOLING_TAB_MAP:
            if key.replace(" ", "") in tab_name or tab_name in key.replace(" ", ""):
                tab_key = key
                break

        if tab_key is None:
            continue  # unknown tab — skip silently

        parsed_rows = _parse_cooling_rows(tab_key, raw_rows)

        for row_idx, row_data in enumerate(parsed_rows):
            ctype = row_data.pop("cooling_system_type")
            label = f"{tab_entry.get('tab', tab_key)} row {row_idx + 1}"

            if ctype == 'chiller':
                form = CoolingSystemChillerForm(row_data)
            else:
                form = CoolingSystemAirConditionerForm(row_data)

            if form.is_valid():
                to_save.append((form, ctype))
            else:
                all_errors[label] = {
                    field: [str(e) for e in errs]
                    for field, errs in form.errors.items()
                }

    if all_errors:
        return JsonResponse({"success": False, "errors": all_errors}, status=400)

    # --- All valid — save inside one transaction ---
    with transaction.atomic():
        for form, ctype in to_save:
            system = form.save(commit=False)
            system.building = building
            system.save()  # model.save() auto-populates baseline_refrigerant_emission_factor

    saved_count = len(to_save)
    logger.info(
        f"Import cooling: {saved_count} system(s) saved for building {building.uuid} by {request.user}"
    )

    return JsonResponse({
        "success": True,
        "saved_count": saved_count,
        "building_uuid": str(building.uuid),
    })


# ---------------------------------------------------------------------------
# Ventilation Systems (Tabs 9–13)
# ---------------------------------------------------------------------------

# Maps Excel sheet name fragment → VentilationType value
VENTILATION_TAB_MAP = {
    'ahu':        VentilationType.AHU,
    'fcu':        VentilationType.FCU,
    'ceilingwa':  VentilationType.CASSETTE_AC,   # Ceiling/Wall Cassette AC
    'doas':       VentilationType.DOAS,
    'ceilingex':  VentilationType.FAN,            # Ceiling/Exhaust/Wall Fan
}

# Which ventilation types have VSD + DCV fields (AHU, DOAS)
VENT_HAS_VSD_DCV = {VentilationType.AHU, VentilationType.DOAS}

# Which ventilation types have a fresh_air_ratio column (Cassette only)
VENT_HAS_FRESH_AIR = {VentilationType.CASSETTE_AC}

# Which ventilation types have power_input in the template (FCU, Cassette, Fan)
# AHU and DOAS compute power_input from airflow × efficiency × units / 1000
VENT_HAS_POWER_INPUT = {VentilationType.FCU, VentilationType.CASSETTE_AC, VentilationType.FAN}

# Which ventilation types have a number_of_stars column (Fan only)
VENT_HAS_STARS = {VentilationType.FAN}

# Airflow capacity unit label → VentilationCapacity model value
VENT_CAPACITY_MAP = {
    'cmh': VentilationCapacity.M3H,
    'm3h': VentilationCapacity.M3H,
    'cfm': VentilationCapacity.F3M,
    'f3m': VentilationCapacity.F3M,
}


def _calc_vent_power(airflow, efficiency, units):
    """
    Auto-calculate total ventilation system power input (kW) for AHU/DOAS.
    Formula: airflow (CMH) × efficiency (W/CMH) × units / 1000
    Returns float or None if inputs are invalid.
    """
    try:
        a = float(airflow)
        e = float(efficiency)
        u = float(units)
        if a > 0 and e > 0 and u > 0:
            return round((a * e * u) / 1000, 4)
    except (ValueError, TypeError):
        pass
    return None


def _calc_vent_energy(power, hours, days, weeks, vsd=False, dcv=False):
    """
    Auto-calculate total annual energy consumption (kWh/year) for ventilation.

    AHU/DOAS formula:  power × h × d × w × vsd_factor × dcv_factor
      vsd_factor = 0.80 if VSD=yes else 1.00
      dcv_factor = 0.70 if DCV=yes else 1.00
    FCU/Cassette/Fan:  power × h × d × w

    Returns rounded int or None if inputs are invalid.
    """
    try:
        p = float(power)
        h = float(hours)
        d = float(days)
        w = float(weeks)
        if p <= 0 or h <= 0 or d <= 0 or w <= 0:
            return None
        vsd_factor = 0.80 if vsd else 1.00
        dcv_factor = 0.70 if dcv else 1.00
        return round(Decimal(str(p * h * d * w * vsd_factor * dcv_factor)), 3)
    except (ValueError, TypeError):
        return None


def _parse_ventilation_rows(vent_type, raw_rows):
    """
    Parse data rows for a single ventilation tab.
    Returns list of dicts ready to pass to VentilationSystemForm.
    Skips rows where number_of_units is blank.

    Column layouts (0-based):

    AHU / DOAS (with VSD + DCV):
      0:units  1:baseline_efficiency  2:vsd  3:dcv  4:hours  5:days  6:weeks
      7:airflow  8:airflow_unit  9:energy(auto, ignored)

    FCU:
      0:units  1:baseline_efficiency  2:hours  3:days  4:weeks
      5:power_input  6:airflow  7:airflow_unit  8:energy(auto, ignored)

    Cassette AC (extra fresh_air_ratio at col 1):
      0:units  1:fresh_air_ratio  2:baseline_efficiency  3:hours  4:days  5:weeks
      6:power_input  7:airflow  8:airflow_unit  9:energy(auto, ignored)

    Fan (extra stars before energy):
      0:units  1:baseline_efficiency  2:hours  3:days  4:weeks
      5:power_input  6:airflow  7:airflow_unit  8:stars  9:energy(auto, ignored)

    Auto-calculated:
    - AHU/DOAS: total_power_input_kw = airflow × efficiency × units / 1000
    - All types: total_energy_consumption_kwh_per_year = power × h × d × w [× factors]
    """
    results = []

    for row in raw_rows:
        def cell(idx, default=''):
            val = row[idx] if idx < len(row) else None
            if val is None or str(val).strip().lower() == 'none':
                return default
            return str(val).strip()

        def yes(idx):
            return cell(idx).lower() in ('yes', 'true', '1')

        # All tabs: col 0 = number_of_units (skip if blank)
        units_raw = cell(0)
        if not units_raw:
            continue

        row_data = {'ventilation_type': vent_type}

        if vent_type in VENT_HAS_VSD_DCV:
            # AHU / DOAS layout
            row_data['number_of_units']          = units_raw
            row_data['baseline_efficiency']       = cell(1)
            row_data['variable_speed_drives']     = 'yes' if yes(2) else 'no'
            row_data['demand_controlled_ventilation'] = 'yes' if yes(3) else 'no'
            row_data['operating_hours_per_day']   = cell(4)
            row_data['operating_days_per_week']   = cell(5)
            row_data['operating_weeks_per_year']  = cell(6)
            row_data['airflow_rate']              = cell(7)
            airflow_unit_raw = cell(8).lower()

            # Auto-calculate power_input from airflow × efficiency × units / 1000
            computed_power = _calc_vent_power(cell(7), cell(1), units_raw)
            if computed_power is not None:
                row_data['power_input'] = str(computed_power)

            # Auto-calculate annual energy
            computed_energy = _calc_vent_energy(
                row_data.get('power_input', ''),
                cell(4), cell(5), cell(6),
                vsd=yes(2), dcv=yes(3),
            )
            if computed_energy is not None:
                row_data['annual_energy_consumption'] = str(computed_energy)

        elif vent_type == VentilationType.CASSETTE_AC:
            # Cassette layout (fresh_air_ratio at col 1, shifts everything by 1)
            row_data['number_of_units']          = units_raw
            row_data['fresh_air_ratio']           = cell(1)
            row_data['baseline_efficiency']       = cell(2)
            row_data['operating_hours_per_day']   = cell(3)
            row_data['operating_days_per_week']   = cell(4)
            row_data['operating_weeks_per_year']  = cell(5)
            row_data['power_input']               = cell(6)
            row_data['airflow_rate']              = cell(7)
            airflow_unit_raw = cell(8).lower()

            computed_energy = _calc_vent_energy(cell(6), cell(3), cell(4), cell(5))
            if computed_energy is not None:
                row_data['annual_energy_consumption'] = str(computed_energy)

        elif vent_type == VentilationType.FAN:
            # Fan layout (stars at col 8 before energy)
            row_data['number_of_units']          = units_raw
            row_data['baseline_efficiency']       = cell(1)
            row_data['operating_hours_per_day']   = cell(2)
            row_data['operating_days_per_week']   = cell(3)
            row_data['operating_weeks_per_year']  = cell(4)
            row_data['power_input']               = cell(5)
            row_data['airflow_rate']              = cell(6)
            airflow_unit_raw = cell(7).lower()
            row_data['number_of_stars']           = cell(8)

            computed_energy = _calc_vent_energy(cell(5), cell(2), cell(3), cell(4))
            if computed_energy is not None:
                row_data['annual_energy_consumption'] = str(computed_energy)

        else:
            # FCU layout
            row_data['number_of_units']          = units_raw
            row_data['baseline_efficiency']       = cell(1)
            row_data['operating_hours_per_day']   = cell(2)
            row_data['operating_days_per_week']   = cell(3)
            row_data['operating_weeks_per_year']  = cell(4)
            row_data['power_input']               = cell(5)
            row_data['airflow_rate']              = cell(6)
            airflow_unit_raw = cell(7).lower()

            computed_energy = _calc_vent_energy(cell(5), cell(2), cell(3), cell(4))
            if computed_energy is not None:
                row_data['annual_energy_consumption'] = str(computed_energy)

        # Resolve airflow capacity unit
        vent_capacity = VENT_CAPACITY_MAP.get(airflow_unit_raw)
        if vent_capacity:
            row_data['ventilation_capacity'] = vent_capacity

        results.append(row_data)

    return results


@login_required
@require_http_methods(["POST"])
def import_ventilation_systems(request):
    """
    Process all ventilation system tabs from the import template.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {
                "tab": "ahu" | "fcu" | "ceilingwa" | "doas" | "ceilingex",
                "rows": [ [col0, col1, ...], ... ]
            },
            ...
        ]
    }

    Validated through VentilationSystemForm (same as normal UI).
    All-or-nothing save. Empty tabs are silently skipped.
    """
    import json
    from django.db import transaction
    from pages.models.building_operation import VentilationSystem

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    systems_payload = data.get("systems", [])
    all_errors = {}
    to_save = []

    for tab_entry in systems_payload:
        tab_name = _str(tab_entry.get("tab", "")).lower().strip()
        raw_rows = tab_entry.get("rows", [])

        # Match tab name to a ventilation type
        vent_type = None
        for key, vtype in VENTILATION_TAB_MAP.items():
            if key in tab_name or tab_name in key:
                vent_type = vtype
                break

        if vent_type is None:
            continue  # unknown tab — skip silently

        parsed_rows = _parse_ventilation_rows(vent_type, raw_rows)

        for row_idx, row_data in enumerate(parsed_rows):
            label = f"{tab_entry.get('tab', tab_name)} row {row_idx + 1}"
            form = VentilationSystemForm(row_data)

            if form.is_valid():
                to_save.append(form)
            else:
                all_errors[label] = {
                    field: [str(e) for e in errs]
                    for field, errs in form.errors.items()
                }

    if all_errors:
        return JsonResponse({"success": False, "errors": all_errors}, status=400)

    with transaction.atomic():
        for form in to_save:
            system = form.save(commit=False)
            system.building = building
            system.save()

    saved_count = len(to_save)
    logger.info(
        f"Import ventilation: {saved_count} system(s) saved for building {building.uuid} by {request.user}"
    )

    return JsonResponse({
        "success": True,
        "saved_count": saved_count,
        "building_uuid": str(building.uuid),
    })


# ---------------------------------------------------------------------------
# Lighting System import
# ---------------------------------------------------------------------------

# Maps Excel sheet name fragment → which layout to use
# 'led'          → LED tab (no tubes, wattage per fixture)
# 'fluorescent'  → Fluorescent tab (has tubes_per_fixture + wattage per tube)
# 'cfl'          → CFL tab (no tubes, bulb type always CFL)
# 'incandescent' → Incandescent tab (no tubes, Incandescent or Halogen sub-type)
# 'hid'          → HiD tab (no tubes, no sensors column, Metal Halide or HPS)
LIGHTING_TAB_LAYOUT = {
    'led':          'led',
    'fluorescent':  'fluorescent',
    'cfl':          'cfl',
    'incandescent': 'incandescent',
    'hid':          'hid',
}

# Maps the "Type of lighting system" column value → LightingBulbType model value
# All comparisons are done after .lower().strip()
LIGHTING_BULB_TYPE_MAP = {
    # LED variants
    'led panel':                       LightingBulbType.LED_PANEL,
    'led tube':                        LightingBulbType.LED_TUBE,
    'led downlight':                   LightingBulbType.LED_DOWNLIGHT,
    'led bulb':                        LightingBulbType.LED_BULB,
    'led (light emitting diode) lights': LightingBulbType.LED_BULB,
    'led strip':                       LightingBulbType.LED_STRIP,
    # Fluorescent variants
    'fluorescent t5':                  LightingBulbType.FLUORESCENT_T5,
    'fluorescent t8':                  LightingBulbType.FLUORESCENT_T8,
    'fluorescent t12':                 LightingBulbType.FLUORESCENT_T12,
    # CFL
    'cfl':                             LightingBulbType.CFL,
    'compact fluorescent lamp':        LightingBulbType.CFL,
    # Incandescent / Halogen
    'incandescent':                    LightingBulbType.INCANDESCENT,
    'halogen':                         LightingBulbType.HALOGEN,
    # HiD
    'metal halide':                    LightingBulbType.METAL_HALIDE,
    'high-pressure sodium':            LightingBulbType.HIGH_PRESSURE_SODIUM,
    'high pressure sodium':            LightingBulbType.HIGH_PRESSURE_SODIUM,
}

# Default bulb type per tab if the "type" column is missing/unrecognised
LIGHTING_TAB_DEFAULT_BULB = {
    'led':          LightingBulbType.LED_BULB,
    'fluorescent':  LightingBulbType.FLUORESCENT_T8,
    'cfl':          LightingBulbType.CFL,
    'incandescent': LightingBulbType.INCANDESCENT,
    'hid':          LightingBulbType.METAL_HALIDE,
}

# Maps Excel room type label (lower) → RoomType model value
ROOM_TYPE_MAP = {
    # Direct matches (model display text)
    'office: conference room':                    RoomType.OFFICE_CONFERENCE,
    'hospital: patient room':                     RoomType.HOSPITAL_PATIENT,
    'residential: kitchen':                       RoomType.RESIDENTIAL_KITCHEN,
    'residential: dining room':                   RoomType.RESIDENTIAL_DINING,
    'commercial: general office/retail':          RoomType.COMMERCIAL_GENERAL,
    'commercial: mall / department store':        RoomType.COMMERCIAL_MALL,
    # Partial / combined matches
    'office':                                     RoomType.OFFICE_CONFERENCE,
    'conference':                                 RoomType.OFFICE_CONFERENCE,
    'hospital':                                   RoomType.HOSPITAL_PATIENT,
    'patient':                                    RoomType.HOSPITAL_PATIENT,
    'residential: kitchen, dining, bedroom, bathroom': RoomType.RESIDENTIAL_KITCHEN,
    'kitchen':                                    RoomType.RESIDENTIAL_KITCHEN,
    'dining':                                     RoomType.RESIDENTIAL_DINING,
    'bedroom':                                    RoomType.RESIDENTIAL_KITCHEN,
    'commercial':                                 RoomType.COMMERCIAL_GENERAL,
    'mall':                                       RoomType.COMMERCIAL_MALL,
    'retail':                                     RoomType.COMMERCIAL_GENERAL,
}

# Maps Excel energy efficiency label → EnergyEfficiencyLabelType model value
ENERGY_LABEL_MAP = {
    'bee':         EnergyEfficiencyLabelType.BEE,
    'bee star':    EnergyEfficiencyLabelType.BEE,
    'egat':        EnergyEfficiencyLabelType.EGAT,
    'esdm':        EnergyEfficiencyLabelType.ESDM,
    'others':      EnergyEfficiencyLabelType.OTHERS,
    'other':       EnergyEfficiencyLabelType.OTHERS,
}


def _calc_lighting_power(fixtures, tubes, wattage):
    """
    Auto-calculate total lighting power (kW).
    Formula: fixtures × tubes × wattage / 1000
    tubes defaults to 1 when not applicable.
    Returns float or None.
    """
    try:
        f = float(fixtures)
        t = float(tubes) if tubes else 1.0
        w = float(wattage)
        if f > 0 and t >= 1 and w > 0:
            return round((f * t * w) / 1000, 4)
    except (ValueError, TypeError):
        pass
    return None


def _calc_lighting_lpd(total_power_kw, area):
    """
    Auto-calculate baseline LPD = total_power (kW) / area (m²).
    Returns Decimal or None.
    """
    try:
        p = float(total_power_kw)
        a = float(area)
        if p > 0 and a > 0:
            return round(p / a, 6)
    except (ValueError, TypeError):
        pass
    return None


def _calc_lighting_energy(total_power_kw, hours, days, weeks, sensors):
    """
    Auto-calculate annual energy consumption (kWh/year).
    Formula: total_power × hours × days × weeks × sensor_factor
    sensor_factor = 0.80 if sensors installed, else 1.00
    Returns rounded int or None.
    """
    try:
        p = float(total_power_kw)
        h = float(hours)
        d = float(days)
        w = float(weeks)
        if p <= 0 or h <= 0 or d <= 0 or w <= 0:
            return None
        sensor_factor = 0.80 if sensors else 1.00
        return round(Decimal(str(p * h * d * w * sensor_factor)), 3)
    except (ValueError, TypeError):
        return None


def _parse_lighting_rows(tab_layout, raw_rows):
    """
    Parse data rows for a single lighting tab.
    Returns list of dicts ready to pass to LightingSystemForm.
    Skips rows where number_of_fixtures (col 3) is blank.

    Column layouts (0-based, all tabs):
      0: room_type
      1: area_of_room
      2: type_of_lighting_system  (→ lighting_bulb_type)
      3: total_number_of_fixtures (→ number_of_bulbs)

    Then diverges by tab:
      LED:          4:wattage  5:hours  6:days  7:weeks  8:sensors  9:label  10:stars
      Fluorescent:  4:tubes    5:wattage  6:hours  7:days  8:weeks  9:sensors  10:label  11:stars
      CFL:          4:wattage  5:hours  6:days  7:weeks  8:sensors  9:label  10:stars
      Incandescent: 4:wattage  5:hours  6:days  7:weeks  8:sensors  9:label  10:stars
      HiD:          4:wattage  5:hours  6:days  7:weeks  8:label    9:stars   (no sensors)
    """
    results = []

    for raw_row in raw_rows:
        # raw_row is a list; extend with Nones to avoid IndexError
        row = list(raw_row) + [None] * 15

        def cell(i):
            v = row[i]
            if v is None:
                return ''
            return str(v).strip()

        # Skip rows without fixture count
        fixtures_raw = cell(3)
        if not fixtures_raw:
            continue

        row_data = {}

        # --- Room type ---
        room_label = cell(0).lower()
        room_type_val = None
        for label, val in ROOM_TYPE_MAP.items():
            if label in room_label or room_label in label:
                room_type_val = val
                break
        if room_type_val:
            row_data['room_type'] = room_type_val

        # --- Area ---
        row_data['area_of_room'] = cell(1)

        # --- Lighting bulb type (col 2: "Type of lighting system") ---
        bulb_label = cell(2).lower()
        bulb_type = LIGHTING_BULB_TYPE_MAP.get(bulb_label)
        if bulb_type is None:
            # Try partial match
            for label, val in LIGHTING_BULB_TYPE_MAP.items():
                if label in bulb_label or bulb_label in label:
                    bulb_type = val
                    break
        if bulb_type is None:
            # Use tab-default
            bulb_type = LIGHTING_TAB_DEFAULT_BULB.get(tab_layout)
        if bulb_type:
            row_data['lighting_bulb_type'] = bulb_type

        # --- Fixtures ---
        row_data['number_of_bulbs'] = fixtures_raw

        # --- Per-tab column layout ---
        if tab_layout == 'fluorescent':
            tubes_raw  = cell(4)
            wattage    = cell(5)
            hours      = cell(6)
            days       = cell(7)
            weeks      = cell(8)
            sensors    = _bool_from_excel(cell(9))
            label_raw  = cell(10)
            stars_raw  = cell(11)
        elif tab_layout == 'hid':
            tubes_raw  = None
            wattage    = cell(4)
            hours      = cell(5)
            days       = cell(6)
            weeks      = cell(7)
            sensors    = False  # HiD tab has no sensors column
            label_raw  = cell(8)
            stars_raw  = cell(9)
        else:
            # LED, CFL, Incandescent share the same layout
            tubes_raw  = None
            wattage    = cell(4)
            hours      = cell(5)
            days       = cell(6)
            weeks      = cell(7)
            sensors    = _bool_from_excel(cell(8))
            label_raw  = cell(9)
            stars_raw  = cell(10)

        row_data['light_bulb_power_rating_w'] = wattage
        row_data['operation_hours_per_workday'] = hours
        row_data['workdays_per_week'] = days
        row_data['workweeks_per_year'] = weeks
        row_data['sensors_installed'] = 'yes' if sensors else 'no'

        if tubes_raw:
            row_data['tubes_per_fixture'] = tubes_raw

        # --- Auto-calculated fields ---
        total_power = _calc_lighting_power(fixtures_raw, tubes_raw, wattage)
        if total_power is not None:
            row_data['total_lighting_power_kw'] = str(total_power)
            lpd = _calc_lighting_lpd(total_power, cell(1))
            if lpd is not None:
                row_data['baseline_lighting_power_density'] = str(lpd)
            energy = _calc_lighting_energy(total_power, hours, days, weeks, sensors)
            if energy is not None:
                row_data['total_energy_consumption_kwh_per_year'] = str(energy)

        # --- Energy efficiency label ---
        label_str = label_raw.lower()
        label_type = ENERGY_LABEL_MAP.get(label_str)
        if label_type is None:
            for key, val in ENERGY_LABEL_MAP.items():
                if key in label_str:
                    label_type = val
                    break
        if label_type:
            row_data['energy_efficiency_label'] = label_type

        # --- Stars ---
        if stars_raw:
            row_data['number_of_stars'] = stars_raw

        results.append(row_data)

    return results


@login_required
@require_http_methods(["POST"])
def import_lighting_systems(request):
    """
    Process all lighting system tabs from the import template.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {
                "tab": "led" | "fluorescent" | "cfl" | "incandescent" | "hid",
                "rows": [ [col0, col1, ...], ... ]
            },
            ...
        ]
    }

    Validated through LightingSystemForm (same as normal UI).
    All-or-nothing save. Empty tabs are silently skipped.
    """
    import json
    from django.db import transaction
    from pages.models.building_operation import LightingSystem

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    systems_payload = data.get("systems", [])
    all_errors = {}
    to_save = []

    for tab_entry in systems_payload:
        tab_name = _str(tab_entry.get("tab", "")).lower().strip()
        raw_rows = tab_entry.get("rows", [])

        # Match tab name to a layout key
        tab_layout = None
        for key in LIGHTING_TAB_LAYOUT:
            if key in tab_name or tab_name in key:
                tab_layout = key
                break

        if tab_layout is None:
            continue  # unknown tab — skip silently

        parsed_rows = _parse_lighting_rows(tab_layout, raw_rows)

        for row_idx, row_data in enumerate(parsed_rows):
            label = f"{tab_entry.get('tab', tab_name)} row {row_idx + 1}"
            form = LightingSystemForm(row_data)

            if form.is_valid():
                to_save.append(form)
            else:
                all_errors[label] = {
                    field: [str(e) for e in errs]
                    for field, errs in form.errors.items()
                }

    if all_errors:
        return JsonResponse({"success": False, "errors": all_errors}, status=400)

    with transaction.atomic():
        for form in to_save:
            system = form.save(commit=False)
            system.building = building
            system.save()

    saved_count = len(to_save)
    logger.info(
        f"Import lighting: {saved_count} system(s) saved for building {building.uuid} by {request.user}"
    )

    return JsonResponse({
        "success": True,
        "saved_count": saved_count,
        "building_uuid": str(building.uuid),
    })


# ---------------------------------------------------------------------------
# Lift & Escalator System import
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def import_lift_escalator_system(request):
    """
    Process the Lift & Escalator System tab from the import template.

    Only one lift & escalator system is allowed per building (same as normal UI).
    If the template row is empty/blank, the step is silently skipped.

    Expects JSON:
    {
        "building_uuid": str,
        "rows": [ [col0_number_of_lifts, col1_regen, col2_vvvf], ... ]
    }

    Column layout (0-based):
      0: number_of_lifts
      1: lift_regenerative_features  ("Yes"/"No")
      2: vvvf_sleep_mode             ("Yes"/"No")

    Annual energy is optional and not present in the Excel template
    (it is pre-filled in the UI from total_kwh × 7.5%).
    """
    import json
    from django.db import transaction
    from pages.models.building_operation import LiftEscalatorSystem

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    raw_rows = data.get("rows", [])

    # Find the first non-empty row (number_of_lifts at col 0 must be present)
    row_data = None
    for raw_row in raw_rows:
        row = list(raw_row) + [None] * 5
        num_lifts_raw = _str(row[0])
        if num_lifts_raw:
            row_data = {
                'number_of_lifts':           num_lifts_raw,
                'lift_regenerative_features': _str(row[1]) or 'no',
                'vvvf_sleep_mode':            _str(row[2]) or 'no',
            }
            break

    if row_data is None:
        # No data — silently skip
        return JsonResponse({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

    existing = LiftEscalatorSystem.objects.filter(building=building).first()
    form = LiftEscalatorSystemForm(row_data, instance=existing)
    if not form.is_valid():
        return JsonResponse({"success": False, "errors": dict(form.errors)}, status=400)

    with transaction.atomic():
        system = form.save(commit=False)
        system.building = building
        system.save()

    logger.info(f"Import lift: system saved for building {building.uuid} by {request.user}")
    return JsonResponse({"success": True, "saved_count": 1, "building_uuid": str(building.uuid)})


# ---------------------------------------------------------------------------
# Hot Water System import
# ---------------------------------------------------------------------------

# Maps Excel sheet name fragment → HotWaterSystemType model value
HOT_WATER_TAB_MAP = {
    'heat-pump':  HotWaterSystemType.HEAT_PUMP,
    'heatpump':   HotWaterSystemType.HEAT_PUMP,
    'heat pump':  HotWaterSystemType.HEAT_PUMP,
    'boiler':     HotWaterSystemType.BOILER,
    'solar':        HotWaterSystemType.SOLAR,
    'water heat':   HotWaterSystemType.SOLAR,   # "Water Heater" tab → 'solar' type
    'waterheate':   HotWaterSystemType.SOLAR,
    'water-heater': HotWaterSystemType.SOLAR,
}

# Maps Excel fuel type text (lower) → FuelType model value
FUEL_TYPE_MAP = {
    'electricity':        FuelType.ELECTRICITY,
    'natural gas':        FuelType.NATURAL_GAS,
    'natural-gas':        FuelType.NATURAL_GAS,
    'lpg':                FuelType.LPG,
    'diesel':             FuelType.DIESEL,
    'kerosene':           FuelType.KEROSENE,
    'coal':               FuelType.COAL,
    'solar':              FuelType.SOLAR,
    'light fuel oil':     FuelType.LIGHT_FUEL_OIL,
    'light-fuel-oil':     FuelType.LIGHT_FUEL_OIL,
    'heavy fuel oil':     FuelType.HEAVY_FUEL_OIL,
    'heavy-fuel-oil':     FuelType.HEAVY_FUEL_OIL,
    'lignite':            FuelType.LIGNITE,
    'fire wood (log wood)':   FuelType.FIRE_WOOD_LOG,
    'fire-wood-log':          FuelType.FIRE_WOOD_LOG,
    'firewood':               FuelType.FIRE_WOOD_LOG,
    'fire wood (wood chips)': FuelType.FIRE_WOOD_CHIPS,
    'fire-wood-chips':        FuelType.FIRE_WOOD_CHIPS,
    'wood chips':             FuelType.FIRE_WOOD_CHIPS,
    'fire wood (wood pellets)': FuelType.FIRE_WOOD_PELLETS,
    'fire-wood-pellets':      FuelType.FIRE_WOOD_PELLETS,
    'wood pellets':           FuelType.FIRE_WOOD_PELLETS,
    'charcoal':               FuelType.CHAR_COAL,
    'char-coal':              FuelType.CHAR_COAL,
    'char coal':              FuelType.CHAR_COAL,
    'ignite':                 FuelType.IGNITE,
    'none':                   FuelType.NONE,
    'other':                  FuelType.OTHER,
}


def _calc_hws_energy(system_type, power, num, hours, days, weeks, cop_or_eff, fuel_type=''):
    """
    Auto-calculate total annual energy consumption (kWh/year) for hot water systems.

    Heat Pump:   power × num × h × d × w / COP
    Boiler:      power × num × h × d × w / (efficiency% / 100)
    Water Heater (solar): 0
    Water Heater (other): power × num × h × d × w / (efficiency% / 100)

    Returns rounded int or None if inputs are insufficient.
    """
    try:
        p = float(power)
        n = float(num)
        h = float(hours)
        d = float(days)
        w = float(weeks)
        e = float(cop_or_eff)
        if p <= 0 or n <= 0 or h <= 0 or d <= 0 or w <= 0 or e <= 0:
            return None

        base = p * n * h * d * w

        if system_type == HotWaterSystemType.HEAT_PUMP:
            # Divide by COP (dimensionless)
            result = base / e
        elif system_type == HotWaterSystemType.SOLAR and str(fuel_type).lower() == 'solar':
            result = 0
        else:
            # Boiler or Water Heater: divide by (efficiency% / 100)
            result = base / (e / 100)

        return round(Decimal(str(result)), 3)
    except (ValueError, TypeError):
        return None


def _parse_hot_water_rows(hws_type, raw_rows):
    """
    Parse data rows for a single hot water system tab.
    Returns list of dicts ready to pass to HotWaterSystemForm.
    Skips rows where number_of_equipment (col 2) is blank.

    Column layouts (0-based):

    Heat Pump:
      0: type_of_hot_water_system  1: fuel_type  2: number_of_equipment
      3: hours  4: days  5: weeks  6: COP (baseline_efficiency)
      7: power_input  8: heat_recovery  9: equipment_efficiency_level
      (energy auto-calculated)

    Boiler:
      0: type_of_hot_water_system  1: fuel_type  2: number_of_equipment
      3: hours  4: days  5: weeks  6: power_input
      7: total_fuel_consumption  8: fuel_consumption_unit
      9: heat_recovery  10: equipment_efficiency_level
      (energy auto-calculated)

    Water Heater:
      0: type_of_hot_water_system  1: fuel_type  2: number_of_equipment
      3: hours  4: days  5: weeks  6: power_input
      7: heat_recovery  8: equipment_efficiency_level
      (energy auto-calculated)
    """
    results = []

    for raw_row in raw_rows:
        row = list(raw_row) + [None] * 15

        def cell(i):
            v = row[i]
            if v is None:
                return ''
            return str(v).strip()

        # Skip rows without number_of_equipment (col 2)
        num_eq_raw = cell(2)
        if not num_eq_raw:
            continue

        row_data = {}

        # --- System type (from tab) ---
        row_data['type_of_hot_water_system'] = hws_type

        # --- Fuel type (col 1) ---
        fuel_raw = cell(1).lower()
        fuel_val = FUEL_TYPE_MAP.get(fuel_raw)
        if fuel_val is None:
            for label, val in FUEL_TYPE_MAP.items():
                if label in fuel_raw or fuel_raw in label:
                    fuel_val = val
                    break
        if fuel_val:
            row_data['fuel_type'] = fuel_val

        row_data['number_of_equipment'] = num_eq_raw

        if hws_type == HotWaterSystemType.HEAT_PUMP:
            hours = cell(3)
            days  = cell(4)
            weeks = cell(5)
            cop   = cell(6)
            power = cell(7)
            heat_recovery = cell(8)
            eff_level     = cell(9)

            row_data['operating_hours_per_day']   = hours
            row_data['operating_days_per_week']   = days
            row_data['operating_weeks_per_year']  = weeks
            row_data['baseline_efficiency']        = cop
            row_data['power_input']                = power
            row_data['heat_recovery_system']       = heat_recovery or 'no'
            row_data['equipment_efficiency_level'] = eff_level

            energy = _calc_hws_energy(hws_type, power, num_eq_raw, hours, days, weeks, cop)

        elif hws_type == HotWaterSystemType.BOILER:
            hours    = cell(3)
            days     = cell(4)
            weeks    = cell(5)
            power    = cell(6)
            fuel_cons      = cell(7)
            fuel_cons_unit = cell(8)
            heat_recovery  = cell(9)
            eff_level      = cell(10)

            row_data['operating_hours_per_day']   = hours
            row_data['operating_days_per_week']   = days
            row_data['operating_weeks_per_year']  = weeks
            row_data['power_input']                = power
            if fuel_cons:
                row_data['total_fuel_consumption'] = fuel_cons
            if fuel_cons_unit:
                row_data['fuel_consumption_unit']  = fuel_cons_unit
            row_data['heat_recovery_system']       = heat_recovery or 'no'
            row_data['equipment_efficiency_level'] = eff_level
            # Boiler uses efficiency % as divider, no COP → set baseline_efficiency = eff_level
            row_data['baseline_efficiency']        = eff_level

            energy = _calc_hws_energy(hws_type, power, num_eq_raw, hours, days, weeks, eff_level)

        else:
            # Water Heater (solar type)
            hours    = cell(3)
            days     = cell(4)
            weeks    = cell(5)
            power    = cell(6)
            heat_recovery = cell(7)
            eff_level     = cell(8)
            fuel_val_str  = str(row_data.get('fuel_type', '')).lower()

            row_data['operating_hours_per_day']   = hours
            row_data['operating_days_per_week']   = days
            row_data['operating_weeks_per_year']  = weeks
            row_data['power_input']                = power
            row_data['heat_recovery_system']       = heat_recovery or 'no'
            row_data['equipment_efficiency_level'] = eff_level
            row_data['baseline_efficiency']        = eff_level

            energy = _calc_hws_energy(hws_type, power, num_eq_raw, hours, days, weeks, eff_level,
                                      fuel_type=fuel_val_str)

        if energy is not None:
            row_data['total_energy_consumption_kwh_per_year'] = str(energy)

        results.append(row_data)

    return results


@login_required
@require_http_methods(["POST"])
def import_hot_water_systems(request):
    """
    Process all hot water system tabs from the import template.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {
                "tab": "heat-pump" | "boiler" | "water-heater",
                "rows": [ [col0, col1, ...], ... ]
            },
            ...
        ]
    }

    Validated through HotWaterSystemForm (same as normal UI).
    All-or-nothing save. Empty tabs are silently skipped.
    """
    import json
    from django.db import transaction

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    systems_payload = data.get("systems", [])
    all_errors = {}
    to_save = []

    for tab_entry in systems_payload:
        tab_name = _str(tab_entry.get("tab", "")).lower().strip()
        raw_rows = tab_entry.get("rows", [])

        # Match tab name to a HotWaterSystemType
        hws_type = None
        for key, val in HOT_WATER_TAB_MAP.items():
            if key in tab_name or tab_name in key:
                hws_type = val
                break

        if hws_type is None:
            continue  # unknown tab — skip silently

        parsed_rows = _parse_hot_water_rows(hws_type, raw_rows)

        for row_idx, row_data in enumerate(parsed_rows):
            label = f"{tab_entry.get('tab', tab_name)} row {row_idx + 1}"
            form = HotWaterSystemForm(row_data)

            if form.is_valid():
                to_save.append(form)
            else:
                all_errors[label] = {
                    field: [str(e) for e in errs]
                    for field, errs in form.errors.items()
                }

    if all_errors:
        return JsonResponse({"success": False, "errors": all_errors}, status=400)

    with transaction.atomic():
        for form in to_save:
            system = form.save(commit=False)
            system.building = building
            system.save()

    saved_count = len(to_save)
    logger.info(
        f"Import hot water: {saved_count} system(s) saved for building {building.uuid} by {request.user}"
    )

    return JsonResponse({
        "success": True,
        "saved_count": saved_count,
        "building_uuid": str(building.uuid),
    })


# ---------------------------------------------------------------------------
# Operational Energy Carriers import
# ---------------------------------------------------------------------------

# Maps common EPD name variants (lower) → canonical name used in EPD table
# Handles typos/capitalisation differences in the template
ENERGY_CARRIER_NAME_MAP = {
    'electricity':                   'electricity ',   # trailing space in DB
    'electricity ':                  'electricity ',
    'natural gas':                   'natural gas',
    'lpg':                           'Liquefied petroleum gas (LPG)',
    'liquefied petroleum gas (lpg)': 'Liquefied petroleum gas (LPG)',
    'liquefied petroleum gas':       'Liquefied petroleum gas (LPG)',
    'diesel':                        'diesel',
    'light fuel oil':                'Light fuel oil',
    'heavy fuel oil':                'Heavy fuel oil',
    'kerosene':                      'cerosin',        # DB name is 'cerosin'
    'cerosin':                       'cerosin',
    'coal':                          'coal',
    'lignite':                       'lignite',
    'charcoal':                      'char coal',
    'char coal':                     'char coal',
    'firewood':                      'fire wood (log wood)',
    'fire wood (log wood)':          'fire wood (log wood)',
    'fire wood (wood chips)':        'fire wood (wood chips)',
    'wood chips':                    'fire wood (wood chips)',
    'fire wood (wood pellets)':      'fire wood (wood pellets)',
    'wood pellets':                  'fire wood (wood pellets)',
}

# Valid unit strings for energy carrier EPDs (kWh is the declared unit;
# conversions also allow kg, m3, liter depending on the EPD)
VALID_ENERGY_UNITS = {u.lower() for u in ('kwh', 'kWh', 'kg', 'm3', 'l', 'liter', 'litre')}


def _lookup_energy_carrier_epd(name_raw, country_name=None):
    """
    Look up an operational energy carrier EPD by name (and optionally country).
    Returns (EPD instance, error_string).

    Strategy:
      1. Exact name match (case-insensitive) within operational EPDs for country
      2. Normalised name via ENERGY_CARRIER_NAME_MAP
      3. Case-insensitive contains match
      4. Any country match (if country not specified or not found)
    """
    qs = EPD.objects.filter(
        category__parent__category_id="9.2",
        declared_unit=Unit.KWH,
        type=EPDType.GENERIC,
    ).select_related('country')

    name_lower = name_raw.strip().lower()

    # Try canonical name mapping first
    canonical = ENERGY_CARRIER_NAME_MAP.get(name_lower, name_raw.strip())

    # Build country-filtered and unfiltered querysets
    if country_name:
        qs_country = qs.filter(country__name__iexact=country_name.strip())
    else:
        qs_country = qs

    # 1. Exact match on canonical name + country
    epd = qs_country.filter(name__iexact=canonical).first()
    if epd:
        return epd, None

    # 2. Exact match on original name + country
    epd = qs_country.filter(name__iexact=name_raw.strip()).first()
    if epd:
        return epd, None

    # 3. Case-insensitive contains + country
    epd = qs_country.filter(name__icontains=canonical).first()
    if epd:
        return epd, None

    # 4. Fall back to any country
    epd = qs.filter(name__iexact=canonical).first()
    if epd:
        return epd, None

    epd = qs.filter(name__icontains=canonical).first()
    if epd:
        return epd, None

    return None, f"Energy carrier EPD not found for name '{name_raw}'."


@login_required
@require_http_methods(["POST"])
def import_operational_energy_carriers(request):
    """
    Process the Operational Energy Carriers tab from the import template.

    Expects JSON:
    {
        "building_uuid": str,
        "rows": [ [col0_name, col1_description, col2_quantity, col3_unit], ... ]
    }

    Column layout (0-based):
      0: Name        — EPD name (used to look up the operational EPD)
      1: Description — optional free text
      2: Quantity    — required, positive number
      3: Quantity unit — required, must be a unit accepted by the EPD

    EPD lookup: name match against operational EPDs
    (category__parent__category_id="9.2", declared_unit=kwh, type=generic).
    Existing OperationalProducts for the building are deleted before saving new ones
    (same behaviour as the normal UI).
    """
    import json
    from django.db import transaction

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    raw_rows = data.get("rows", [])

    if not raw_rows:
        return JsonResponse({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

    errors = {}
    to_save = []

    for row_idx, raw_row in enumerate(raw_rows):
        row = list(raw_row) + [None] * 5

        def cell(i):
            v = row[i]
            if v is None:
                return ''
            return str(v).strip()

        name_raw = cell(0)
        description = cell(1)
        quantity_raw = cell(2)
        unit_raw = cell(3).lower()

        label = f"row {row_idx + 1}"

        if not name_raw:
            continue  # Skip blank rows

        # Validate quantity
        if not quantity_raw:
            errors[label] = {"quantity": ["Quantity is required."]}
            continue
        try:
            quantity = float(quantity_raw)
            if quantity <= 0:
                errors[label] = {"quantity": ["Quantity must be greater than 0."]}
                continue
        except (ValueError, TypeError):
            errors[label] = {"quantity": [f"Invalid quantity: '{quantity_raw}'."]}
            continue

        # Validate unit
        if not unit_raw:
            errors[label] = {"unit": ["Quantity unit is required."]}
            continue

        # Normalise common unit strings
        unit_norm_map = {
            'kwh': 'kwh', 'kilowatt hour': 'kwh', 'kilowatt-hour': 'kwh',
            'kg': 'kg', 'kilogram': 'kg',
            'm3': 'm3', 'm³': 'm3', 'cubic meter': 'm3', 'cubic metre': 'm3',
            'l': 'l', 'liter': 'l', 'litre': 'l', 'liter ': 'l',
        }
        unit_norm = unit_norm_map.get(unit_raw, unit_raw)

        # Look up EPD
        epd, epd_error = _lookup_energy_carrier_epd(name_raw)
        if epd_error:
            errors[label] = {"name": [epd_error]}
            continue

        # Validate unit is accepted by this EPD
        available = epd.get_available_units() or {epd.declared_unit}
        available_lower = {str(u).lower() for u in available}
        if unit_norm not in available_lower and unit_raw not in available_lower:
            errors[label] = {
                "unit": [
                    f"Unit '{unit_raw}' is not valid for '{epd.name}'. "
                    f"Accepted: {', '.join(sorted(available_lower))}."
                ]
            }
            continue

        to_save.append({
            "epd": epd,
            "quantity": quantity,
            "input_unit": unit_norm,
            "description": description,
        })

    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    with transaction.atomic():
        # Replace existing operational products (same as normal UI behaviour)
        OperationalProduct.objects.filter(building=building).delete()
        for item in to_save:
            OperationalProduct.objects.create(
                building=building,
                epd=item["epd"],
                quantity=item["quantity"],
                input_unit=item["input_unit"],
                description=item["description"],
            )

    saved_count = len(to_save)
    logger.info(
        f"Import energy carriers: {saved_count} product(s) saved for building {building.uuid} by {request.user}"
    )

    return JsonResponse({
        "success": True,
        "saved_count": saved_count,
        "building_uuid": str(building.uuid),
    })


# ---------------------------------------------------------------------------
# Structural Components import (By Component)
# ---------------------------------------------------------------------------

# Maps Excel "Building Component" column (lower/stripped) → AssemblyCategory id
STRUCTURAL_CATEGORY_MAP = {}  # populated lazily in _get_structural_category_map()

def _get_structural_category_map():
    """Build a lower-cased name → AssemblyCategory lookup (cached in module dict)."""
    if not STRUCTURAL_CATEGORY_MAP:
        for cat in AssemblyCategory.objects.all():
            STRUCTURAL_CATEGORY_MAP[cat.name.lower().strip()] = cat
            # Also add singular/plural variants
            if cat.name.endswith('s'):
                STRUCTURAL_CATEGORY_MAP[cat.name[:-1].lower().strip()] = cat
            else:
                STRUCTURAL_CATEGORY_MAP[(cat.name + 's').lower().strip()] = cat
    return STRUCTURAL_CATEGORY_MAP


# Maps Excel "Dimension" column (lower) → AssemblyDimension value
DIMENSION_MAP = {
    'area':   AssemblyDimension.AREA,
    'length': AssemblyDimension.LENGTH,
    'mass':   AssemblyDimension.MASS,
    'volume': AssemblyDimension.VOLUME,
    'pieces': AssemblyDimension.PCS,
    'pcs':    AssemblyDimension.PCS,
}

# Maps Excel "Units" column (lower) → Unit model value
STRUCTURAL_UNIT_MAP = {
    'm2':  Unit.M2, 'm²': Unit.M2, 'sq m': Unit.M2, 'sqm': Unit.M2,
    'm3':  Unit.M3, 'm³': Unit.M3, 'cu m': Unit.M3, 'cum': Unit.M3,
    'm':   Unit.M,
    'kg':  Unit.KG,
    'ton': Unit.TONES, 'tones': Unit.TONES, 'tonnes': Unit.TONES,
    'pcs': Unit.PCS, 'pieces': Unit.PCS,
}


def _lookup_structural_epd(epd_name_raw, country_name_raw):
    """
    Look up a structural (non-operational) EPD by name and country.
    Returns (EPD instance, error_string).
    Tries exact, then case-insensitive, then country-agnostic matches.
    """
    qs = EPD.objects.exclude(
        category__parent__category_id="9.2"
    ).exclude(declared_unit=Unit.KWH)

    name = epd_name_raw.strip()
    country = country_name_raw.strip()

    # 1. Exact name + country
    epd = qs.filter(name__iexact=name, country__name__iexact=country).first()
    if epd:
        return epd, None

    # 2. Exact name only
    epd = qs.filter(name__iexact=name).first()
    if epd:
        return epd, None

    # 3. Name contains + country
    epd = qs.filter(name__icontains=name, country__name__iexact=country).first()
    if epd:
        return epd, None

    # 4. Name contains only
    epd = qs.filter(name__icontains=name).first()
    if epd:
        return epd, None

    return None, f"Structural EPD not found for name '{name}' (country: '{country}')."


@login_required
@require_http_methods(["POST"])
def import_structural_components(request):
    """
    Process the 'Structural Components - By Component' tab from the import template.

    The sheet has a two-row header:
      Row 1 (col 0-6):  Title | Building Component | Construction Technique |
                         Dimension | Quantity | Units | Comment
      Row 1 (col 8-11): Added Materials header (ignored)
      Row 2 (col 8-11): EPD Name | Country | Quantity | Units  ← added materials sub-header

    Data starts from row 3 (0-indexed row 2).
    Each data row carries:
      col 0:  Title         (optional label)
      col 1:  Building Component  (→ AssemblyCategory)
      col 2:  Construction Technique  (→ AssemblyTechnique, optional)
      col 3:  Dimension     (→ AssemblyDimension)
      col 4:  Quantity
      col 5:  Units
      col 6:  Comment       (optional)
      col 8:  EPD Name      (Added Material)
      col 9:  Country       (Added Material country)
      col 10: Quantity      (Added Material quantity)
      col 11: Units         (Added Material unit)

    Multiple consecutive rows with the same Building Component + Technique
    represent multiple materials for the same assembly. A blank col 2 + 3 + 4
    row signals a section break (skip it).

    Expects JSON:
    {
        "building_uuid": str,
        "rows": [ [col0..col16], ... ]   (data rows only, headers stripped by JS)
    }

    All-or-nothing save (atomic). Each assembly gets one BuildingAssembly record.
    """
    import json
    from django.db import transaction

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    raw_rows = data.get("rows", [])
    if not raw_rows:
        return JsonResponse({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

    cat_map = _get_structural_category_map()
    errors = {}

    # We group rows into assemblies.
    # Each new non-blank Building Component starts a new assembly.
    # Within an assembly, each row is one material (EPD).
    assemblies_to_create = []  # list of dicts
    current_assembly = None

    for row_idx, raw_row in enumerate(raw_rows):
        row = list(raw_row) + [None] * 17

        def cell(i):
            v = row[i]
            if v is None:
                return ''
            return str(v).strip()

        comp_raw   = cell(1)
        tech_raw   = cell(2)
        dim_raw    = cell(3)
        qty_raw    = cell(4)
        unit_raw   = cell(5)
        comment    = cell(6)
        title      = cell(0)

        epd_name   = cell(8)
        epd_country= cell(9)
        epd_qty    = cell(10)
        epd_unit   = cell(11)

        label = f"row {row_idx + 1}"

        # Separator row: Building Component present but no material data → end of group
        if comp_raw and not tech_raw and not qty_raw:
            current_assembly = None
            continue

        # New assembly: row has Building Component + Dimension + Quantity
        if comp_raw and qty_raw:
            # Resolve category
            cat = cat_map.get(comp_raw.lower().strip())
            if cat is None:
                errors[label] = {"building_component": [f"Unknown building component '{comp_raw}'."]}
                current_assembly = None
                continue

            # Resolve dimension
            dim_val = DIMENSION_MAP.get(dim_raw.lower().strip())
            if not dim_val:
                errors[label] = {"dimension": [f"Unknown dimension '{dim_raw}'."]}
                current_assembly = None
                continue

            # Validate assembly quantity
            try:
                asm_qty = float(qty_raw)
                if asm_qty <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors[label] = {"quantity": [f"Invalid quantity '{qty_raw}'."]}
                current_assembly = None
                continue

            # Resolve assembly unit
            asm_unit = STRUCTURAL_UNIT_MAP.get(unit_raw.lower())
            if not asm_unit:
                errors[label] = {"unit": [f"Unknown unit '{unit_raw}'."]}
                current_assembly = None
                continue

            current_assembly = {
                "title":      title or comp_raw,
                "category":   cat,
                "technique_name": tech_raw,
                "dimension":  dim_val,
                "quantity":   asm_qty,
                "unit":       asm_unit,
                "comment":    comment,
                "materials":  [],
            }
            assemblies_to_create.append(current_assembly)

        # Material row: has EPD name and quantity (col 8+)
        if epd_name and epd_qty:
            if current_assembly is None:
                errors[label] = {"epd": ["Material row found without a preceding assembly row."]}
                continue

            # Validate material quantity
            try:
                mat_qty = float(epd_qty)
                if mat_qty <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors[label] = {"epd_quantity": [f"Invalid material quantity '{epd_qty}'."]}
                continue

            # Look up EPD
            epd, epd_error = _lookup_structural_epd(epd_name, epd_country)
            if epd_error:
                errors[label] = {"epd_name": [epd_error]}
                continue

            # Derive the correct input_unit from the assembly dimension (same logic as UI)
            from pages.views.assembly.epd_dimension_info import get_epd_dimension_info
            _, expected_unit = get_epd_dimension_info(current_assembly["dimension"], epd.declared_unit)

            current_assembly["materials"].append({
                "epd":      epd,
                "quantity": mat_qty,
                "unit":     expected_unit,
            })

    # Remove assemblies that ended up with no materials
    assemblies_to_create = [a for a in assemblies_to_create if a["materials"]]

    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    if not assemblies_to_create:
        return JsonResponse({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

    # Resolve technique → classification for each assembly
    # (AssemblyCategoryTechnique links category + technique; used as StructuralProduct.classification)
    from pages.models.assembly import AssemblyTechnique

    saved_count = 0
    with transaction.atomic():
        for asm_data in assemblies_to_create:
            # Resolve technique (optional)
            classification = None
            if asm_data["technique_name"]:
                try:
                    technique = AssemblyTechnique.objects.get(
                        name__iexact=asm_data["technique_name"].strip()
                    )
                    classification = AssemblyCategoryTechnique.objects.filter(
                        category=asm_data["category"],
                        technique=technique,
                    ).first()
                except AssemblyTechnique.DoesNotExist:
                    # Technique not found — still create assembly without classification
                    pass

            # Create Assembly
            assembly = Assembly.objects.create(
                created_by=request.user,
                name=asm_data["title"],
                comment=asm_data["comment"],
                dimension=asm_data["dimension"],
                mode=AssemblyMode.CUSTOM,
                is_boq=False,
                is_template=False,
                public=False,
                draft=False,
            )

            # Create StructuralProduct records
            for mat in asm_data["materials"]:
                StructuralProduct.objects.create(
                    epd=mat["epd"],
                    assembly=assembly,
                    quantity=mat["quantity"],
                    input_unit=mat["unit"],
                    classification=classification,
                )

            # Link assembly to building
            from pages.models.building import BuildingAssembly
            BuildingAssembly.objects.create(
                building=building,
                assembly=assembly,
                quantity=asm_data["quantity"],
                reporting_life_cycle=50,
            )

            saved_count += 1

    logger.info(
        f"Import structural: {saved_count} assembly(ies) saved for building {building.uuid} by {request.user}"
    )

    return JsonResponse({
        "success": True,
        "saved_count": saved_count,
        "building_uuid": str(building.uuid),
    })


# ---------------------------------------------------------------------------
# Cancel import — delete the partially created building
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def cancel_import(request):
    """
    Delete a partially created building when the user cancels the import.
    Only deletes the building if it belongs to the requesting user.
    """
    import json
    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({"success": False}, status=400)

    building_uuid_str = _str(data.get("building_uuid"))
    if not building_uuid_str:
        return JsonResponse({"success": True})  # Nothing to clean up

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)

        # Delete certification file from storage
        if building.certification_file:
            building.certification_file.delete(save=False)

        # Delete all BoQ files from storage
        for boq in building.boq_files.all():
            boq.file.delete(save=False)

        building.delete()
        logger.info(f"Import cancelled: building {building_uuid_str} deleted by {request.user}")
    except (ValueError, Building.DoesNotExist):
        pass  # Already gone or never existed — that's fine

    return JsonResponse({"success": True})


# ---------------------------------------------------------------------------
# Existing dialog views (unchanged)
# ---------------------------------------------------------------------------

def view_import_dialog(request):
    return render(request, "pages/home/import-dialog/import-dialog.html")


def view_initial_import_dialog(request):
    return render(request, "pages/home/import-dialog/initial-dialog.html")


def view_import_building_step(request, step_id):
    logger.debug(f"Received request for import building step: {step_id}")
    context = {}
    if step_id == "step-upload":
        try:
            context["import_template_url"] = static("docs/import-template.xlsx")
        except Exception:
            context["import_template_url"] = None
    return render(request, f"pages/home/import-dialog/{step_id}.html", context)


# ---------------------------------------------------------------------------
# Tab 1 — Building Name & Location
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def import_building_name_location(request):
    """
    Process Tab 1 (Building Name and Location) from the import template.

    Expects multipart/form-data or JSON with fields:
      building_name, address, country, region (optional), city,
      longitude (optional), latitude (optional),
      building_uuid (optional — if re-submitting to update)

    Returns JSON with building_uuid on success, or field errors.
    """
    import json

    # Support both JSON and form-data payloads
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body)
        except (ValueError, KeyError):
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON."]}}, status=400)
    else:
        data = request.POST.dict()

    errors = {}

    building_name = _str(data.get("building_name"))
    address = _str(data.get("address"))
    country_name = _str(data.get("country"))
    region_name = _str(data.get("region"))
    city_name = _str(data.get("city"))
    longitude = data.get("longitude") or None
    latitude = data.get("latitude") or None
    building_uuid = _str(data.get("building_uuid"))

    # --- Required field checks ---
    if not building_name:
        errors["building_name"] = "Building name is required."
    if not address:
        errors["address"] = "Address is required."

    # --- Country validation ---
    country, country_err = _resolve_country(country_name)
    if country_err:
        errors["country"] = country_err

    # --- Region (optional) ---
    region = None
    if country and region_name:
        region, region_err = _resolve_region(region_name, country)
        if region_err:
            errors["region"] = region_err

    # --- City ---
    city = None
    if country:
        city, city_err = _resolve_city(city_name, country)
        if city_err:
            errors["city"] = city_err
    elif not city_name:
        errors["city"] = "City is required."

    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    # --- Parse coordinates ---
    try:
        longitude = float(longitude) if longitude else None
    except (ValueError, TypeError):
        longitude = None
    try:
        latitude = float(latitude) if latitude else None
    except (ValueError, TypeError):
        latitude = None

    # --- Save or update building ---
    if building_uuid:
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
            building.name = building_name
            building.street = address
            building.country = country
            building.region = region
            building.city = city
            building.longitude = longitude
            building.latitude = latitude
            building.save()
        except (ValueError, Building.DoesNotExist):
            return JsonResponse(
                {"success": False, "errors": {"__all__": ["Invalid building UUID."]}},
                status=400,
            )
    else:
        building = Building.objects.create(
            name=building_name,
            street=address,
            country=country,
            region=region,
            city=city,
            longitude=longitude,
            latitude=latitude,
            created_by=request.user,
            # Defaults — will be updated in Tab 2
            climate_zone=ClimateZone.TROPICAL_WET,
            total_floor_area=100,
            reference_period=50,
        )

    logger.info(f"Import Tab 1: building {building.uuid} saved by {request.user}")

    return JsonResponse({
        "success": True,
        "building_uuid": str(building.uuid),
    })


# ---------------------------------------------------------------------------
# Tab 2 — Building Details
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def import_building_details(request):
    """
    Process Tab 2 (Building Details) from the import template.

    Expects multipart/form-data with fields:
      building_uuid (required),
      building_type (e.g. "Homes - middle income"),
      climate_type, assessment_period, total_floor_area,
      conditioned_floor_area (optional), construction_year (optional),
      floors_below_ground (optional),
      has_certification ("Yes"/"No"), certification_file (file, if yes),
      has_boq ("Yes"/"No"), boq_files (one or more files, if yes)
    """
    import os

    building_uuid_str = request.POST.get("building_uuid", "").strip()
    if not building_uuid_str:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=400,
        )

    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=404,
        )

    errors = {}

    # --- Building type ---
    building_type_str = _str(request.POST.get("building_type"))
    cat_subcat, bt_err = _resolve_building_type(building_type_str)
    if bt_err:
        errors["building_type"] = bt_err

    # --- Climate type ---
    climate_value, climate_err = _resolve_climate(request.POST.get("climate_type"))
    if climate_err:
        errors["climate_type"] = climate_err

    # --- Assessment period ---
    assessment_period_raw = _str(request.POST.get("assessment_period"))
    assessment_period = None
    if not assessment_period_raw:
        errors["assessment_period"] = "Assessment period is required."
    else:
        try:
            assessment_period = int(float(assessment_period_raw))
            if assessment_period <= 0:
                errors["assessment_period"] = "Assessment period must be a positive number."
        except (ValueError, TypeError):
            errors["assessment_period"] = "Assessment period must be a valid number."

    # --- Total floor area ---
    total_floor_area_raw = _str(request.POST.get("total_floor_area"))
    total_floor_area = None
    if not total_floor_area_raw:
        errors["total_floor_area"] = "Total floor area is required."
    else:
        try:
            total_floor_area = float(total_floor_area_raw)
            if total_floor_area <= 0:
                errors["total_floor_area"] = "Total floor area must be greater than zero."
        except (ValueError, TypeError):
            errors["total_floor_area"] = "Total floor area must be a valid number."

    # --- Optional numeric fields ---
    conditioned_floor_area = None
    cfa_raw = _str(request.POST.get("conditioned_floor_area"))
    if cfa_raw:
        try:
            conditioned_floor_area = float(cfa_raw)
        except (ValueError, TypeError):
            errors["conditioned_floor_area"] = "Conditioned floor area must be a valid number."

    construction_year = None
    cy_raw = _str(request.POST.get("construction_year"))
    if cy_raw:
        try:
            construction_year = int(float(cy_raw))
        except (ValueError, TypeError):
            errors["construction_year"] = "Construction year must be a valid year."

    floors_below_ground = None
    fbg_raw = _str(request.POST.get("floors_below_ground"))
    if fbg_raw:
        try:
            floors_below_ground = int(float(fbg_raw))
        except (ValueError, TypeError):
            errors["floors_below_ground"] = "Floors below ground must be a valid number."

    # --- Boolean flags ---
    has_certification = _bool_from_excel(request.POST.get("has_certification", "no"))
    has_boq = _bool_from_excel(request.POST.get("has_boq", "no"))

    # --- File validation ---
    from pages.views.building.building_step_files import (
        ALLOWED_EXTENSIONS,
        MAX_FILE_SIZE_BYTES,
        _validate_file,
    )

    if has_certification:
        cert_file = request.FILES.get("certification_file")
        if not cert_file:
            errors["certification_file"] = (
                "A certification file is required when 'Has certification' is Yes."
            )
        else:
            cert_err = _validate_file(cert_file)
            if cert_err:
                errors["certification_file"] = f"Certification file: {cert_err}"

    if has_boq:
        boq_files = request.FILES.getlist("boq_files")
        if not boq_files:
            errors["boq_files"] = (
                "At least one BoQ file is required when 'Has BoQ' is Yes."
            )
        else:
            for f in boq_files:
                boq_err = _validate_file(f)
                if boq_err:
                    errors["boq_files"] = f"BoQ file '{f.name}': {boq_err}"
                    break

    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    # --- Apply changes to building ---
    if cat_subcat:
        building.category = cat_subcat
    building.climate_zone = climate_value
    building.reference_period = assessment_period
    building.total_floor_area = total_floor_area

    if conditioned_floor_area is not None:
        building.cond_floor_area = conditioned_floor_area
    if construction_year is not None:
        building.construction_year = construction_year
    if floors_below_ground is not None:
        building.floors_below_ground = floors_below_ground

    building.has_certification = has_certification
    building.has_boq = has_boq

    # --- Handle certification file ---
    if has_certification:
        cert_file = request.FILES.get("certification_file")
        if cert_file:
            # Remove old file if present
            if building.certification_file:
                try:
                    old_path = building.certification_file.path
                    if os.path.isfile(old_path):
                        os.remove(old_path)
                except Exception:
                    pass
            building.certification_file = cert_file
    else:
        # Clear existing cert file if user says No
        if building.certification_file:
            try:
                old_path = building.certification_file.path
                if os.path.isfile(old_path):
                    os.remove(old_path)
            except Exception:
                pass
            building.certification_file = None

    building.save()

    # --- Handle BoQ files ---
    if has_boq:
        new_boq_files = request.FILES.getlist("boq_files")
        if new_boq_files:
            # Remove existing BoQ files
            for old_file in building.boq_files.all():
                try:
                    if os.path.isfile(old_file.file.path):
                        os.remove(old_file.file.path)
                except Exception:
                    pass
                old_file.delete()
            # Save new ones
            for f in new_boq_files:
                BuildingBoQFile.objects.create(
                    building=building,
                    file=f,
                    original_filename=f.name,
                )
    else:
        # Remove all existing BoQ files if user says No
        for old_file in building.boq_files.all():
            try:
                if os.path.isfile(old_file.file.path):
                    os.remove(old_file.file.path)
            except Exception:
                pass
            old_file.delete()

    logger.info(f"Import Tab 2: building {building.uuid} details saved by {request.user}")

    return JsonResponse({
        "success": True,
        "building_uuid": str(building.uuid),
    })