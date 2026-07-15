"""
Tests for calculate_impacts() with BoQ assemblies.

In BoQ assemblies (is_boq=True), the assembly-level dimension is ignored.
Dimension is inferred from the product's input_unit instead.
"""
from decimal import Decimal

import pytest

from pages.models.epd import Unit
from pages.models.assembly import Assembly, AssemblyMode, AssemblyDimension
from pages.views.building.impact_calculation import calculate_impacts, ImpactCalculationError

from pages.tests.test_impact_calculation import (
    create_epd,
    create_impact,
    create_epd_impact,
    create_assembly,
    create_product,
)


@pytest.fixture
def create_boq_assembly():
    def _create_assembly():
        return Assembly.objects.create(
            mode=AssemblyMode.CUSTOM,
            dimension=AssemblyDimension.AREA,  # irrelevant for BoQ
            is_boq=True,
        )
    return _create_assembly


def _calc_boq(p):
    """Run calculate_impacts for a BoQ product (dimension=None, assembly_quantity=1, floor_area=1)."""
    return calculate_impacts(
        dimension=None,
        assembly_quantity=1,
        total_floor_area=1,
        p=p,
    )


def _gwp(impacts):
    for i in impacts:
        if i["impact_type"].__str__() == "gwp a1a3":
            return i["impact_value"]
    raise AssertionError("No gwp a1a3 impact found")


# ---------------------------------------------------------------------------
# BoQ: direct unit matches — dimension inferred from input_unit
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_boq_pcs(create_epd, create_epd_impact, create_boq_assembly, create_product):
    """BoQ + pcs EPD → Factor = product_quantity."""
    epd = create_epd("Tile", Unit.PCS, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    p = create_product(assembly, epd, Decimal("4"), Unit.PCS)
    assert _gwp(_calc_boq(p)) == pytest.approx(Decimal("12"))


@pytest.mark.django_db
def test_boq_m(create_epd, create_epd_impact, create_boq_assembly, create_product):
    """BoQ + m EPD with input_unit=m → direct match, Factor = 1 × 4 = 4."""
    epd = create_epd("Pipe", Unit.M, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    p = create_product(assembly, epd, Decimal("4"), Unit.M)
    assert _gwp(_calc_boq(p)) == pytest.approx(Decimal("12"))


@pytest.mark.django_db
def test_boq_m2(create_epd, create_epd_impact, create_boq_assembly, create_product):
    """BoQ + m² EPD with input_unit=m2 → direct match, Factor = 1 × 4 = 4."""
    epd = create_epd("Slab", Unit.M2, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    p = create_product(assembly, epd, Decimal("4"), Unit.M2)
    assert _gwp(_calc_boq(p)) == pytest.approx(Decimal("12"))


@pytest.mark.django_db
def test_boq_m3(create_epd, create_epd_impact, create_boq_assembly, create_product):
    """BoQ + m³ EPD with input_unit=m3 → direct match, Factor = 1 × 4 = 4."""
    epd = create_epd("Concrete", Unit.M3, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    p = create_product(assembly, epd, Decimal("4"), Unit.M3)
    assert _gwp(_calc_boq(p)) == pytest.approx(Decimal("12"))


@pytest.mark.django_db
def test_boq_kg(create_epd, create_epd_impact, create_boq_assembly, create_product):
    """BoQ + kg EPD with input_unit=kg → direct match, Factor = 1 × 4 = 4."""
    epd = create_epd("Steel", Unit.KG, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    p = create_product(assembly, epd, Decimal("4"), Unit.KG)
    assert _gwp(_calc_boq(p)) == pytest.approx(Decimal("12"))


@pytest.mark.django_db
def test_boq_ton(create_epd, create_epd_impact, create_boq_assembly, create_product):
    """BoQ + ton EPD with input_unit=ton → direct match (quantity already in tons).

    Common for TGO steel/rebar EPDs declared per ton. Factor = 1 × 4 = 4 tons,
    impact = 3 kgCO2e/ton × 4 = 12 (no kg conversion because input is in tons).
    """
    epd = create_epd("Rebar", Unit.TON, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    p = create_product(assembly, epd, Decimal("4"), Unit.TON)
    assert _gwp(_calc_boq(p)) == pytest.approx(Decimal("12"))


# ---------------------------------------------------------------------------
# BoQ: conversions used when input_unit ≠ declared_unit
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_boq_kg_epd_with_m3_input_uses_volume_density(
    create_epd, create_epd_impact, create_boq_assembly, create_product
):
    """BoQ + kg EPD but input_unit=m3 → inferred VOLUME dimension.
    Volume→kg: Factor = assembly_qty × share × volume_density.
    product_quantity stored as m3 directly (not percent for BoQ).
    Factor = 1 × 4 × 2 = 8  →  impact = 3 × 8 = 24.
    """
    epd = create_epd("BoQ Dense", Unit.KG, [
        {"name": "volume density", "value": "2", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    p = create_product(assembly, epd, Decimal("4"), Unit.M3)
    # input_unit=M3 → dimension inferred as VOLUME
    # Volume+KG: Factor = 1 × 4 × 2 = 8
    assert _gwp(_calc_boq(p)) == pytest.approx(Decimal("24"))


@pytest.mark.django_db
def test_boq_m3_epd_with_kg_input_raises(
    create_epd, create_epd_impact, create_boq_assembly, create_product
):
    """BoQ + m³ EPD with input_unit=kg → inferred MASS dimension.
    Mass→m³ requires volume density. If missing, raise ImpactCalculationError.
    """
    epd = create_epd("BoQ No density", Unit.M3, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_boq_assembly()
    # Create with M3 (valid for M3 EPD), then override to KG at runtime
    p = create_product(assembly, epd, Decimal("4"), Unit.M3)
    p.input_unit = Unit.KG  # simulate KG input without re-triggering model validation
    with pytest.raises(ImpactCalculationError):
        _calc_boq(p)
