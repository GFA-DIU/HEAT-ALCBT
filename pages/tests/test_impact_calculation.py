"""
Tests for calculate_impacts() — aligned with the PDF spec:
  "Formula Reference — Embodied Carbon (A1–A3) Developer Edition"

Conversion lookup uses 'name' key in EPD.conversions JSON:
  - "volume density"          → kg/m³
  - "area density"            → kg/m²
  - "linear density"          → kg/m
  - "conversion factor to 1 kg" → "-"

Legacy data without 'name' key falls back to 'unit' string match.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from pages.models.assembly import (
    Assembly,
    AssemblyCategory,
    AssemblyCategoryTechnique,
    AssemblyDimension,
    AssemblyMode,
    AssemblyTechnique,
    StructuralProduct,
)
from pages.models.epd import (
    EPD,
    EPDImpact,
    EPDType,
    Impact,
    ImpactCategoryKey,
    LifeCycleStage,
    MaterialCategory,
    Unit,
)
from pages.views.building.impact_calculation import calculate_impacts, ImpactCalculationError


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def create_impact():
    return Impact.objects.create(
        impact_category=ImpactCategoryKey.GWP,
        life_cycle_stage=LifeCycleStage.A1A3,
    )


@pytest.fixture
def create_epd():
    def _create_epd(name, declared_unit, conversions):
        return EPD.objects.create(
            names=[{"value": name, "lang": "en"}],
            type=EPDType.CUSTOM,
            declared_amount=1,
            category=MaterialCategory.objects.first(),
            declared_unit=declared_unit,
            conversions=conversions,
        )
    return _create_epd


@pytest.fixture
def create_epd_impact(create_impact):
    def _create_epd_impact(epd, value):
        return EPDImpact.objects.create(
            epd=epd,
            impact=create_impact,
            value=value,
        )
    return _create_epd_impact


@pytest.fixture
def create_assembly():
    def _create_assembly(dimension):
        return Assembly.objects.create(
            mode=AssemblyMode.CUSTOM,
            dimension=dimension,
        )
    return _create_assembly


@pytest.fixture
def create_product():
    def _create_product(assembly, epd, quantity, unit):
        category = AssemblyCategory.objects.first()
        technique = AssemblyTechnique.objects.first()
        assemblycategorytechnique, _ = AssemblyCategoryTechnique.objects.get_or_create(
            category=category,
            technique=technique,
            defaults={"description": "Created for test"},
        )
        return StructuralProduct.objects.create(
            assembly=assembly,
            classification=assemblycategorytechnique,
            epd=epd,
            quantity=quantity,
            input_unit=unit,
        )
    return _create_product


# ---------------------------------------------------------------------------
# Helper: run calculate_impacts with assembly_quantity=1, floor_area=1
# ---------------------------------------------------------------------------

def _calc(dimension, p):
    return calculate_impacts(
        dimension=dimension,
        assembly_quantity=1,
        total_floor_area=1,
        p=p,
    )


def _gwp(impacts):
    """Extract the single GWP A1-A3 impact value."""
    for i in impacts:
        if i["impact_type"].__str__() == "gwp a1a3":
            return i["impact_value"]
    raise AssertionError("No gwp a1a3 impact found")


# ---------------------------------------------------------------------------
# PDF Level 1 — Single material, direct matches (Step 2)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_area_m2_direct(create_epd, create_epd_impact, create_assembly, create_product):
    """Area assembly + EPD m² → Factor = assembly_quantity × layer_count."""
    epd = create_epd("Slab", Unit.M2, [])
    create_epd_impact(epd, Decimal("4.12"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("1"), Unit.UNKNOWN)
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(Decimal("4.12"))


@pytest.mark.django_db
def test_volume_m3_direct(create_epd, create_epd_impact, create_assembly, create_product):
    """Volume assembly + EPD m³ → Factor = assembly_quantity × share."""
    epd = create_epd("Concrete", Unit.M3, [])
    create_epd_impact(epd, Decimal("300"))
    assembly = create_assembly(AssemblyDimension.VOLUME)
    p = create_product(assembly, epd, Decimal("50"), Unit.PERCENT)  # 50% share
    # Factor = 1 * 0.50 = 0.5  →  impact = 300 * 0.5 = 150
    assert _gwp(_calc(AssemblyDimension.VOLUME, p)) == pytest.approx(Decimal("150"))


@pytest.mark.django_db
def test_mass_kg_direct(create_epd, create_epd_impact, create_assembly, create_product):
    """Mass assembly + EPD kg → Factor = assembly_quantity × share_of_mass."""
    epd = create_epd("Cement", Unit.KG, [])
    create_epd_impact(epd, Decimal("0.82"))
    assembly = create_assembly(AssemblyDimension.MASS)
    p = create_product(assembly, epd, Decimal("100"), Unit.PERCENT)  # 100% share
    # Factor = 1 * 1.00 = 1  →  impact = 0.82
    assert _gwp(_calc(AssemblyDimension.MASS, p)) == pytest.approx(Decimal("0.82"))


@pytest.mark.django_db
def test_length_m_direct(create_epd, create_epd_impact, create_assembly, create_product):
    """Length assembly + EPD m → Factor = assembly_quantity × count."""
    epd = create_epd("Pipe", Unit.M, [])
    create_epd_impact(epd, Decimal("5"))
    assembly = create_assembly(AssemblyDimension.LENGTH)
    p = create_product(assembly, epd, Decimal("3"), Unit.UNKNOWN)
    # Factor = 1 * 3 = 3  →  impact = 15
    assert _gwp(_calc(AssemblyDimension.LENGTH, p)) == pytest.approx(Decimal("15"))


@pytest.mark.django_db
def test_pcs_any_dimension(create_epd, create_epd_impact, create_assembly, create_product):
    """pcs EPD: Factor = product_quantity, assembly_quantity ignored."""
    epd = create_epd("Tile", Unit.PCS, [])
    create_epd_impact(epd, Decimal("0.045"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("25"), Unit.PCS)
    # Factor = 25  →  impact = 0.045 * 25 = 1.125
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(Decimal("1.125"))


# ---------------------------------------------------------------------------
# PDF Level 1 — Area assembly conversions (Step 3)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_area_m3_via_thickness(create_epd, create_epd_impact, create_assembly, create_product):
    """Area → m³: Factor = assembly_qty × thickness_m.
    thickness = 5 cm → 0.05 m.  EPD impact = 94.  Factor = 1 * 0.05 = 0.05.  Result = 4.7.
    From Excel benchmark.
    """
    epd = create_epd("XPS", Unit.M3, [{"name": "volume density", "value": "32", "unit": "kg/m^3"}])
    create_epd_impact(epd, Decimal("94.0282964318439"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("5"), Unit.CM)
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(
        Decimal("4.70141482159219"), rel=Decimal("1e-10")
    )


@pytest.mark.django_db
def test_area_kg_via_area_density_preferred(create_epd, create_epd_impact, create_assembly, create_product):
    """Area → kg: Option B (preferred) — area density.
    Factor = assembly_qty × area_density = 1 × 12 = 12.  impact = 0.1 * 12 = 1.2.
    """
    epd = create_epd("Paint", Unit.KG, [
        {"name": "area density", "value": "12", "unit": "kg/m^2"},
        {"name": "volume density", "value": "1200", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("0.1"))
    assembly = create_assembly(AssemblyDimension.AREA)
    # quantity/input_unit here is irrelevant when area density exists
    p = create_product(assembly, epd, Decimal("5"), Unit.CM)
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(Decimal("1.2"))


@pytest.mark.django_db
def test_area_kg_via_thickness_volume_density_fallback(create_epd, create_epd_impact, create_assembly, create_product):
    """Area → kg: Option A (fallback) — thickness × volume density (no area density).
    thickness=3.5 cm → 0.035 m.  volume_density=2200.  Factor=1×0.035×2200=77.
    impact = 0.183550838458225 × 77 = 14.1334...  (Excel benchmark)
    """
    epd = create_epd("Cement screed", Unit.KG, [
        {"name": "volume density", "value": "2200", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("0.183550838458225"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("3.5"), Unit.CM)
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(
        Decimal("14.1334145612833"), rel=Decimal("1e-10")
    )


@pytest.mark.django_db
def test_area_kg_via_conversion_factor_last_resort(create_epd, create_epd_impact, create_assembly, create_product):
    """Area → kg: Option C (last resort) — conversion factor to 1 kg.
    Factor = assembly_qty × conv_factor = 1 × 5 = 5.  impact = 2 * 5 = 10.
    """
    epd = create_epd("Material C", Unit.KG, [
        {"name": "conversion factor to 1 kg", "value": "5", "unit": "-"},
    ])
    create_epd_impact(epd, Decimal("2"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("5"), Unit.CM)
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(Decimal("10"))


@pytest.mark.django_db
def test_area_kg_blocks_when_no_conversion(create_epd, create_epd_impact, create_assembly, create_product):
    """Area → kg: BLOCK when no area density, volume density, or conversion factor."""
    epd = create_epd("Mystery", Unit.KG, [])
    create_epd_impact(epd, Decimal("1"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("5"), Unit.CM)
    with pytest.raises(ImpactCalculationError):
        _calc(AssemblyDimension.AREA, p)


# ---------------------------------------------------------------------------
# PDF Level 1 — Volume assembly conversions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_volume_kg_via_volume_density(create_epd, create_epd_impact, create_assembly, create_product):
    """Volume → kg: Factor = assembly_qty × share × volume_density.
    share=50%→0.5.  volume_density=2.  Factor=1×0.5×2=1.  impact=3.
    """
    epd = create_epd("Concrete vol", Unit.KG, [
        {"name": "volume density", "value": "2", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.VOLUME)
    p = create_product(assembly, epd, Decimal("50"), Unit.PERCENT)
    assert _gwp(_calc(AssemblyDimension.VOLUME, p)) == pytest.approx(Decimal("3"))


@pytest.mark.django_db
def test_volume_kg_via_conv_factor_fallback(create_epd, create_epd_impact, create_assembly, create_product):
    """Volume → kg: fallback to conversion factor to 1 kg when no volume density."""
    epd = create_epd("Vol mat", Unit.KG, [
        {"name": "conversion factor to 1 kg", "value": "4", "unit": "-"},
    ])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.VOLUME)
    p = create_product(assembly, epd, Decimal("50"), Unit.PERCENT)
    # Factor = 1 × 0.5 × 4 = 2  →  impact = 6
    assert _gwp(_calc(AssemblyDimension.VOLUME, p)) == pytest.approx(Decimal("6"))


@pytest.mark.django_db
def test_volume_kg_blocks_no_conversion(create_epd, create_epd_impact, create_assembly, create_product):
    """Volume → kg: BLOCK when no volume density or conversion factor."""
    epd = create_epd("Vol mystery", Unit.KG, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.VOLUME)
    p = create_product(assembly, epd, Decimal("50"), Unit.PERCENT)
    with pytest.raises(ImpactCalculationError):
        _calc(AssemblyDimension.VOLUME, p)


# ---------------------------------------------------------------------------
# PDF Level 1 — Mass assembly conversions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mass_m3_via_volume_density(create_epd, create_epd_impact, create_assembly, create_product):
    """Mass → m³: Factor = constituent_mass / volume_density.
    share=100%→1.0 (single constituent).  volume_density=2.
    Factor = 1 × 1.0 / 2 = 0.5.  impact = 3 × 0.5 = 1.5.
    """
    epd = create_epd("Dense mat", Unit.M3, [
        {"name": "volume density", "value": "2", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.MASS)
    # 100% share — single constituent, validates correctly
    p = create_product(assembly, epd, Decimal("100"), Unit.PERCENT)
    assert _gwp(_calc(AssemblyDimension.MASS, p)) == pytest.approx(Decimal("1.5"))


@pytest.mark.django_db
def test_mass_m3_blocks_no_volume_density(create_epd, create_epd_impact, create_assembly, create_product):
    """Mass → m³: BLOCK — no fallback allowed per PDF spec."""
    epd = create_epd("No density", Unit.M3, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.MASS)
    p = create_product(assembly, epd, Decimal("4"), Unit.PERCENT)
    with pytest.raises(ImpactCalculationError):
        _calc(AssemblyDimension.MASS, p)


@pytest.mark.django_db
def test_mass_m2_via_area_density(create_epd, create_epd_impact, create_assembly, create_product):
    """Mass → m²: Factor = constituent_mass / area_density.
    share=100%→1.0 kg (single constituent).  area_density=10.
    Factor = 1 × 1.0 / 10 = 0.1.  impact = 2 × 0.1 = 0.2.
    """
    epd = create_epd("Sheet", Unit.M2, [
        {"name": "area density", "value": "10", "unit": "kg/m^2"},
    ])
    create_epd_impact(epd, Decimal("2"))
    assembly = create_assembly(AssemblyDimension.MASS)
    # 100% share — single constituent, validates correctly
    p = create_product(assembly, epd, Decimal("100"), Unit.PERCENT)
    assert _gwp(_calc(AssemblyDimension.MASS, p)) == pytest.approx(Decimal("0.2"))


@pytest.mark.django_db
def test_mass_m2_blocks_no_area_density(create_epd, create_epd_impact, create_assembly, create_product):
    """Mass → m²: BLOCK — no fallback allowed per PDF spec."""
    epd = create_epd("No area density", Unit.M2, [])
    create_epd_impact(epd, Decimal("2"))
    assembly = create_assembly(AssemblyDimension.MASS)
    p = create_product(assembly, epd, Decimal("50"), Unit.PERCENT)
    with pytest.raises(ImpactCalculationError):
        _calc(AssemblyDimension.MASS, p)


# ---------------------------------------------------------------------------
# PDF Level 1 — Length assembly conversions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_length_m3_via_cross_section(create_epd, create_epd_impact, create_assembly, create_product):
    """Length → m³: Factor = assembly_qty × cross_section_m².
    cross_section=100 cm² → 0.01 m².  Factor=1×0.01=0.01.  impact=3×0.01=0.03.
    """
    epd = create_epd("Beam", Unit.M3, [])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.LENGTH)
    p = create_product(assembly, epd, Decimal("100"), Unit.CM2)
    assert _gwp(_calc(AssemblyDimension.LENGTH, p)) == pytest.approx(Decimal("0.03"))


@pytest.mark.django_db
def test_length_kg_via_linear_density_preferred(create_epd, create_epd_impact, create_assembly, create_product):
    """Length → kg: Option A (preferred) — linear density.
    Factor = assembly_qty × linear_density = 1 × 7.85 = 7.85.  impact = 2 × 7.85 = 15.7.
    """
    epd = create_epd("Steel bar", Unit.KG, [
        {"name": "linear density", "value": "7.85", "unit": "kg/m"},
        {"name": "volume density", "value": "7850", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("2"))
    assembly = create_assembly(AssemblyDimension.LENGTH)
    p = create_product(assembly, epd, Decimal("100"), Unit.CM2)
    assert _gwp(_calc(AssemblyDimension.LENGTH, p)) == pytest.approx(Decimal("15.7"))


@pytest.mark.django_db
def test_length_kg_via_cross_section_volume_density_fallback(create_epd, create_epd_impact, create_assembly, create_product):
    """Length → kg: Option B (fallback) — cross_section × volume_density (no linear density).
    cross_section=100 cm² → 0.01 m².  volume_density=2.  Factor=1×0.01×2=0.02.  impact=3×0.02=0.06.
    """
    epd = create_epd("Beam KG", Unit.KG, [
        {"name": "volume density", "value": "2", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.LENGTH)
    p = create_product(assembly, epd, Decimal("100"), Unit.CM2)
    assert _gwp(_calc(AssemblyDimension.LENGTH, p)) == pytest.approx(Decimal("0.06"))


@pytest.mark.django_db
def test_length_kg_blocks_no_conversion(create_epd, create_epd_impact, create_assembly, create_product):
    """Length → kg: BLOCK when no linear density and no volume density.
    CM2 unit is valid for LENGTH+KG (cross-section). But without volume density,
    the cross_section path also fails → ImpactCalculationError.
    """
    epd = create_epd("Mystery length", Unit.KG, [
        # Has kg/m^3 so model validation (epd_filtering) passes,
        # but we strip it to simulate the no-conversion case by patching conversions
        {"name": "volume density", "value": "5", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(AssemblyDimension.LENGTH)
    p = create_product(assembly, epd, Decimal("100"), Unit.CM2)
    # Now clear conversions at runtime to simulate missing data
    p.epd.conversions = []
    with pytest.raises(ImpactCalculationError):
        _calc(AssemblyDimension.LENGTH, p)


# ---------------------------------------------------------------------------
# PDF Level 1 — _resolve_thickness_m: derive from EPD conversions when no user thickness
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_resolve_thickness_from_epd_conversions(create_epd, create_epd_impact, create_assembly, create_product):
    """_resolve_thickness_m: derive thickness = area_density / volume_density when input_unit != cm.
    area_density=24, volume_density=1200 → thickness = 24/1200 = 0.02 m.
    Area→m³ with CM input_unit=0 (we set quantity=0 to force EPD-derived path):
    Actually: use a product saved with CM unit but then override input_unit at runtime
    so _resolve_thickness_m skips the user-entered path and derives from EPD.

    Simpler: just verify that when BOTH area+volume density exist, thickness is derived.
    Use quantity=0 with CM so the cm path returns 0.0 which would be wrong — instead
    patch input_unit to UNKNOWN at runtime after creation (model already saved).
    area_density=24 / volume_density=1200 = 0.02 m.  Factor=1×0.02=0.02.  impact=5×0.02=0.1.
    """
    epd = create_epd("Derived thickness", Unit.M3, [
        {"name": "area density", "value": "24", "unit": "kg/m^2"},
        {"name": "volume density", "value": "1200", "unit": "kg/m^3"},
    ])
    create_epd_impact(epd, Decimal("5"))
    assembly = create_assembly(AssemblyDimension.AREA)
    # Save with CM (valid for AREA+M3), then override input_unit to UNKNOWN at runtime
    # so _resolve_thickness_m falls through to the EPD-derived path
    p = create_product(assembly, epd, Decimal("5"), Unit.CM)
    p.input_unit = Unit.UNKNOWN  # override without re-saving — bypasses clean()
    # Now thickness_m must be derived: 24 / 1200 = 0.02 m
    # Factor = 1 × 0.02 = 0.02,  impact = 5 × 0.02 = 0.1
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(Decimal("0.1"))


# ---------------------------------------------------------------------------
# PDF Level 2 — Composite validation: share_of_mass must sum to 100%
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mass_share_sum_validation(create_epd, create_epd_impact, create_assembly, create_product):
    """Mass assembly: shares not summing to 100% must raise ImpactCalculationError."""
    epd1 = create_epd("Mat A", Unit.KG, [])
    epd2 = create_epd("Mat B", Unit.KG, [])
    create_epd_impact(epd1, Decimal("1"))
    create_epd_impact(epd2, Decimal("1"))
    assembly = create_assembly(AssemblyDimension.MASS)
    p1 = create_product(assembly, epd1, Decimal("60"), Unit.PERCENT)
    p2 = create_product(assembly, epd2, Decimal("30"), Unit.PERCENT)  # total=90%, not 100%

    with pytest.raises(ImpactCalculationError, match="100%"):
        _calc(AssemblyDimension.MASS, p1)


@pytest.mark.django_db
def test_mass_share_sum_100_passes(create_epd, create_epd_impact, create_assembly, create_product):
    """Mass assembly: shares summing to exactly 100% must not raise."""
    epd1 = create_epd("Mat X", Unit.KG, [])
    epd2 = create_epd("Mat Y", Unit.KG, [])
    create_epd_impact(epd1, Decimal("0.5"))
    create_epd_impact(epd2, Decimal("0.5"))
    assembly = create_assembly(AssemblyDimension.MASS)
    p1 = create_product(assembly, epd1, Decimal("70"), Unit.PERCENT)
    p2 = create_product(assembly, epd2, Decimal("30"), Unit.PERCENT)
    # Should not raise; just check it returns a result
    result = _calc(AssemblyDimension.MASS, p1)
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# PDF — Legacy data: fallback to 'unit' string match (no 'name' key)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_legacy_unit_string_fallback_volume_density(create_epd, create_epd_impact, create_assembly, create_product):
    """Legacy EPD data without 'name' key: volume density matched by unit string 'kg/m^3'."""
    epd = create_epd("Legacy cement", Unit.KG, [
        {"unit": "kg/m^3", "value": "2200"},  # no 'name' key
    ])
    create_epd_impact(epd, Decimal("0.183550838458225"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("3.5"), Unit.CM)
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(
        Decimal("14.1334145612833"), rel=Decimal("1e-10")
    )


@pytest.mark.django_db
def test_legacy_unit_string_area_density_preferred(create_epd, create_epd_impact, create_assembly, create_product):
    """Legacy EPD: area density (kg/m^2) preferred over volume density (kg/m^3) for Area→kg."""
    epd = create_epd("Legacy paint", Unit.KG, [
        {"unit": "kg/m^2", "value": "12"},   # area density — preferred
        {"unit": "kg/m^3", "value": "1200"},  # volume density — fallback
    ])
    create_epd_impact(epd, Decimal("0.1"))
    assembly = create_assembly(AssemblyDimension.AREA)
    p = create_product(assembly, epd, Decimal("5"), Unit.CM)
    # Must use area density: Factor = 1 × 12 = 12  →  impact = 1.2
    assert _gwp(_calc(AssemblyDimension.AREA, p)) == pytest.approx(Decimal("1.2"))


# ---------------------------------------------------------------------------
# Model validation: StructuralProduct.clean() rejects invalid unit combos
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize(
    "declared_unit, conversions, quantity, product_unit, dimension",
    [
        # Mass assembly + m3 EPD without volume density → invalid unit at model level
        (Unit.M3, [], Decimal("4"), Unit.CM, AssemblyDimension.MASS),
        # Length assembly + kg EPD without any conversion → UNKNOWN unit invalid
        (Unit.KG, [], Decimal("4"), Unit.UNKNOWN, AssemblyDimension.LENGTH),
        # Area assembly + kg EPD without any conversion → UNKNOWN unit invalid
        (Unit.KG, [], Decimal("4"), Unit.UNKNOWN, AssemblyDimension.AREA),
    ],
)
def test_model_validation_rejects_invalid_units(
    declared_unit, conversions, quantity, product_unit, dimension,
    create_epd, create_epd_impact, create_assembly, create_product,
):
    """StructuralProduct.clean() raises ValidationError for invalid unit combinations."""
    epd = create_epd("Test", declared_unit, conversions)
    create_epd_impact(epd, Decimal("3"))
    assembly = create_assembly(dimension=dimension)
    with pytest.raises(ValidationError):
        create_product(assembly, epd, quantity, product_unit)
