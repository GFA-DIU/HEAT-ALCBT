from decimal import Decimal
from typing import Literal, TYPE_CHECKING

from pages.models.assembly import AssemblyDimension, StructuralProduct
from pages.models.epd import Unit

if TYPE_CHECKING:
    # Use a forward reference to avoid circular import at runtime
    from pages.models.building import OperationalProduct


# TODO: Add Try/Catch when trying to fetch a non-existing conversion and handle and display error
def calculate_impacts(
    dimension: AssemblyDimension,
    assembly_quantity: int,
    total_floor_area: int,
    p: StructuralProduct,
):
    """Calculate EPDs using the dimension approach.

    # Each AssembyDimension implies a set of allowed `declared_unit`s of EPDs. This is summarized
    in the table below.
    | **    Declared unit   ** | **    Area Assembly   ** | **    Volume Assembly   ** | **    Mass Assembly   ** | **    Length Assembly   ** |
    |--------------------------|--------------------------|----------------------------|--------------------------|----------------------------|
    |     m3                   |     Yes                  |     Yes                    |     w. Volume density    |     Yes                    |
    |     m2                   |     Yes                  |     No                     |     No                   |     No                     |
    |     m                    |     No                   |     No                     |     No                   |     Yes                    |
    |     kg                   |     w. Volume density    |     w. Volume density      |     Yes                  |     w. Volume density      |
    |     pieces               |     Set a quantity       |     Set a quantity         |     Set a quantity       |     Set a quantity         |

    # Notes
     - Some EPDs do not have a base unit of 1 (e.g. 1 kg). That is why we normalize by 'declared_amount'

    """

    def fetch_conversion(unit: str) -> str | None:
        """Fetch conversion factor based on the unit."""
        try:
            return next(
                (c["value"] for c in p.epd.conversions if c["unit"] == unit), None
            )
        except:
            return None

    def fetch_dimension_for_boq(input_unit):
        """Assign dimension based on 'input_unit'."""
        boq_dim_map = {
            Unit.PCS: None,  # pieces doesn't rely on dimension
            Unit.M: AssemblyDimension.LENGTH,
            Unit.M2: AssemblyDimension.AREA,
            Unit.M3: AssemblyDimension.VOLUME,
            Unit.KG: AssemblyDimension.MASS,
        }
        return boq_dim_map[input_unit]

    def calculate_impact(factor=1):
        """Calculate impacts using a given factor and normalized by EPD base amount and reporting life_cycle."""
        impacts_list = getattr(p.epd, "all_impacts", None)
        if not impacts_list:
            impacts_list = p.epd.epdimpact_set.all()
        
        container = []
        for epdimpact in impacts_list:
            container.append(
                {
                    "assembly_id": p.assembly.pk,
                    "epd_id": p.epd.pk,
                    "assembly_category": (
                        p.classification.category if p.classification else ""
                    ),
                    "material_category": p.epd.category,
                    "impact_type": epdimpact.impact,
                    "impact_value": Decimal(factor)
                    * Decimal(epdimpact.value)
                    / Decimal(p.epd.declared_amount)  # Normalise by base amount
                    / Decimal(total_floor_area),  # Normalise by total floor area
                }
            )
        return container

    declared_unit = p.epd.declared_unit

    if p.assembly.is_boq:
        # For BoQs assembly-level dimension is irrelevant as assembly quantity is fixed to 1.
        dimension = fetch_dimension_for_boq(p.input_unit)

    quantity = p.quantity / 100 if p.input_unit == Unit.PERCENT else p.quantity

    cm_to_m = 100

    match (dimension, declared_unit):
        case (_, Unit.PCS):
            # impact = impact_per_unit * number of pieces / epd_base_amount
            impacts = calculate_impact(quantity)

        case (AssemblyDimension.AREA, Unit.M2):
            # impact = impact_per_unit * total_m2 * num_layers / epd_base_amount
            impacts = calculate_impact(Decimal(assembly_quantity) * Decimal(quantity))
        case (AssemblyDimension.AREA, Unit.M3):
            # impact = impact_per_unit * total_m2 * thickness_in_cm * unit_conversion_cm_to_m / epd_base_amount
            impacts = calculate_impact(
                Decimal(assembly_quantity) * Decimal(quantity) / Decimal(cm_to_m)
            )
        case (AssemblyDimension.AREA, Unit.KG):
            # impact = impact_per_unit * conversion_kg_per_m2 * total_m2 * thickness_in_cm * unit_conversion_cm_to_m / epd_base_amount
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(assembly_quantity)
                * Decimal(quantity)
                * Decimal(conversion_f)
                / Decimal(cm_to_m)
            )

        case (AssemblyDimension.VOLUME, Unit.M3):
            # impact = impact_per_unit * total_m3 / epd_base_amount
            impacts = calculate_impact(Decimal(assembly_quantity) * Decimal(quantity))
        case (AssemblyDimension.VOLUME, Unit.KG):
            # impact = impact_per_unit * conversion_kg_per_m3 * total_m3 * percentage / epd_base_amount
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(assembly_quantity) * Decimal(quantity) * Decimal(conversion_f)
            )

        case (AssemblyDimension.MASS, Unit.KG):
            # impact = impact_per_unit * total_kg / epd_base_amount
            impacts = calculate_impact(Decimal(assembly_quantity) * Decimal(quantity))
        case (AssemblyDimension.MASS, Unit.M3):
            # impact = impact_per_unit / conversion_kg_per_m3 * total_kg * percentage / epd_base_amount
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(assembly_quantity) * Decimal(quantity) / Decimal(conversion_f)
            )

        case (AssemblyDimension.LENGTH, Unit.M):
            # impact = impact_per_unit * total_length * num_elements / epd_base_amount
            impacts = calculate_impact(Decimal(assembly_quantity) * Decimal(quantity))
        case (AssemblyDimension.LENGTH, Unit.M3):
            # impact = impact_per_unit * total_length * surface_cross-section_to_m2 / unit_conversion_cm2_to_m2 / epd_base_amount
            impacts = calculate_impact(
                Decimal(assembly_quantity) * Decimal(quantity) / Decimal(cm_to_m**2)
            )
        case (AssemblyDimension.LENGTH, Unit.KG):
            # impact = impact_per_unit * conversion_kg_per_m * total_length * surface_cross-section_to_m2 / unit_conversion_cm2_to_m2 / epd_base_amount
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(assembly_quantity)
                * Decimal(quantity)
                * Decimal(conversion_f)
                / Decimal(cm_to_m**2)
            )

        case _:
            raise ValueError(
                f"Unsupported combination: dimension '{dimension}', declared_unit '{declared_unit}'"
            )

    return impacts


def calculate_impact_operational(
    p: "OperationalProduct",
) -> dict[Literal["gwp_b6", "penrt_b6"], Decimal]:
    def fetch_conversion(unit) -> Decimal|None:
        """Fetch conversion factor based on the unit."""
        try:
            return next(
                (c["value"] for c in p.epd.conversions if c["unit"] == unit), None
            )
        except:
            return None

    def calculate_impact(factor, gwp_impact, penrt_impact):
        return {
            "gwp_b6": Decimal(factor)
            * Decimal(gwp_impact)
            / Decimal(p.epd.declared_amount)  # Normalise by base amount
            / Decimal(p.building.total_floor_area),  # Normalise by floor area,
            "penrt_b6": Decimal(factor)
            * Decimal(penrt_impact)
            / Decimal(p.epd.declared_amount)  # Normalise by base amount
            / Decimal(p.building.total_floor_area),  # Normalise by floor area,
        }

    impact_set = p.epd.epdimpact_set.filter(impact__life_cycle_stage="b6")
    gwp_b6 = next(
        (i.value for i in impact_set if i.impact.impact_category == "gwp"), None
    )
    penrt_b6 = next(
        (i.value for i in impact_set if i.impact.impact_category == "penrt"), None
    )

    # TODO: Flexibilise to other declared_units
    match (p.epd.declared_unit, p.input_unit):

        case (Unit.KWH, Unit.KWH):
            impacts = calculate_impact(Decimal(p.quantity), gwp_b6, penrt_b6)
        case (Unit.KWH, Unit.M3):
            kwh_per_kg = fetch_conversion("kg") or fetch_conversion(
                "-"
            )  # "-" is used by Ökobdauat for name:'conversion
            kg_per_m3 = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(p.quantity) * Decimal(kwh_per_kg) * Decimal(kg_per_m3),
                gwp_b6,
                penrt_b6,
            )
        case (Unit.KWH, Unit.LITER):
            kwh_per_kg = fetch_conversion("kg") or fetch_conversion(
                "-"
            )  # "-" is used by Ökobdauat for name:'conversion
            kg_per_m3 = fetch_conversion("kg/m^3")
            impacts = calculate_impact(
                Decimal(p.quantity) * Decimal(kwh_per_kg) * Decimal(kg_per_m3) / 1000,
                gwp_b6,
                penrt_b6,
            )
        case (Unit.KWH, Unit.KG):
            kwh_per_kg = fetch_conversion("kg") or fetch_conversion("-")  # "-" is used by Ökobdauat for name:'conversion factor to 1 kg'
            impacts = calculate_impact(
                Decimal(p.quantity) * Decimal(kwh_per_kg), gwp_b6, penrt_b6
            )

        case _:
            raise ValueError(
                f"Unsupported combination: declared_unit '{p.epd.declared_unit}', input_unit '{p.input_unit}'"
            )

    return impacts
