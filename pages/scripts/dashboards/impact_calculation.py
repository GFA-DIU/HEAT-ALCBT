from pages.models.assembly import AssemblyDimension, Product
from pages.models.epd import Unit


def calculate_impacts(dimension: AssemblyDimension, assembly_quantity: int, p: Product):
    def fetch_conversion(unit):
        """Fetch conversion factor based on the unit."""
        return next(c["value"] for c in p.epd.conversions if c["unit"] == unit)

    def calculate_impact(factor=1):
        """Calculate impacts using a given factor."""
        return [(p.assembly.id, p.epd.category, epdimpact.impact, factor * epdimpact.value) for epdimpact in p.epd.epdimpact_set.all()]

    #TODO
    assembly_quantity = 20
    declared_unit = p.epd.declared_unit

    match (dimension, declared_unit):
        case (_, Unit.PCS):
            impacts = calculate_impact(p.quantity)
        
        case (AssemblyDimension.AREA, Unit.M2):
            impacts = calculate_impact(assembly_quantity)
        case (AssemblyDimension.AREA, Unit.M3 | Unit.KG):
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(assembly_quantity * p.quantity * conversion_f)
        
        case (AssemblyDimension.VOLUME, Unit.M3):
            impacts = calculate_impact(assembly_quantity * p.quantity)
        case (AssemblyDimension.VOLUME, Unit.KG):
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(assembly_quantity * p.quantity * conversion_f)
        
        case (AssemblyDimension.MASS, Unit.KG):
            impacts = calculate_impact(assembly_quantity * p.quantity)
        case (AssemblyDimension.MASS, Unit.M3):
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(assembly_quantity * p.quantity * conversion_f)
        
        case (AssemblyDimension.LENGTH, Unit.M):
            impacts = calculate_impact(assembly_quantity * p.quantity)
        case (AssemblyDimension.LENGTH, Unit.M3 | Unit.KG):
            conversion_f = fetch_conversion("kg/m^3")
            impacts = calculate_impact(assembly_quantity * p.quantity * conversion_f)
        
        case _:
            raise ValueError(f"Unsupported combination: dimension '{dimension}', declared_unit '{declared_unit}'")

    return impacts