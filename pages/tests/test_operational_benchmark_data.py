"""Tests for the operational-carbon (Layer 1) EUI benchmark.

Covers:
- ``get_operational_benchmark_for_building``: taxonomy/climate/country resolution,
  the best-practice guard, and the "blank cell -> no benchmark" rule.
- ``calculate_operational_benchmark_position``: position %, tier labels, gap stats,
  including the exact worked example from the methodology spec §5.
"""

from decimal import Decimal

import pytest

from cities_light.models import Country

from pages.models.building import (
    Building,
    BuildingCategory,
    BuildingSubcategory,
    CategorySubcategory,
)
from pages.models.climate_type import ClimateType
from pages.views.building.operational_benchmark_data import (
    NATIONAL_AVG_EUI,
    BEST_PRACTICE_INDIA,
    get_operational_benchmark_for_building,
    calculate_operational_benchmark_position,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def make_country():
    def _make(name, code2):
        return Country.objects.create(name=name, code2=code2)
    return _make


@pytest.fixture
def make_building():
    def _make(country=None, climate="composite", category_name=None,
              subcategory_name=None, total_floor_area=Decimal("1000"),
              cond_floor_area=None, reference_period=50):
        climate_obj, _ = ClimateType.objects.get_or_create(name=climate)
        category = None
        if category_name and subcategory_name:
            cat, _ = BuildingCategory.objects.get_or_create(name=category_name)
            sub, _ = BuildingSubcategory.objects.get_or_create(name=subcategory_name)
            category, _ = CategorySubcategory.objects.get_or_create(
                category=cat, subcategory=sub, country=country,
            )
        return Building.objects.create(
            name="Test Building",
            country=country,
            climate_zone=climate_obj,
            category=category,
            total_floor_area=total_floor_area,
            cond_floor_area=cond_floor_area,
            reference_period=reference_period,
        )
    return _make


# ---------------------------------------------------------------------------
# Benchmark resolution
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_india_office_resolves(make_country, make_building):
    india = make_country("India", "IN")
    # Office/Business > Day time use, Composite, >50% AC (cond>=50% of total)
    building = make_building(
        country=india, climate="composite",
        category_name="Office/Business", subcategory_name="Day time use",
        total_floor_area=Decimal("1000"), cond_floor_area=Decimal("800"),
    )
    entry = get_operational_benchmark_for_building(building)
    assert entry is not None
    assert entry["building_type"] == "Office"
    assert entry["sub_type"] == ">50% AC"
    assert entry["climate_label"] == "Composite"
    assert entry["national_average_eui"] == 179.0
    assert entry["best_practice_eui"] == 139.6  # ECBC Super tier


@pytest.mark.django_db
def test_office_ac_split_below_50(make_country, make_building):
    india = make_country("India", "IN")
    building = make_building(
        country=india, climate="composite",
        category_name="Office/Business", subcategory_name="Day time use",
        total_floor_area=Decimal("1000"), cond_floor_area=Decimal("300"),
    )
    entry = get_operational_benchmark_for_building(building)
    assert entry["sub_type"] == "<50% AC"
    assert entry["national_average_eui"] == 86.0


@pytest.mark.django_db
def test_missing_cond_area_defaults_to_above_50(make_country, make_building):
    india = make_country("India", "IN")
    building = make_building(
        country=india, climate="composite",
        category_name="Office/Business", subcategory_name="Day time use",
        total_floor_area=Decimal("1000"), cond_floor_area=None,
    )
    entry = get_operational_benchmark_for_building(building)
    assert entry["sub_type"] == ">50% AC"
    assert entry["is_approximation"] is True


@pytest.mark.django_db
def test_non_india_uses_leed_best_practice(make_country, make_building):
    """Rewritten 19.10.2026. This used Vietnam Office Composite = 86, which was
    India's figure copied into Vietnam and has been removed. Thailand exercises
    the same guard: its office figure of 59.26 is below LEED's 136, so best
    practice is hidden."""
    thailand = make_country("Thailand", "TH")
    building = make_building(
        country=thailand, climate="composite",
        category_name="Office", subcategory_name="Grade A",
        total_floor_area=Decimal("1000"), cond_floor_area=Decimal("100"),
    )
    entry = get_operational_benchmark_for_building(building)
    assert entry["national_average_eui"] == 59.26
    assert entry["best_practice_eui"] is None  # LEED >= national -> guard hides it


@pytest.mark.django_db
def test_non_india_leed_below_national_shown(make_country, make_building):
    vietnam = make_country("Vietnam", "VN")
    # Vietnam Shopping Mall Tropical Wet national = 300; LEED Retail = 267 < 300 -> shown.
    building = make_building(
        country=vietnam, climate="tropical-wet",
        category_name="Retail", subcategory_name="Shopping Mall",
    )
    entry = get_operational_benchmark_for_building(building)
    assert entry["national_average_eui"] == 300.0
    assert entry["best_practice_eui"] == 267.0


@pytest.mark.django_db
def test_blank_cell_returns_none(make_country, make_building):
    cambodia = make_country("Cambodia", "KH")
    # Cambodia Residential warm-humid has no cell (only Composite=60) -> hide Layer 1.
    building = make_building(
        country=cambodia, climate="warm-humid",
        category_name="Homes", subcategory_name="Middle income",
    )
    assert get_operational_benchmark_for_building(building) is None


@pytest.mark.django_db
def test_unsupported_country_returns_none(make_country, make_building):
    germany = make_country("Germany", "DE")
    building = make_building(
        country=germany, climate="composite",
        category_name="Office", subcategory_name="Grade A",
    )
    assert get_operational_benchmark_for_building(building) is None


@pytest.mark.django_db
def test_no_category_returns_none(make_country, make_building):
    india = make_country("India", "IN")
    building = make_building(country=india, climate="composite")
    assert get_operational_benchmark_for_building(building) is None


@pytest.mark.django_db
def test_cold_climate_falls_back_to_composite(make_country, make_building):
    india = make_country("India", "IN")
    building = make_building(
        country=india, climate="cold",
        category_name="Health care", subcategory_name="Hospital",
    )
    entry = get_operational_benchmark_for_building(building)
    assert entry["climate_label"] == "Composite"
    assert entry["is_approximation"] is True  # cold -> composite flagged


# ---------------------------------------------------------------------------
# Position / tier calculation — exact worked example (spec §5)
# ---------------------------------------------------------------------------

def test_worked_example_india_office_composite():
    """India, Office, Composite, >50% AC, GFA 1000, 160,000 kWh/yr, grid 0.7051."""
    entry = {
        "country": "India", "building_type": "Office", "sub_type": ">50% AC",
        "climate_label": "Composite",
        "national_average_eui": NATIONAL_AVG_EUI[("India", "Office", ">50% AC", "Composite")],
        "best_practice_eui": BEST_PRACTICE_INDIA[("Office", ">50% AC", "Composite")],
        "is_approximation": False,
    }
    actual_eui = 160000 / 1000  # 160
    r = calculate_operational_benchmark_position(actual_eui, entry, 0.7051, 1000, 50)

    assert r["actual_carbon"] == 112.8
    assert r["national_average"] == 126.2
    assert r["best_practice"] == 98.4
    assert r["position_pct"] == 51.8
    assert r["tier"] == "Between best practice and national average"
    assert r["gap_carbon_per_year"] == 14.4
    assert r["gap_energy_kwh"] == 20400
    assert r["gap_carbon_lifetime"] == 719


def test_position_exceeds_best_practice():
    entry = {
        "national_average_eui": 179.0, "best_practice_eui": 139.6,
        "building_type": "Office", "sub_type": ">50% AC",
        "climate_label": "Composite", "is_approximation": False,
    }
    # actual EUI 90 (below best-practice 139.6) -> exceeds best practice
    r = calculate_operational_benchmark_position(90, entry, 0.7051, 1000, 50)
    assert r["tier"] == "Exceeds best practice"
    assert r["position_pct"] == 0.0
    assert r["gap_carbon_per_year"] == 0.0  # already below best practice


def test_position_above_national_average():
    entry = {
        "national_average_eui": 179.0, "best_practice_eui": 139.6,
        "building_type": "Office", "sub_type": ">50% AC",
        "climate_label": "Composite", "is_approximation": False,
    }
    r = calculate_operational_benchmark_position(250, entry, 0.7051, 1000, 50)
    assert r["tier"] == "Above national average"
    assert r["position_pct"] == 100.0


def test_no_best_practice_shows_national_only():
    entry = {
        "national_average_eui": 64.0, "best_practice_eui": None,
        "building_type": "Residential", "sub_type": None,
        "climate_label": "Warm & Humid", "is_approximation": False,
    }
    r = calculate_operational_benchmark_position(80, entry, 0.7051, 1000, 50)
    assert r["has_best_practice"] is False
    assert r["position_pct"] is None
    assert r["tier"] == "Above national average"
    assert r["best_practice"] is None


def test_zero_grid_factor_returns_none():
    entry = {
        "national_average_eui": 179.0, "best_practice_eui": 139.6,
        "building_type": "Office", "sub_type": ">50% AC",
        "climate_label": "Composite", "is_approximation": False,
    }
    assert calculate_operational_benchmark_position(160, entry, 0, 1000, 50) is None


# ---------------------------------------------------------------------------
# Indonesia, replaced 19.10.2026 from the national studies
# ---------------------------------------------------------------------------

def test_indonesia_benchmarks_sit_below_the_wasteful_threshold():
    """The previous figures were above the studies' own "wasteful" line, so
    almost any Indonesian building scored well against its national average.

    BPPT 2020 wasteful thresholds: large office >193, 3-star hotel >216,
    5-star >270, supermall >403, hospital Class B >253.
    """
    from pages.views.building.operational_benchmark_data import NATIONAL_AVG_EUI
    ceilings = {
        ("Office", ">50% AC"): 193,
        ("Office", "<50% AC"): 285,
        ("Hotel", "Up to 3-star"): 216,
        ("Hotel", "Above 3-star"): 270,
        ("Shopping Mall", None): 403,
        ("Hospital", None): 253,
    }
    for (btype, sub), ceiling in ceilings.items():
        for key, value in NATIONAL_AVG_EUI.items():
            if key[0] == "Indonesia" and key[1] == btype and key[2] == sub:
                assert value < ceiling, f"{btype} {sub}: {value} is not below {ceiling}"


def test_indonesia_covers_every_climate_its_buildings_use():
    """The studies are national and do not resolve by climate, so one figure
    per type applies to all zones. 252 of 430 Indonesian buildings are in the
    composite zone, which previously had no row at all - only 15 of 430 found
    any benchmark."""
    from pages.views.building.operational_benchmark_data import NATIONAL_AVG_EUI
    needed = {"Tropical Wet", "Composite", "Warm & Humid", "Temperate", "Hot & Dry"}
    for btype in ("Office", "Hotel", "Shopping Mall", "Hospital", "Residential"):
        got = {k[3] for k in NATIONAL_AVG_EUI if k[0] == "Indonesia" and k[1] == btype}
        assert needed <= got, f"{btype} missing {needed - got}"


def test_indonesia_residential_exists_and_matches_the_measured_average():
    """C40 2023 measured 108 kWh/m2/yr across Jakarta homes. BEAT carried 60,
    little over half, and only under Temperate - so 140 Indonesian homes were
    judged against a figure nearly half the measured average, or against
    nothing at all."""
    from pages.views.building.operational_benchmark_data import NATIONAL_AVG_EUI
    for climate in ("Tropical Wet", "Composite"):
        assert NATIONAL_AVG_EUI[("Indonesia", "Residential", None, climate)] == 108


def test_the_two_office_figures_follow_the_sources_own_reasoning():
    """BPPT split at 5,000 m2 because large offices use centralised AC and
    medium ones use split units, which is why BEAT's conditioned-area split
    maps onto it."""
    from pages.views.building.operational_benchmark_data import NATIONAL_AVG_EUI
    large = NATIONAL_AVG_EUI[("Indonesia", "Office", ">50% AC", "Composite")]
    medium = NATIONAL_AVG_EUI[("Indonesia", "Office", "<50% AC", "Composite")]
    assert large == 155 and medium == 158


def test_no_country_borrows_indias_benchmarks():
    """15 of Vietnam's 22 rows and 7 of Cambodia's 15 were India's BEE figures
    copied verbatim, so a Vietnamese hotel was told its national average was
    333 kWh/m2/yr - India's warm-and-humid figure from a survey of 1,160
    Indian buildings. Published Vietnamese research puts hotels at 151.

    A borrowed number is invisible: it looks exactly like data.
    """
    from pages.views.building.operational_benchmark_data import NATIONAL_AVG_EUI as N
    india = {(k[1], k[2], k[3]): v for k, v in N.items() if k[0] == "India"}
    for key, value in N.items():
        if key[0] in ("India", "Indonesia"):
            continue
        shape = (key[1], key[2], key[3])
        assert india.get(shape) != value, (
            f"{key[0]} {key[1]} {key[3]} = {value} is India's figure")


def test_india_matches_the_bee_benchmark_pdf():
    """EPI_2024_benchmark.pdf, Bureau of Energy Efficiency, from the UNDP-GEF
    study of 1,160 commercial buildings. Checked against the tables
    19.10.2026."""
    from pages.views.building.operational_benchmark_data import NATIONAL_AVG_EUI as N
    expected = {
        ("Office", "<50% AC", "Warm & Humid"): 101,
        ("Office", ">50% AC", "Warm & Humid"): 182,
        ("Office", "<50% AC", "Composite"): 86,
        ("Hospital", None, "Warm & Humid"): 275,
        ("Hotel", "Up to 3-star", "Warm & Humid"): 215,
        ("Hotel", "Above 3-star", "Warm & Humid"): 333,
        ("Shopping Mall", None, "Warm & Humid"): 428,
        ("Institute", None, "Warm & Humid"): 150,
        ("BPO", None, "Warm & Humid"): 452,
    }
    for (btype, sub, climate), value in expected.items():
        assert N[("India", btype, sub, climate)] == value, (btype, climate)


def test_a_temperate_indian_office_finds_its_benchmark():
    """The BEE tables call that zone "Moderate" and every other row here was
    normalised to BEAT's "Temperate". This one was missed, so a temperate-zone
    Indian office with more than half its area conditioned found nothing."""
    from pages.views.building.operational_benchmark_data import NATIONAL_AVG_EUI as N
    assert ("India", "Office", ">50% AC", "Temperate") in N
    assert ("India", "Office", ">50% AC", "Moderate") not in N
