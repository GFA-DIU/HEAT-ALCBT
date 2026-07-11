from decimal import Decimal
from typing import Literal, TYPE_CHECKING

from pages.models.assembly import AssemblyDimension, StructuralProduct
from pages.models.epd import Unit

if TYPE_CHECKING:
    from pages.models.building import OperationalProduct


class ImpactCalculationError(ValueError):
    """Raised when a factor cannot be resolved due to missing EPD conversion data."""
    pass


def calculate_impacts(
    dimension: AssemblyDimension,
    assembly_quantity: int,
    total_floor_area: int,
    p: StructuralProduct,
):
    """Calculate embodied carbon emissions using the Factor resolution logic from the PDF spec.

    Formula:
        Emissions [kgCO₂e] = Factor × (EPDImpact.value / EPD.declared_amount)
        Emissions per m²   = Total Emissions / floor_area

    Factor resolution:
        Step 1 — pcs check
        Step 2 — direct unit match
        Step 3 — conversion paths per assembly dimension

    Field mapping (StructuralProduct.quantity + input_unit → PDF concept):
        input_unit=cm       → thickness          (÷100 → metres)
        input_unit=percent  → share_of_mass / share_of_volume
        input_unit=cm2      → cross_section       (÷10000 → m²)
        input_unit=pcs      → product_quantity    (pieces per assembly unit)
        input_unit=unknown  → layer count (area/m² direct match)
        input_unit=m/m2/m3/kg → BoQ direct quantity
    """

    # ------------------------------------------------------------------
    # Helpers — EPD conversion lookup
    # ------------------------------------------------------------------

    def _epd_conversion(name: str) -> Decimal | None:
        """Return a conversion value from EPD.conversions by name.

        Lookup order:
          1. Match by 'name' key (PDF spec: "volume density", "area density", etc.)
          2. Fallback: match by 'unit' string for legacy data without 'name' key.
        """
        try:
            conversions = p.epd.conversions or []
            for c in conversions:
                if c.get("name") == name:
                    return Decimal(str(c["value"]))
            # Legacy fallback: unit-string map
            unit_map = {
                "volume density": "kg/m^3",
                "area density": "kg/m^2",
                "linear density": "kg/m",
                "conversion factor to 1 kg": "-",
            }
            unit_str = unit_map.get(name)
            if unit_str:
                for c in conversions:
                    if c.get("unit") == unit_str:
                        return Decimal(str(c["value"]))
            return None
        except Exception:
            return None

    def _resolve_thickness_m() -> Decimal:
        """Resolve layer thickness in metres.

        Priority 1: user-entered thickness (input_unit == cm, stored in cm).
        Priority 2: derive from EPD — area_density / volume_density.
        """
        if p.input_unit == Unit.CM and p.quantity is not None:
            return Decimal(str(p.quantity)) / Decimal("100")

        area_density = _epd_conversion("area density")
        volume_density = _epd_conversion("volume density")
        if area_density is not None and volume_density is not None and volume_density != 0:
            return area_density / volume_density

        raise ImpactCalculationError(
            f"Layer thickness required but not available for '{p.epd.name}'. "
            "Not set on product and cannot be derived from EPD conversions "
            "(both area density and volume density must exist to derive it)."
        )

    def _cross_section_m2() -> Decimal:
        """Return cross-section in m² (stored in cm² on product, ÷ 10,000)."""
        if p.input_unit == Unit.CM2 and p.quantity is not None:
            return Decimal(str(p.quantity)) / Decimal("10000")
        raise ImpactCalculationError(
            f"Cross section (cm²) required but not set on product for '{p.epd.name}'."
        )

    # ------------------------------------------------------------------
    # BoQ: infer dimension from input_unit
    # ------------------------------------------------------------------

    def _fetch_dimension_for_boq() -> AssemblyDimension | None:
        boq_dim_map = {
            Unit.PCS: AssemblyDimension.PCS,
            Unit.M:   AssemblyDimension.LENGTH,
            Unit.M2:  AssemblyDimension.AREA,
            Unit.M3:  AssemblyDimension.VOLUME,
            Unit.KG:  AssemblyDimension.MASS,
            Unit.TON: AssemblyDimension.MASS,  # ton is a mass unit (1 ton = 1000 kg)
        }
        return boq_dim_map[p.input_unit]

    # ------------------------------------------------------------------
    # Resolve effective dimension
    # ------------------------------------------------------------------

    eff_dim = _fetch_dimension_for_boq() if p.assembly.is_boq else dimension

    # ------------------------------------------------------------------
    # Composite validation: mass assembly shares must sum to 100%
    # ------------------------------------------------------------------

    if eff_dim == AssemblyDimension.MASS:
        products = getattr(p.assembly, "prefetched_products", None)
        if products is None:
            products = list(p.assembly.structuralproduct_set.all())
        percent_products = [sp for sp in products if sp.input_unit == Unit.PERCENT]
        if percent_products:
            total_share = sum(Decimal(str(sp.quantity)) for sp in percent_products)
            if round(total_share, 4) != Decimal("100"):
                raise ImpactCalculationError(
                    f"Share of mass must sum to 100% for assembly '{p.assembly.name}'. "
                    f"Current total: {total_share}%."
                )

    # ------------------------------------------------------------------
    # Factor resolution
    # ------------------------------------------------------------------

    declared_unit = p.epd.declared_unit
    assembly_qty = Decimal(str(assembly_quantity))

    # Ton is a mass unit (1 ton = 1000 kg). Resolve the factor as if the EPD were
    # declared per kg (reusing all the mass/density logic), then convert kg → ton
    # (÷1000) at the end. Exception: when the quantity itself was entered in tons
    # (BoQ ton EPDs, input_unit == ton) it is already in the declared unit, so no
    # conversion is applied.
    ton_declared = declared_unit == Unit.TON
    resolve_unit = Unit.KG if ton_declared else declared_unit

    # Step 1 — pcs EPD: assembly_quantity always ignored
    if declared_unit == Unit.PCS:
        if p.quantity is None:
            raise ImpactCalculationError(
                f"Pieces per assembly unit not entered for '{p.epd.name}'. "
                "Required for pcs EPDs."
            )
        factor = Decimal(str(p.quantity))

    else:
        # Step 2 — direct unit match
        direct_match = {
            AssemblyDimension.AREA:   Unit.M2,
            AssemblyDimension.VOLUME: Unit.M3,
            AssemblyDimension.MASS:   Unit.KG,
            AssemblyDimension.LENGTH: Unit.M,
        }
        if direct_match.get(eff_dim) == resolve_unit:
            qty = (
                Decimal(str(p.quantity)) / Decimal("100")
                if p.input_unit == Unit.PERCENT
                else Decimal(str(p.quantity))
            )
            factor = assembly_qty * qty

        else:
            # Step 3 — conversion required
            factor = _resolve_conversion_factor(
                eff_dim, resolve_unit, assembly_qty,
                _epd_conversion, _resolve_thickness_m, _cross_section_m2, p,
            )

    # kg → ton for ton-declared EPDs (unless the quantity was already in tons).
    if ton_declared and p.input_unit != Unit.TON:
        factor = factor / Decimal("1000")

    # ------------------------------------------------------------------
    # Build impact list
    # ------------------------------------------------------------------

    impacts_list = getattr(p.epd, "all_impacts", None)
    if not impacts_list:
        impacts_list = p.epd.epdimpact_set.all()

    result = []
    for epdimpact in impacts_list:
        result.append(
            {
                "assembly_id": p.assembly.pk,
                "epd_id": p.epd.pk,
                "assembly_category": (
                    p.classification.category if p.classification else ""
                ),
                "material_category": p.epd.category,
                "impact_type": epdimpact.impact,
                "impact_value": (
                    Decimal(str(factor))
                    * Decimal(str(epdimpact.value))
                    / Decimal(str(p.epd.declared_amount))
                    / Decimal(str(total_floor_area))
                ),
            }
        )
    return result


def _resolve_conversion_factor(
    eff_dim, declared_unit, assembly_qty,
    _epd_conversion, _resolve_thickness_m, _cross_section_m2, p,
) -> Decimal:
    """Step 3: resolve Factor when no direct unit match exists.

    Implements the full conversion paths from the PDF Developer Edition spec.
    """

    qty_raw = Decimal(str(p.quantity))
    qty = qty_raw / Decimal("100") if p.input_unit == Unit.PERCENT else qty_raw

    # ---- AREA assembly (m²) ------------------------------------------
    if eff_dim == AssemblyDimension.AREA:

        if declared_unit == Unit.M3:
            return assembly_qty * _resolve_thickness_m()

        if declared_unit == Unit.KG:
            area_density = _epd_conversion("area density")
            if area_density is not None:
                return assembly_qty * area_density

            volume_density = _epd_conversion("volume density")
            if volume_density is not None:
                return assembly_qty * _resolve_thickness_m() * volume_density

            conv_factor = _epd_conversion("conversion factor to 1 kg")
            if conv_factor is not None:
                return assembly_qty * conv_factor

            raise ImpactCalculationError(
                f"Cannot convert area assembly to kg for '{p.epd.name}' — "
                "no area density, volume density, or conversion factor found in EPD conversions."
            )

        if declared_unit == Unit.PCS:
            # pieces_factor = pieces per m² — user-entered, stored as p.quantity with input_unit=pcs
            if p.quantity is None:
                raise ImpactCalculationError(
                    f"Pieces per m² required for '{p.epd.name}' but not entered."
                )
            return assembly_qty * Decimal(str(p.quantity))

    # ---- VOLUME assembly (m³) ----------------------------------------
    if eff_dim == AssemblyDimension.VOLUME:

        if declared_unit == Unit.KG:
            volume_density = _epd_conversion("volume density")
            if volume_density is not None:
                return assembly_qty * qty * volume_density

            conv_factor = _epd_conversion("conversion factor to 1 kg")
            if conv_factor is not None:
                return assembly_qty * qty * conv_factor

            raise ImpactCalculationError(
                f"Cannot convert volume assembly to kg for '{p.epd.name}' — "
                "volume density and conversion factor both missing from EPD conversions."
            )

        if declared_unit == Unit.M2:
            return assembly_qty * qty / _resolve_thickness_m()

        if declared_unit == Unit.PCS:
            # pieces_factor = pieces per m³ — user-entered
            if p.quantity is None:
                raise ImpactCalculationError(
                    f"Pieces per m³ required for '{p.epd.name}' but not entered."
                )
            return assembly_qty * Decimal(str(p.quantity))

    # ---- MASS assembly (kg) ------------------------------------------
    if eff_dim == AssemblyDimension.MASS:
        constituent_mass = assembly_qty * qty

        if declared_unit == Unit.M3:
            volume_density = _epd_conversion("volume density")
            if volume_density is not None and volume_density != 0:
                return constituent_mass / volume_density
            raise ImpactCalculationError(
                f"Cannot convert mass assembly to m³ for '{p.epd.name}' — "
                "volume density missing from EPD conversions. No safe fallback."
            )

        if declared_unit == Unit.M2:
            area_density = _epd_conversion("area density")
            if area_density is not None and area_density != 0:
                return constituent_mass / area_density
            raise ImpactCalculationError(
                f"Cannot convert mass assembly to m² for '{p.epd.name}' — "
                "area density missing from EPD conversions. No safe fallback."
            )

        if declared_unit == Unit.PCS:
            # pieces_factor = pieces per kg — user-entered
            if p.quantity is None:
                raise ImpactCalculationError(
                    f"Pieces per kg required for '{p.epd.name}' but not entered."
                )
            return constituent_mass * Decimal(str(p.quantity))

    # ---- LENGTH assembly (m) -----------------------------------------
    if eff_dim == AssemblyDimension.LENGTH:

        if declared_unit == Unit.M3:
            return assembly_qty * _cross_section_m2()

        if declared_unit == Unit.KG:
            linear_density = _epd_conversion("linear density")
            if linear_density is not None:
                return assembly_qty * linear_density

            volume_density = _epd_conversion("volume density")
            if volume_density is not None:
                return assembly_qty * _cross_section_m2() * volume_density

            raise ImpactCalculationError(
                f"Cannot convert length assembly to kg for '{p.epd.name}' — "
                "linear density missing and cross section or volume density not available."
            )

        if declared_unit == Unit.PCS:
            # pieces_factor = pieces per m — user-entered
            if p.quantity is None:
                raise ImpactCalculationError(
                    f"Pieces per m required for '{p.epd.name}' but not entered."
                )
            return assembly_qty * Decimal(str(p.quantity))

    # ---- PCS assembly (pcs) — pcs→other conversions from DB ----------
    if eff_dim == AssemblyDimension.PCS:

        if declared_unit == Unit.KG:
            # pieces per kg from DB: mass = pieces ÷ (pcs/kg)
            pieces_per_kg = _epd_conversion("conversion factor to 1 kg")
            if pieces_per_kg is not None and pieces_per_kg != 0:
                return assembly_qty / pieces_per_kg
            raise ImpactCalculationError(
                f"Cannot convert pcs assembly to kg for '{p.epd.name}' — "
                "conversion factor to 1 kg missing from EPD conversions."
            )

        if declared_unit == Unit.M2:
            # pieces per m² from DB: area = pieces ÷ (pcs/m²)
            pieces_per_m2 = _epd_conversion("area density")
            if pieces_per_m2 is not None and pieces_per_m2 != 0:
                return assembly_qty / pieces_per_m2
            raise ImpactCalculationError(
                f"Cannot convert pcs assembly to m² for '{p.epd.name}' — "
                "area density (pcs/m²) missing from EPD conversions."
            )

        if declared_unit == Unit.M3:
            # pieces per m³ from DB: volume = pieces ÷ (pcs/m³)
            pieces_per_m3 = _epd_conversion("volume density")
            if pieces_per_m3 is not None and pieces_per_m3 != 0:
                return assembly_qty / pieces_per_m3
            raise ImpactCalculationError(
                f"Cannot convert pcs assembly to m³ for '{p.epd.name}' — "
                "volume density (pcs/m³) missing from EPD conversions."
            )

    raise ImpactCalculationError(
        f"Unsupported combination: dimension='{eff_dim}', "
        f"declared_unit='{declared_unit}' for EPD '{p.epd.name}'."
    )


def calculate_impact_operational(
    p: "OperationalProduct",
) -> dict[Literal["gwp_b6", "penrt_b6"], Decimal]:
    """Calculate operational carbon (GWP B6 and PENRT B6)."""

    def fetch_conversion(unit) -> Decimal | None:
        try:
            return next(
                (Decimal(str(c["value"])) for c in p.epd.conversions if c["unit"] == unit),
                None,
            )
        except Exception:
            return None

    def calculate_impact(factor, gwp_impact, penrt_impact):
        return {
            "gwp_b6": (
                Decimal(str(factor))
                * Decimal(str(gwp_impact))
                / Decimal(str(p.epd.declared_amount))
                / Decimal(str(p.building.total_floor_area))
            ),
            "penrt_b6": (
                Decimal(str(factor))
                * Decimal(str(penrt_impact))
                / Decimal(str(p.epd.declared_amount))
                / Decimal(str(p.building.total_floor_area))
            ),
        }

    impact_set = p.epd.epdimpact_set.filter(impact__life_cycle_stage="b6")
    gwp_b6 = next(
        (i.value for i in impact_set if i.impact.impact_category == "gwp"), None
    )
    penrt_b6 = next(
        (i.value for i in impact_set if i.impact.impact_category == "penrt"), None
    )

    match (p.epd.declared_unit, p.input_unit):

        case (Unit.KWH, Unit.KWH):
            impacts = calculate_impact(Decimal(str(p.quantity)), gwp_b6, penrt_b6)

        case (Unit.KWH, Unit.M3):
            kwh_per_kg = fetch_conversion("kg") or fetch_conversion("-")
            kg_per_m3 = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(str(p.quantity)) * Decimal(str(kwh_per_kg)) * Decimal(str(kg_per_m3)),
                gwp_b6,
                penrt_b6,
            )

        case (Unit.KWH, Unit.LITER):
            kwh_per_kg = fetch_conversion("kg") or fetch_conversion("-")
            kg_per_m3 = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(str(p.quantity)) * Decimal(str(kwh_per_kg)) * Decimal(str(kg_per_m3)) / Decimal("1000"),
                gwp_b6,
                penrt_b6,
            )

        case (Unit.KWH, Unit.KG):
            kwh_per_kg = fetch_conversion("kg") or fetch_conversion("-")
            impacts = calculate_impact(
                Decimal(str(p.quantity)) * Decimal(str(kwh_per_kg)),
                gwp_b6,
                penrt_b6,
            )

        case _:
            raise ValueError(
                f"Unsupported combination: declared_unit '{p.epd.declared_unit}', "
                f"input_unit '{p.input_unit}'"
            )

    return impacts
