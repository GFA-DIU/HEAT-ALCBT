from decimal import Decimal

from pages.models.assembly import AssemblyDimension, Product
from pages.models.epd import Unit


# TODO: Add Try/Catch when trying to fetch a non-existing conversion and handle and display error
def calculate_impacts(
    dimension: AssemblyDimension,
    assembly_quantity: int,
    reporting_life_cycle: int,
    p: Product,
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
            return next((c["value"] for c in p.epd.conversions if c["unit"] == unit), None)
        except:
            return None

    def calculate_impact(factor=1):
        """Calculate impacts using a given factor and normalized by EPD base amount and reporting life_cycle."""
        container = []
        for epdimpact in p.epd.epdimpact_set.all():
            container.append(
                {
                    "assembly_id": p.assembly.pk,
                    "epd_id": p.epd.pk,
                    "assembly_category": (
                        p.assembly.classification.category
                        if p.assembly.classification
                        else ""
                    ),
                    "material_category": p.epd.category,
                    "impact_type": epdimpact.impact,
                    "impact_value": Decimal(factor)
                    * Decimal(epdimpact.value)
                    / Decimal(p.epd.declared_amount)  # Normalise by base amount
                    / Decimal(
                        reporting_life_cycle
                    ),  # Normalise by reporting_life_cycle
                }
            )
        return container

    declared_unit = p.epd.declared_unit
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
            # impact = impact_per_unit * total_m2 * thickness_to_meter / epd_base_amount
            impacts = calculate_impact(
                Decimal(assembly_quantity) * Decimal(quantity) / Decimal(cm_to_m)
            )
        case (AssemblyDimension.AREA, Unit.KG):
            # impact = impact_per_unit * conversion_kg_per_m2 * total_m2 * thickness_to_meter / epd_base_amount
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
            # impact = impact_per_unit * total_length * surface_cross-section_to_m2 / epd_base_amount
            impacts = calculate_impact(
                Decimal(assembly_quantity) * Decimal(quantity) / Decimal(cm_to_m**2)
            )
        case (AssemblyDimension.LENGTH, Unit.KG):
            # impact = impact_per_unit * conversion_kg_per_m * total_length * surface_cross-section_to_m2 / epd_base_amount
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
