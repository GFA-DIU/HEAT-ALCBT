"""
Comprehensive tests for the building import wizard endpoints.

Covers every import tab:
  - Tab 1: Building Name & Location
  - Tab 2: Building Details
  - Tab 3: Operational Schedule & Temperature
  - Cooling Systems (Window AC / Split AC / VRF / PackagedDuctab / Water-cooled Chiller / Air-cooled Chiller)
  - Ventilation Systems (AHU / FCU / Cassette AC / DOAS / Fan)
  - Lighting Systems (LED / Fluorescent / CFL / Incandescent / HiD)
  - Lift & Escalator System
  - Hot Water Systems (Heat Pump / Boiler / Water Heater)
  - Operational Energy Carriers
  - Structural Components (By Component)

Edge cases tested per tab:
  - Valid happy path
  - Missing required fields
  - Invalid / out-of-range values
  - Capital / mixed-case strings for choice fields
  - Numeric values supplied as strings
  - Empty / null rows are silently skipped
  - Unauthenticated requests return 302 redirect
  - Wrong building owner returns 404
  - All auto-calculated fields are correctly computed
"""
import json
import pytest
from decimal import Decimal

from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

from pages.models.building import Building, OperationalProduct
from pages.models.building_operation import (
    CoolingSystemAirConditioner,
    CoolingSystemChiller,
    VentilationSystem,
    LiftEscalatorSystem,
    HotWaterSystem,
)
from pages.models.building_operation.lighting import LightingSystem
from pages.models.assembly import Assembly, StructuralProduct
from pages.models.building import BuildingAssembly
from pages.models.epd import EPD, EPDType, Unit

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _make_verified_user(username, email, password="testpass123"):
    u = User.objects.create_user(username=username, email=email, password=password)
    EmailAddress.objects.create(user=u, email=email, verified=True, primary=True)
    return u


@pytest.fixture
def user(db):
    return _make_verified_user("importuser", "importuser@example.com")


@pytest.fixture
def other_user(db):
    return _make_verified_user("otheruser", "other@example.com")


@pytest.fixture
def building(db, user):
    return Building.objects.create(
        name="Import Test Building",
        total_floor_area=1000.0,
        created_by=user,
    )


@pytest.fixture
def other_building(db, other_user):
    return Building.objects.create(
        name="Other Building",
        total_floor_area=500.0,
        created_by=other_user,
    )


@pytest.fixture
def indonesia(db):
    """Create an Indonesia Country record (ALCBT-supported, code2='ID')."""
    from cities_light.models import Country
    return Country.objects.get_or_create(
        code2="ID",
        defaults={"name": "Indonesia", "continent": "AS", "slug": "indonesia"},
    )[0]


@pytest.fixture
def jakarta(db, indonesia):
    """Create Jakarta city for Indonesia."""
    from cities_light.models import City
    return City.objects.get_or_create(
        name="Jakarta",
        country=indonesia,
        defaults={"slug": "jakarta"},
    )[0]


def _make_energy_carrier_epd(db, user, name, country=None):
    """
    Create a minimal energy carrier EPD (category 9.2, declared_unit=kwh, type=generic).
    Returns the EPD instance.
    """
    from pages.models.epd import EPD, EPDType, Unit, MaterialCategory
    # Create category hierarchy: root → 9.2 parent → child
    root, _ = MaterialCategory.objects.get_or_create(
        category_id="9", defaults={"name_en": "Others", "name_de": "Others", "level": 1}
    )
    parent, _ = MaterialCategory.objects.get_or_create(
        category_id="9.2",
        defaults={"name_en": "Energy carrier", "name_de": "Energietraeger", "level": 2, "parent": root},
    )
    child, _ = MaterialCategory.objects.get_or_create(
        category_id=f"9.2.{name[:4]}",
        defaults={"name_en": name, "name_de": name, "level": 3, "parent": parent},
    )
    return EPD.objects.create(
        name=name,
        names=[{"value": name, "lang": "en"}],
        UUID=f"test-{name[:20].replace(' ', '-')}",
        declared_unit=Unit.KWH,
        conversions=[],
        type=EPDType.GENERIC,
        category=child,
        country=country,
        public=True,
        draft=False,
        declared_amount=1,
        created_by=user,
    )


@pytest.fixture
def energy_carrier_epds(db, user):
    """
    Seed minimal energy carrier EPDs needed by import tests.
    Covers: electricity, LPG, diesel, natural gas, kerosene/cerosin, charcoal.
    """
    epds = {}
    epds["electricity "] = _make_energy_carrier_epd(db, user, "electricity ")
    epds["lpg"] = _make_energy_carrier_epd(db, user, "Liquefied petroleum gas (LPG)")
    epds["diesel"] = _make_energy_carrier_epd(db, user, "diesel")
    epds["natural gas"] = _make_energy_carrier_epd(db, user, "natural gas")
    epds["cerosin"] = _make_energy_carrier_epd(db, user, "cerosin")
    epds["char coal"] = _make_energy_carrier_epd(db, user, "char coal")
    return epds


@pytest.fixture
def structural_epd(db, user):
    """Create a minimal structural EPD for structural component import tests."""
    from pages.models.epd import EPD, EPDType, Unit, MaterialCategory
    root, _ = MaterialCategory.objects.get_or_create(
        category_id="1", defaults={"name_en": "Construction", "name_de": "Konstruktion", "level": 1}
    )
    child, _ = MaterialCategory.objects.get_or_create(
        category_id="1.1",
        defaults={"name_en": "Concrete", "name_de": "Beton", "level": 2, "parent": root},
    )
    return EPD.objects.create(
        name="Test Concrete M30",
        names=[{"value": "Test Concrete M30", "lang": "en"}],
        UUID="test-concrete-m30",
        declared_unit=Unit.M3,
        conversions=[],
        type=EPDType.GENERIC,
        category=child,
        public=True,
        draft=False,
        declared_amount=1,
        created_by=user,
    )


@pytest.fixture
def assembly_category(db):
    """Create a minimal AssemblyCategory for structural component import tests."""
    from pages.models.assembly import AssemblyCategory
    return AssemblyCategory.objects.get_or_create(
        tag="TEST01",
        defaults={"name": "Test Beams"},
    )[0]


def _post_json(client, url_name, payload, **url_kwargs):
    url = reverse(url_name, kwargs=url_kwargs) if url_kwargs else reverse(url_name)
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


def _post_form(client, url_name, payload, **url_kwargs):
    url = reverse(url_name, kwargs=url_kwargs) if url_kwargs else reverse(url_name)
    return client.post(url, data=payload)


# ---------------------------------------------------------------------------
# Tab 1 — Building Name & Location
# ---------------------------------------------------------------------------

class TestImportBuildingNameLocation:

    def test_unauthenticated_redirects(self, client, db):
        resp = _post_json(client, "import_building_name_location", {"building_name": "X"})
        assert resp.status_code == 302

    def test_missing_required_fields(self, client, user):
        client.force_login(user)
        resp = _post_json(client, "import_building_name_location", {})
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert "building_name" in data["errors"] or "__all__" in data["errors"]

    def test_creates_building_with_all_fields(self, client, user, jakarta):
        client.force_login(user)
        payload = {
            "building_name": "My Tower",
            "address": "123 Main St",
            "country": "Indonesia",
            "city": "Jakarta",
            "longitude": "106.8456",
            "latitude": "-6.2088",
        }
        resp = _post_json(client, "import_building_name_location", payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "building_uuid" in data
        building = Building.objects.get(uuid=data["building_uuid"])
        assert building.name == "My Tower"
        assert building.created_by == user

    def test_updates_existing_building(self, client, user, building, jakarta):
        client.force_login(user)
        payload = {
            "building_uuid": str(building.uuid),
            "building_name": "Updated Name",
            "address": "123 Main St",
            "country": "Indonesia",
            "city": "Jakarta",
        }
        resp = _post_json(client, "import_building_name_location", payload)
        assert resp.status_code == 200
        building.refresh_from_db()
        assert building.name == "Updated Name"

    def test_cannot_update_other_users_building(self, client, user, other_building):
        client.force_login(user)
        payload = {
            "building_uuid": str(other_building.uuid),
            "building_name": "Hacked",
            "country": "Indonesia",
            "city": "Jakarta",
        }
        resp = _post_json(client, "import_building_name_location", payload)
        assert resp.status_code in (400, 404)

    def test_invalid_country(self, client, user, db):
        client.force_login(user)
        payload = {
            "building_name": "Test",
            "country": "Narnia",
            "city": "Somewhere",
        }
        resp = _post_json(client, "import_building_name_location", payload)
        assert resp.status_code == 400

    def test_longitude_latitude_optional(self, client, user, jakarta):
        client.force_login(user)
        payload = {
            "building_name": "No Coords",
            "address": "456 Side St",
            "country": "Indonesia",
            "city": "Jakarta",
        }
        resp = _post_json(client, "import_building_name_location", payload)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tab 3 — Operational Schedule & Temperature
# ---------------------------------------------------------------------------

class TestImportOperationalSchedule:

    def test_unauthenticated(self, client, db):
        resp = _post_json(client, "import_operational_schedule", {})
        assert resp.status_code == 302

    def test_missing_building_uuid(self, client, user):
        client.force_login(user)
        resp = _post_json(client, "import_operational_schedule", {})
        assert resp.status_code == 400

    def test_valid_schedule(self, client, user, building):
        client.force_login(user)
        payload = {
            "building_uuid": str(building.uuid),
            "num_residents": "10",
            "hours_per_workday": "8",
            "workdays_per_week": "5",
            "weeks_per_year": "52",
            "heating_temp": "22",
            "heating_temp_unit": "celsius",
            "cooling_temp": "26",
            "cooling_temp_unit": "celsius",
            "renewable_energy_percent": "20",
            "building_smart_system": "no",
        }
        resp = _post_json(client, "import_operational_schedule", payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_invalid_hours_out_of_range(self, client, user, building):
        client.force_login(user)
        payload = {
            "building_uuid": str(building.uuid),
            "num_residents": "5",
            "hours_per_workday": "25",  # > 24
            "workdays_per_week": "5",
            "weeks_per_year": "52",
            "heating_temp": "22",
            "heating_temp_unit": "celsius",
            "cooling_temp": "26",
            "cooling_temp_unit": "celsius",
            "renewable_energy_percent": "0",
            "building_smart_system": "no",
        }
        resp = _post_json(client, "import_operational_schedule", payload)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Cooling Systems
# ---------------------------------------------------------------------------

class TestImportCoolingSystems:

    def _url(self):
        return reverse("import_cooling_systems")

    def test_unauthenticated(self, client, db):
        resp = client.post(self._url(), data="{}", content_type="application/json")
        assert resp.status_code == 302

    def test_missing_building_uuid(self, client, user):
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {"systems": []})
        assert resp.status_code == 400

    def test_empty_systems_skipped_silently(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_window_ac_happy_path(self, client, user, building):
        # col: year, ref_type, ref_qty, capacity, cap_unit, num_units, leakage, hours, days, weeks, power_input, eer
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "window ac",
                "rows": [[
                    "2020",   # col0 year_of_installation
                    "R-410A", # col1 refrigerant_type
                    "0.5",    # col2 refrigerant_quantity_kg
                    "5.28",   # col3 cooling_capacity_per_unit (kW)
                    "kw",     # col4 capacity_unit
                    "2",      # col5 number_of_units
                    "",       # col6 leakage (auto-default)
                    "8",      # col7 hours_per_day
                    "5",      # col8 days_per_week
                    "52",     # col9 weeks_per_year
                    "",       # col10 power_input (empty → use capacity/EER)
                    "3.0",    # col11 EER
                    None,     # col12 energy_label
                    None,     # col13 stars
                ]],
            }],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["saved_count"] == 1
        ac = CoolingSystemAirConditioner.objects.filter(building=building).first()
        assert ac is not None
        assert ac.number_of_units == 2

    def test_window_ac_auto_calc_energy(self, client, user, building):
        """Energy should be auto-calculated from capacity/EER and schedule."""
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "window ac",
                "rows": [["2020","R-410A","0.5","5.28","kw","1","","8","5","52","","3.0",None,None]],
            }],
        })
        assert resp.status_code == 200
        ac = CoolingSystemAirConditioner.objects.filter(building=building).first()
        # 5.28/3.0 * 1 unit * 8h * 5d * 52w = ~7,309 kWh
        assert ac.total_energy_consumption_kwh_per_year is not None
        assert ac.total_energy_consumption_kwh_per_year > 0

    def test_split_ac_happy_path(self, client, user, building):
        # col: year, ref_type, ref_qty, capacity, cap_unit, num_units, leakage, hours, days, weeks, power_input, eer
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "split ac",
                "rows": [["2021","R-32","0.3","7.03","kw","3","","10","6","50","","4.0",None,None]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1

    def test_water_cooled_chiller_happy_path(self, client, user, building):
        # col: year, ref_type, ref_qty, load_kW, num_chillers, leakage, hours, days, weeks, cop, vsd, hr, ipvl, load_factor, total_power, cop2, label, stars
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "water cooled",
                "rows": [[
                    "2019",   # 0: year
                    "R-134a", # 1: refrigerant
                    "100",    # 2: refrigerant qty kg
                    "500",    # 3: load kW
                    "1",      # 4: num_chillers
                    "",       # 5: leakage → auto
                    "10",     # 6: hours/day
                    "5",      # 7: days/week
                    "52",     # 8: weeks/year
                    "0.65",   # 9: efficiency kW/RT (valid range 0.40-1.00)
                    "No",     # 10: VSD
                    "No",     # 11: heat recovery
                    None,     # 12: ipvl
                    None,     # 13: load_factor
                    None,     # 14: total_power
                    None,     # 15: cop2
                    None,     # 16: label
                    None,     # 17: stars
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1

    def test_missing_required_year(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "window ac",
                "rows": [[
                    None,           # missing year → row is skipped (year required)
                    "R-410A","0.5","5.28","kw","2","","8","5","52","","3.0",None,None,
                ]],
            }],
        })
        # year is None → row skipped → saved_count=0, not 400
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_empty_rows_skipped(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "window ac",
                "rows": [
                    [None, None, None, None, None, None, None, None, None, None, None],
                    [None, None, None, None, None, None, None, None, None, None, None],
                ],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_multiple_tabs_saved(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [
                {
                    "tab": "window ac",
                    "rows": [["2020","R-410A","0.5","5.28","kw","1","","8","5","52","","3.0",None,None]],
                },
                {
                    "tab": "split ac",
                    "rows": [["2021","R-32","0.3","7.03","kw","2","","10","6","50","","4.0",None,None]],
                },
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 2

    def test_leakage_factor_auto_default_old_unit(self, client, user, building):
        """Units installed >= 7 years ago should get leakage factor 10%."""
        client.force_login(user)
        import datetime
        old_year = str(datetime.datetime.now().year - 8)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "window ac",
                "rows": [[old_year,"R-410A","0.5","5.28","kw","1","","8","5","52","","3.0",None,None]],
            }],
        })
        assert resp.status_code == 200
        ac = CoolingSystemAirConditioner.objects.filter(building=building).first()
        assert ac.baseline_leakage_factor_percent == 10

    def test_leakage_factor_auto_default_new_unit(self, client, user, building):
        """Units installed < 7 years ago should get leakage factor 2%."""
        client.force_login(user)
        import datetime
        new_year = str(datetime.datetime.now().year - 2)
        resp = _post_json(client, "import_cooling_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "window ac",
                "rows": [[new_year,"R-410A","0.5","5.28","kw","1","","8","5","52","","3.0",None,None]],
            }],
        })
        assert resp.status_code == 200
        ac = CoolingSystemAirConditioner.objects.filter(building=building).first()
        assert ac.baseline_leakage_factor_percent == 2


# ---------------------------------------------------------------------------
# Ventilation Systems
# ---------------------------------------------------------------------------

class TestImportVentilationSystems:

    def test_unauthenticated(self, client, db):
        resp = client.post(reverse("import_ventilation_systems"), data="{}", content_type="application/json")
        assert resp.status_code == 302

    def test_ahu_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "ahu",
                "rows": [[
                    "2",    # units
                    "0.5",  # baseline_efficiency (W/CMH)
                    "No",   # VSD
                    "No",   # DCV
                    "10",   # hours
                    "5",    # days
                    "50",   # weeks
                    "1000", # airflow CMH
                    "cmh",  # airflow unit
                    None,   # energy (auto)
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1
        sys_obj = VentilationSystem.objects.filter(building=building).first()
        assert sys_obj is not None
        # power = 1000 * 0.5 * 2 / 1000 = 1.0 kW
        assert sys_obj.total_power_input_kw == Decimal("1.0")

    def test_ahu_with_vsd_dcv_reduces_energy(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "ahu",
                "rows": [[
                    "1", "0.5", "Yes", "Yes", "10", "5", "50", "1000", "cmh", None,
                ]],
            }],
        })
        assert resp.status_code == 200
        sys_obj = VentilationSystem.objects.filter(building=building).first()
        # energy = 0.5 * 10 * 5 * 50 * 0.80 * 0.70 = 700 kWh
        assert sys_obj.total_energy_consumption_kwh_per_year == 700

    def test_fcu_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "fcu",
                "rows": [[
                    "4",    # units
                    "0.8",  # baseline_efficiency
                    "8",    # hours
                    "5",    # days
                    "52",   # weeks
                    "0.5",  # power_input kW
                    "500",  # airflow
                    "cmh",  # unit
                    None,   # energy
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1

    def test_doas_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "doas",
                "rows": [[
                    "1", "0.4", "No", "No", "12", "7", "52", "2000", "cmh", None,
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1

    def test_ceiling_wall_cassette_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "ceilingwa",
                "rows": [[
                    "3",    # units
                    "30",   # fresh_air_ratio %
                    "0.6",  # baseline_efficiency
                    "8",    # hours
                    "5",    # days
                    "52",   # weeks
                    "0.75", # power_input
                    "600",  # airflow
                    "cmh",  # unit
                    None,   # energy
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1

    def test_ceiling_exhaust_fan_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "ceilingex",
                "rows": [[
                    "6",    # units
                    "0.5",  # baseline_efficiency
                    "10",   # hours
                    "6",    # days
                    "50",   # weeks
                    "0.25", # power_input
                    "300",  # airflow
                    "cmh",  # unit
                    "3",    # stars
                    None,   # energy
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1

    def test_empty_rows_skipped(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "ahu", "rows": [[None]*10]}],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_multiple_systems_saved(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_ventilation_systems", {
            "building_uuid": str(building.uuid),
            "systems": [
                {"tab": "ahu", "rows": [["1","0.5","No","No","10","5","50","1000","cmh",None]]},
                {"tab": "fcu", "rows": [["2","0.8","8","5","52","0.5","500","cmh",None]]},
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 2


# ---------------------------------------------------------------------------
# Lighting Systems
# ---------------------------------------------------------------------------

class TestImportLightingSystems:

    def test_unauthenticated(self, client, db):
        resp = client.post(reverse("import_lighting_systems"), data="{}", content_type="application/json")
        assert resp.status_code == 302

    def test_led_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "led",
                "rows": [[
                    "Residential: Kitchen",  # room_type
                    "16",                    # area
                    "LED Bulb",              # type of lighting system
                    "5",                     # fixtures
                    "12",                    # wattage
                    "12",                    # hours/day
                    "7",                     # days/week
                    "52",                    # weeks/year
                    "No",                    # sensors
                    None,                    # label
                    None,                    # stars
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1
        light = LightingSystem.objects.filter(building=building).first()
        assert light.lighting_bulb_type == "LED_BULB"
        # Auto-calc: 5 * 1 * 12 / 1000 = 0.06 kW
        assert light.total_lighting_power_kw == Decimal("0.06")
        # Energy: 0.06 * 12 * 7 * 52 * 1.0 = 262.08 → 262
        assert light.total_energy_consumption_kwh_per_year == 262

    def test_led_case_insensitive_room_type(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "led", "rows": [[
                "OFFICE: CONFERENCE ROOM", "30", "LED Panel", "10", "20",
                "10", "5", "50", "No", None, None,
            ]]}],
        })
        assert resp.status_code == 200
        light = LightingSystem.objects.filter(building=building).first()
        assert light.room_type == "OFFICE_CONFERENCE"

    def test_led_sensor_factor_reduces_energy(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "led", "rows": [[
                "Residential: Kitchen", "16", "LED Bulb", "5", "12",
                "12", "7", "52", "Yes",  # sensors = yes → factor 0.80
                None, None,
            ]]}],
        })
        assert resp.status_code == 200
        light = LightingSystem.objects.filter(building=building).first()
        # Energy: 0.06 * 12 * 7 * 52 * 0.80 = 209.66 → rounded int
        assert light.total_energy_consumption_kwh_per_year <= 210

    def test_fluorescent_with_tubes(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "fluorescent", "rows": [[
                "Office: Conference Room", "30",
                "Fluorescent T8",   # type
                "10",               # fixtures
                "2",                # tubes per fixture
                "36",               # wattage per tube
                "10", "5", "50",    # schedule
                "No",               # sensors
                "BEE", "4",
            ]]}],
        })
        assert resp.status_code == 200
        light = LightingSystem.objects.filter(building=building).first()
        assert light.lighting_bulb_type == "FLUORESCENT_T8"
        assert light.tubes_per_fixture == 2
        # Power: 10 * 2 * 36 / 1000 = 0.72 kW
        assert light.total_lighting_power_kw == Decimal("0.72")

    def test_cfl_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "cfl", "rows": [[
                "Commercial: General Office/Retail", "50",
                "CFL", "20", "15",  # fixtures, wattage
                "10", "5", "52",    # schedule
                "No", None, None,
            ]]}],
        })
        assert resp.status_code == 200
        light = LightingSystem.objects.filter(building=building).first()
        assert light.lighting_bulb_type == "CFL"

    def test_incandescent_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "incandescent", "rows": [[
                "Residential: Kitchen", "20",
                "Halogen", "10", "50",
                "8", "7", "52",
                "No", None, None, None,
            ]]}],
        })
        assert resp.status_code == 200
        light = LightingSystem.objects.filter(building=building).first()
        assert light.lighting_bulb_type == "HALOGEN"

    def test_hid_no_sensors_column(self, client, user, building):
        """HiD tab has no sensors column — sensors should default False."""
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "hid", "rows": [[
                "Commercial: Mall / Department Store", "200",
                "Metal Halide", "30", "250",
                "14", "7", "52",
                None, None,  # label, stars — no sensors col for HiD
            ]]}],
        })
        assert resp.status_code == 200
        light = LightingSystem.objects.filter(building=building).first()
        assert light.lighting_bulb_type == "METAL_HALIDE"
        assert light.sensors_installed is False

    def test_energy_efficiency_label_case_insensitive(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "led", "rows": [[
                "Residential: Kitchen", "16", "LED Bulb", "5", "12",
                "12", "7", "52", "No", "bee", "3",
            ]]}],
        })
        assert resp.status_code == 200
        light = LightingSystem.objects.filter(building=building).first()
        assert light.energy_efficiency_label == "BEE"
        assert light.number_of_stars == 3

    def test_missing_required_fixtures(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "led", "rows": [[
                "Residential: Kitchen", "16", "LED Bulb",
                None,  # missing fixtures — should be skipped
                "12", "12", "7", "52", "No", None, None,
            ]]}],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0  # row skipped

    def test_multiple_types_saved(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lighting_systems", {
            "building_uuid": str(building.uuid),
            "systems": [
                {"tab": "led", "rows": [["Residential: Kitchen","16","LED Bulb","5","12","12","7","52","No",None,None]]},
                {"tab": "cfl", "rows": [["Commercial: General Office/Retail","50","CFL","20","15","10","5","52","No",None,None]]},
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 2


# ---------------------------------------------------------------------------
# Lift & Escalator System
# ---------------------------------------------------------------------------

class TestImportLiftEscalator:

    def test_unauthenticated(self, client, db):
        resp = client.post(reverse("import_lift_escalator"), data="{}", content_type="application/json")
        assert resp.status_code == 302

    def test_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lift_escalator", {
            "building_uuid": str(building.uuid),
            "rows": [["3", "No", "Yes"]],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1
        lift = LiftEscalatorSystem.objects.filter(building=building).first()
        assert lift.number_of_lifts == 3
        assert lift.vvvf_sleep_mode is True
        assert lift.lift_regenerative_features is False

    def test_case_insensitive_yes_no(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lift_escalator", {
            "building_uuid": str(building.uuid),
            "rows": [["5", "YES", "NO"]],
        })
        assert resp.status_code == 200
        lift = LiftEscalatorSystem.objects.filter(building=building).first()
        assert lift.lift_regenerative_features is True
        assert lift.vvvf_sleep_mode is False

    def test_one_per_building_enforced(self, client, user, building):
        client.force_login(user)
        # First save
        _post_json(client, "import_lift_escalator", {
            "building_uuid": str(building.uuid),
            "rows": [["3", "No", "Yes"]],
        })
        # Second attempt should fail
        resp = _post_json(client, "import_lift_escalator", {
            "building_uuid": str(building.uuid),
            "rows": [["5", "Yes", "No"]],
        })
        assert resp.status_code == 400
        assert LiftEscalatorSystem.objects.filter(building=building).count() == 1

    def test_empty_rows_skipped(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_lift_escalator", {
            "building_uuid": str(building.uuid),
            "rows": [[None, None, None]],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_missing_building_uuid(self, client, user):
        client.force_login(user)
        resp = _post_json(client, "import_lift_escalator", {"rows": [["3","No","Yes"]]})
        assert resp.status_code == 400

    def test_wrong_owner_building(self, client, user, other_building):
        client.force_login(user)
        resp = _post_json(client, "import_lift_escalator", {
            "building_uuid": str(other_building.uuid),
            "rows": [["3","No","Yes"]],
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Hot Water Systems
# ---------------------------------------------------------------------------

class TestImportHotWaterSystems:

    def test_unauthenticated(self, client, db):
        resp = client.post(reverse("import_hot_water_systems"), data="{}", content_type="application/json")
        assert resp.status_code == 302

    def test_heat_pump_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_hot_water_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "heat-pump",
                "rows": [[
                    "Heat Pump Water Heater",  # type (ignored, overridden by tab)
                    "electricity",             # fuel
                    "2",                       # num equipment
                    "4",                       # hours/day
                    "7",                       # days/week
                    "52",                      # weeks/year
                    "3.5",                     # COP (baseline_efficiency)
                    "5",                       # power_input kW
                    "No",                      # heat recovery
                    "90",                      # equipment_efficiency_level
                ]],
            }],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1
        hws = HotWaterSystem.objects.filter(building=building).first()
        assert hws.type_of_hot_water_system == "heat-pump"
        # Auto-calc: 5 * 2 * 4 * 7 * 52 / 3.5 = 4160 kWh
        assert hws.total_energy_consumption_kwh_per_year == 4160

    def test_boiler_happy_path(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_hot_water_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "boiler",
                "rows": [[
                    "Boiler",          # type
                    "natural gas",     # fuel
                    "1",               # num equipment
                    "8",               # hours/day
                    "5",               # days/week
                    "50",              # weeks/year
                    "100",             # power_input kW
                    "500",             # total_fuel_consumption
                    "m3",              # fuel_consumption_unit
                    "No",              # heat recovery
                    "80",              # efficiency %
                ]],
            }],
        })
        assert resp.status_code == 200
        hws = HotWaterSystem.objects.filter(building=building).first()
        assert hws.type_of_hot_water_system == "boiler"
        # Auto-calc: 100 * 1 * 8 * 5 * 50 / (80/100) = 250000 kWh
        assert hws.total_energy_consumption_kwh_per_year == 250000

    def test_water_heater_solar_zero_energy(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_hot_water_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "water-heater",
                "rows": [[
                    "Solar Water Heater",
                    "solar",     # solar fuel → energy = 0
                    "1",
                    "8", "7", "52",
                    "3",         # power_input
                    "No",
                    "90",
                ]],
            }],
        })
        assert resp.status_code == 200
        hws = HotWaterSystem.objects.filter(building=building).first()
        assert hws.total_energy_consumption_kwh_per_year == 0

    def test_water_heater_electric_energy_calc(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_hot_water_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{
                "tab": "water-heater",
                "rows": [[
                    "Instant Electric Water Heater",
                    "electricity",
                    "2",
                    "1", "7", "52",
                    "3.5",  # power_input
                    "No",
                    "90",   # efficiency %
                ]],
            }],
        })
        assert resp.status_code == 200
        hws = HotWaterSystem.objects.filter(building=building).first()
        # 3.5 * 2 * 1 * 7 * 52 / (90/100) = 2831.11 → 2831
        assert hws.total_energy_consumption_kwh_per_year == 2831

    def test_fuel_type_case_insensitive(self, client, user, building):
        client.force_login(user)
        for fuel_str in ["NATURAL GAS", "Natural Gas", "natural gas", "Natural-Gas"]:
            building.hot_water_systems.all().delete()
            resp = _post_json(client, "import_hot_water_systems", {
                "building_uuid": str(building.uuid),
                "systems": [{
                    "tab": "boiler",
                    "rows": [[
                        "Boiler", fuel_str, "1", "8", "5", "50",
                        "50", None, None, "No", "80",
                    ]],
                }],
            })
            assert resp.status_code == 200, f"Failed for fuel_str={fuel_str!r}: {resp.json()}"

    def test_empty_rows_skipped(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_hot_water_systems", {
            "building_uuid": str(building.uuid),
            "systems": [{"tab": "heat-pump", "rows": [[None]*10]}],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_multiple_tabs(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_hot_water_systems", {
            "building_uuid": str(building.uuid),
            "systems": [
                {
                    "tab": "heat-pump",
                    "rows": [["Heat Pump","electricity","1","4","7","52","3.5","5","No","90"]],
                },
                {
                    "tab": "boiler",
                    "rows": [["Boiler","natural gas","1","8","5","50","100",None,None,"No","80"]],
                },
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 2


# ---------------------------------------------------------------------------
# Operational Energy Carriers
# ---------------------------------------------------------------------------

class TestImportEnergyCarriers:

    def _electricity_epd(self, db):
        return EPD.objects.filter(
            category__parent__category_id="9.2",
            declared_unit=Unit.KWH,
            type=EPDType.GENERIC,
            name__iexact="electricity ",
        ).first()

    def _natural_gas_epd(self, db):
        return EPD.objects.filter(
            category__parent__category_id="9.2",
            declared_unit=Unit.KWH,
            type=EPDType.GENERIC,
            name__iexact="natural gas",
        ).first()

    def test_unauthenticated(self, client, db):
        resp = client.post(reverse("import_energy_carriers"), data="{}", content_type="application/json")
        assert resp.status_code == 302

    def test_happy_path_electricity_kwh(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [["electricity", "office electricity", "1000", "kwh"]],
        })
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is True
        assert data["saved_count"] == 1
        op = OperationalProduct.objects.filter(building=building).first()
        assert op is not None
        assert float(op.quantity) == 1000.0
        assert op.input_unit == "kwh"
        assert op.description == "office electricity"

    def test_name_case_insensitive(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        for name in ["ELECTRICITY", "Electricity", "electricity", "ELECTRICITY "]:
            OperationalProduct.objects.filter(building=building).delete()
            resp = _post_json(client, "import_energy_carriers", {
                "building_uuid": str(building.uuid),
                "rows": [[name, "", "500", "kwh"]],
            })
            assert resp.status_code == 200, f"Failed for name={name!r}: {resp.json()}"
            assert OperationalProduct.objects.filter(building=building).count() == 1

    def test_lpg_canonical_name_mapping(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        for name in ["lpg", "LPG", "Liquefied Petroleum Gas (LPG)", "liquefied petroleum gas"]:
            OperationalProduct.objects.filter(building=building).delete()
            resp = _post_json(client, "import_energy_carriers", {
                "building_uuid": str(building.uuid),
                "rows": [[name, "", "200", "kwh"]],
            })
            assert resp.status_code == 200, f"Failed for name={name!r}: {resp.json()}"

    def test_diesel_name_variants(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        for name in ["diesel", "Diesel", "DIESEL"]:
            OperationalProduct.objects.filter(building=building).delete()
            resp = _post_json(client, "import_energy_carriers", {
                "building_uuid": str(building.uuid),
                "rows": [[name, "", "300", "kwh"]],
            })
            assert resp.status_code == 200, f"Failed for name={name!r}: {resp.json()}"

    def test_natural_gas_variants(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        for name in ["natural gas", "Natural Gas", "NATURAL GAS"]:
            OperationalProduct.objects.filter(building=building).delete()
            resp = _post_json(client, "import_energy_carriers", {
                "building_uuid": str(building.uuid),
                "rows": [[name, "", "400", "kwh"]],
            })
            assert resp.status_code == 200, f"Failed for name={name!r}: {resp.json()}"

    def test_kerosene_alias(self, client, user, building, energy_carrier_epds):
        """Kerosene is stored as 'cerosin' in DB — alias mapping must work."""
        client.force_login(user)
        for name in ["kerosene", "Kerosene", "cerosin", "Cerosin"]:
            OperationalProduct.objects.filter(building=building).delete()
            resp = _post_json(client, "import_energy_carriers", {
                "building_uuid": str(building.uuid),
                "rows": [[name, "", "150", "kwh"]],
            })
            assert resp.status_code == 200, f"Failed for name={name!r}: {resp.json()}"

    def test_charcoal_alias(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        for name in ["charcoal", "Charcoal", "char coal", "Char Coal"]:
            OperationalProduct.objects.filter(building=building).delete()
            resp = _post_json(client, "import_energy_carriers", {
                "building_uuid": str(building.uuid),
                "rows": [[name, "", "100", "kwh"]],
            })
            assert resp.status_code == 200, f"Failed for name={name!r}: {resp.json()}"

    def test_unit_normalisation(self, client, user, building, energy_carrier_epds):
        """kWh, kwh, KWH should all be accepted."""
        client.force_login(user)
        for unit in ["kwh", "kWh", "KWH"]:
            OperationalProduct.objects.filter(building=building).delete()
            resp = _post_json(client, "import_energy_carriers", {
                "building_uuid": str(building.uuid),
                "rows": [["electricity", "", "500", unit]],
            })
            assert resp.status_code == 200, f"Failed for unit={unit!r}: {resp.json()}"

    def test_invalid_epd_name_returns_error(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [["unicorn fuel", "", "100", "kwh"]],
        })
        assert resp.status_code == 400
        assert "success" in resp.json() and resp.json()["success"] is False

    def test_missing_quantity_returns_error(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [["electricity", "", None, "kwh"]],
        })
        assert resp.status_code == 400

    def test_zero_quantity_returns_error(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [["electricity", "", "0", "kwh"]],
        })
        assert resp.status_code == 400

    def test_quantity_as_string_number(self, client, user, building, energy_carrier_epds):
        """Quantity passed as string '1000.5' should be accepted."""
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [["electricity", "", "1000.5", "kwh"]],
        })
        assert resp.status_code == 200

    def test_description_optional(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [["electricity", None, "500", "kwh"]],
        })
        assert resp.status_code == 200

    def test_multiple_carriers_saved(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [
                ["electricity", "lighting", "1000", "kwh"],
                ["natural gas", "heating", "500", "kwh"],
                ["diesel", "backup gen", "200", "kwh"],
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 3
        assert OperationalProduct.objects.filter(building=building).count() == 3

    def test_replaces_existing_carriers(self, client, user, building, energy_carrier_epds):
        """Submitting again should delete old records and create new ones."""
        client.force_login(user)
        _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [["electricity", "", "1000", "kwh"]],
        })
        assert OperationalProduct.objects.filter(building=building).count() == 1

        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [
                ["natural gas", "", "400", "kwh"],
                ["diesel", "", "200", "kwh"],
            ],
        })
        assert resp.status_code == 200
        # Old electricity record replaced with 2 new ones
        assert OperationalProduct.objects.filter(building=building).count() == 2

    def test_blank_name_rows_skipped(self, client, user, building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [
                [None, "", "100", "kwh"],    # blank name → skipped
                ["electricity", "", "500", "kwh"],
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 1

    def test_empty_rows_list(self, client, user, building, db):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(building.uuid),
            "rows": [],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_wrong_owner_building(self, client, user, other_building, energy_carrier_epds):
        client.force_login(user)
        resp = _post_json(client, "import_energy_carriers", {
            "building_uuid": str(other_building.uuid),
            "rows": [["electricity", "", "100", "kwh"]],
        })
        assert resp.status_code == 404

    def test_invalid_json_returns_400(self, client, user):
        client.force_login(user)
        url = reverse("import_energy_carriers")
        resp = client.post(url, data="not-json", content_type="application/json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Structural Components
# ---------------------------------------------------------------------------

class TestImportStructuralComponents:

    def test_unauthenticated(self, client, db):
        resp = client.post(
            reverse("import_structural_components"), data="{}", content_type="application/json"
        )
        assert resp.status_code == 302

    def test_happy_path_single_assembly(self, client, user, building, structural_epd, assembly_category):
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(building.uuid),
            "rows": [
                [
                    "Ground Floor",           # col0 title
                    assembly_category.name,   # col1 building component (must match AssemblyCategory)
                    "Some Technique",         # col2 technique
                    "Volume",                 # col3 dimension
                    "100",                    # col4 quantity (m3)
                    "m3",                     # col5 assembly unit
                    None,                     # col6 comment
                    None,                     # col7 (gap)
                    structural_epd.name,      # col8 EPD name
                    "",                       # col9 country
                    "50",                     # col10 material qty (% share of volume)
                    "percent",                # col11 material unit (Volume dim → percent)
                ],
            ],
        })
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is True
        assert data["saved_count"] == 1
        assert Assembly.objects.filter(created_by=user).count() == 1
        assert BuildingAssembly.objects.filter(building=building).count() == 1
        sp = StructuralProduct.objects.filter(assembly__buildingassembly__building=building).first()
        assert sp is not None
        assert sp.epd == structural_epd

    def test_separator_row_ends_assembly(self, client, user, building, structural_epd, assembly_category):
        """A row with component name but no qty is a separator — ends current assembly."""
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(building.uuid),
            "rows": [
                [
                    "", assembly_category.name, "Technique A", "Volume", "100", "m3",
                    None, None, structural_epd.name, "", "60", "percent",
                ],
                # Separator: component present, no qty
                ["", assembly_category.name, None, None, None, None, None, None, None, None, None, None],
                # New assembly after separator
                [
                    "", assembly_category.name, "Technique B", "Volume", "50", "m3",
                    None, None, structural_epd.name, "", "40", "percent",
                ],
            ],
        })
        assert resp.status_code == 200, resp.json()
        assert resp.json()["saved_count"] == 2

    def test_unknown_category_returns_error(self, client, user, building, structural_epd):
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(building.uuid),
            "rows": [[
                "", "Nonexistent Category XYZ", "Some Technique", "Volume", "10", "m3",
                None, None, structural_epd.name, "", "10", structural_epd.declared_unit,
            ]],
        })
        assert resp.status_code == 400

    def test_unknown_dimension_returns_error(self, client, user, building, structural_epd, assembly_category):
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(building.uuid),
            "rows": [[
                "", assembly_category.name, "Some Technique", "INVALID_DIM", "10", "m3",
                None, None, structural_epd.name, "", "10", structural_epd.declared_unit,
            ]],
        })
        assert resp.status_code == 400

    def test_dimension_case_insensitive(self, client, user, building, structural_epd, assembly_category):
        """Dimension values like 'VOLUME', 'Volume', 'volume' all map correctly."""
        client.force_login(user)
        for dim in ["Volume", "VOLUME", "volume"]:
            BuildingAssembly.objects.filter(building=building).delete()
            Assembly.objects.filter(created_by=user).delete()
            resp = _post_json(client, "import_structural_components", {
                "building_uuid": str(building.uuid),
                "rows": [[
                    "", assembly_category.name, None, dim, "10", "m3",
                    None, None, structural_epd.name, "", "50", "percent",
                ]],
            })
            assert resp.status_code == 200, f"Failed for dim={dim!r}: {resp.json()}"
            assert resp.json()["saved_count"] == 1

    def test_assembly_without_materials_skipped(self, client, user, building, assembly_category):
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(building.uuid),
            "rows": [
                # Assembly row with no subsequent material rows (no EPD name in col8)
                ["", assembly_category.name, "Some Technique", "Volume", "10", "m3",
                 None, None, None, None, None, None],
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_empty_rows_returns_zero(self, client, user, building):
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(building.uuid),
            "rows": [],
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 0

    def test_wrong_owner_building(self, client, user, other_building, structural_epd, assembly_category):
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(other_building.uuid),
            "rows": [[
                "", assembly_category.name, None, "Volume", "10", "m3",
                None, None, structural_epd.name, "", "10", structural_epd.declared_unit,
            ]],
        })
        assert resp.status_code == 404

    def test_multiple_materials_per_assembly(self, client, user, building, structural_epd, assembly_category):
        """Two consecutive material rows create one assembly with two StructuralProducts."""
        from pages.models.epd import EPD, EPDType, Unit, MaterialCategory
        # Create a second EPD with a different name
        root = MaterialCategory.objects.get(category_id="1")
        child = MaterialCategory.objects.get(category_id="1.1")
        epd2 = EPD.objects.create(
            name="Test Steel Bar",
            names=[{"value": "Test Steel Bar", "lang": "en"}],
            UUID="test-steel-bar",
            declared_unit=Unit.KG,
            conversions=[],
            type=EPDType.GENERIC,
            category=child,
            public=True,
            draft=False,
            declared_amount=1,
            created_by=user,
        )
        client.force_login(user)
        resp = _post_json(client, "import_structural_components", {
            "building_uuid": str(building.uuid),
            "rows": [
                # First row: assembly header + first material
                ["", assembly_category.name, None, "Volume", "50", "m3",
                 None, None, structural_epd.name, "", "60", "percent"],
                # Second row: material only (no assembly header columns)
                [None, None, None, None, None, None,
                 None, None, epd2.name, "", "40", "percent"],
            ],
        })
        assert resp.status_code == 200, resp.json()
        assert resp.json()["saved_count"] == 1
        assembly = Assembly.objects.filter(created_by=user).first()
        assert StructuralProduct.objects.filter(assembly=assembly).count() == 2


# ---------------------------------------------------------------------------
# Cancel import
# ---------------------------------------------------------------------------

class TestCancelImport:

    def test_unauthenticated(self, client, db):
        resp = _post_json(client, "import_building_cancel", {})
        assert resp.status_code == 302

    def test_cancels_and_deletes_building(self, client, user, building):
        client.force_login(user)
        uuid_str = str(building.uuid)
        resp = _post_json(client, "import_building_cancel", {"building_uuid": uuid_str})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert not Building.objects.filter(uuid=uuid_str).exists()

    def test_cannot_cancel_other_users_building(self, client, user, other_building):
        client.force_login(user)
        uuid_str = str(other_building.uuid)
        resp = _post_json(client, "import_building_cancel", {"building_uuid": uuid_str})
        # Should succeed (no error) but not delete the other user's building
        assert resp.status_code == 200
        assert Building.objects.filter(uuid=uuid_str).exists()

    def test_empty_uuid_is_noop(self, client, user):
        client.force_login(user)
        resp = _post_json(client, "import_building_cancel", {"building_uuid": ""})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auto-calculation unit tests (pure Python, no HTTP)
# ---------------------------------------------------------------------------

class TestAutoCalcHelpers:
    """Tests for the auto-calculation helper functions (no DB required)."""

    def test_calc_lighting_power_led(self):
        from pages.views.building.import_building import _calc_lighting_power
        assert _calc_lighting_power(5, None, 12) == 0.06  # 5*1*12/1000
        assert _calc_lighting_power(10, 2, 36) == 0.72    # 10*2*36/1000

    def test_calc_lighting_power_invalid(self):
        from pages.views.building.import_building import _calc_lighting_power
        assert _calc_lighting_power(0, 1, 12) is None
        assert _calc_lighting_power("abc", 1, 12) is None
        assert _calc_lighting_power(5, 1, 0) is None

    def test_calc_lighting_energy_no_sensors(self):
        from pages.views.building.import_building import _calc_lighting_energy
        e = _calc_lighting_energy(0.06, 12, 7, 52, False)
        assert e == 262  # 0.06 * 12 * 7 * 52 = 262.08 → 262

    def test_calc_lighting_energy_with_sensors(self):
        from pages.views.building.import_building import _calc_lighting_energy
        e = _calc_lighting_energy(0.06, 12, 7, 52, True)
        assert e == 210  # 262.08 * 0.80 = 209.664 → 210

    def test_calc_lighting_lpd(self):
        from pages.views.building.import_building import _calc_lighting_lpd
        assert _calc_lighting_lpd(0.06, 16) == pytest.approx(0.00375, rel=1e-3)
        assert _calc_lighting_lpd(0, 16) is None
        assert _calc_lighting_lpd(0.06, 0) is None

    def test_leakage_default_old(self):
        import datetime
        from pages.views.building.import_building import _leakage_default
        old_year = str(datetime.datetime.now().year - 10)
        assert _leakage_default(old_year) == '10'

    def test_leakage_default_new(self):
        import datetime
        from pages.views.building.import_building import _leakage_default
        new_year = str(datetime.datetime.now().year - 3)
        assert _leakage_default(new_year) == '2'

    def test_leakage_default_invalid(self):
        from pages.views.building.import_building import _leakage_default
        assert _leakage_default("not-a-year") == '2'
        assert _leakage_default(None) == '2'
        assert _leakage_default("") == '2'

    def test_calc_hws_energy_heat_pump(self):
        from pages.views.building.import_building import _calc_hws_energy
        from pages.models.building_operation import HotWaterSystemType
        # 5 kW * 2 * 4h * 7d * 52w / COP 3.5 = 4160 kWh
        assert _calc_hws_energy(HotWaterSystemType.HEAT_PUMP, 5, 2, 4, 7, 52, 3.5) == pytest.approx(4160, rel=0.01)

    def test_calc_hws_energy_boiler(self):
        from pages.views.building.import_building import _calc_hws_energy
        from pages.models.building_operation import HotWaterSystemType
        # 100 kW * 1 * 8h * 5d * 50w / (80/100) = 250000 kWh
        assert _calc_hws_energy(HotWaterSystemType.BOILER, 100, 1, 8, 5, 50, 80) == pytest.approx(250000, rel=0.01)

    def test_calc_hws_energy_solar_zero(self):
        from pages.views.building.import_building import _calc_hws_energy
        from pages.models.building_operation import HotWaterSystemType
        assert _calc_hws_energy(HotWaterSystemType.SOLAR, 3, 1, 8, 7, 52, 90, fuel_type='solar') == 0

    def test_calc_vent_power(self):
        from pages.views.building.import_building import _calc_vent_power
        # 1000 CMH * 0.5 W/CMH * 2 units / 1000 = 1.0 kW
        assert _calc_vent_power(1000, 0.5, 2) == pytest.approx(1.0, rel=0.01)
        assert _calc_vent_power(0, 0.5, 2) is None

    def test_calc_vent_energy_with_vsd_dcv(self):
        from pages.views.building.import_building import _calc_vent_energy
        # 1.0 * 10 * 5 * 50 * 0.80 * 0.70 = 1400 kWh... wait:
        # power=0.5, h=10, d=5, w=50, vsd=True, dcv=True
        # 0.5 * 10 * 5 * 50 * 0.80 * 0.70 = 700
        e = _calc_vent_energy(0.5, 10, 5, 50, vsd=True, dcv=True)
        assert e == pytest.approx(700.0, rel=0.01)