from pages.models.assembly import AssemblyDimension
from pages.models.epd import Unit


def get_epd_dimension_info(dimension: AssemblyDimension, declared_unit: Unit):
    """Rule for input texts and units depending on Dimension."""
    match (dimension, declared_unit):
        case (_, Unit.PCS):
            # 'Pieces' EPD is treated the same across all assembly dimensions
            selection_text = "Quantity"
            selection_unit = Unit.PCS
        case (AssemblyDimension.AREA, Unit.M2):
            selection_text = "Number of layers"
            selection_unit = Unit.UNKNOWN
        case (AssemblyDimension.AREA, _):
            selection_text = "Layer Thickness"
            selection_unit = Unit.CM
        case (AssemblyDimension.VOLUME, _):
            selection_text = "Share of volume"
            selection_unit = Unit.PERCENT
        case (AssemblyDimension.MASS, _):
            selection_text = "Share of mass"
            selection_unit = Unit.PERCENT
        case (AssemblyDimension.LENGTH, Unit.M):
            selection_text = "Number of full-lengt elements"
            selection_unit = Unit.UNKNOWN
        case (AssemblyDimension.LENGTH, _):
            selection_text = "Share of cross-section"
            selection_unit = Unit.CM2
        case _:
            raise ValueError(
                f"Unsupported combination: dimension '{dimension}', declared_unit '{declared_unit}'"
            )

    return selection_text, selection_unit