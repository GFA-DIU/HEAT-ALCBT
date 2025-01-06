from dataclasses import dataclass
from typing import Optional

from pages.models.assembly import AssemblyDimension, Product
from pages.models.epd import EPD
from pages.views.assembly.epd_filtering import get_epd_dimension_info, get_filtered_epd_list


@dataclass
class SelectedEPD:
    id: str
    sel_unit: Optional[str]
    sel_text: Optional[str]
    sel_quantity: float
    name: str
    category: Optional[str]
    country: Optional[str]
    source: Optional[str]

    @classmethod
    def parse_product(cls, product:Product):
        """
        Parses a Product instance into a SelectedEPD dataclass.
        """
        sel_text, _ = get_epd_dimension_info(product.assembly.dimension, product.epd.declared_unit)
        
        return cls(
            id=str(product.epd.id),
            sel_unit=product.input_unit,
            sel_text= sel_text,
            sel_quantity=float(product.quantity),
            name=product.epd.name,
            category=product.epd.category.name_en if product.epd.category else None,
            country=product.epd.country.name if product.epd.country else None,
            source=product.epd.source,
        )

    @classmethod
    def parse_epd(cls, epd):
        """
        Parses an EPD instance into a SelectedEPD dataclass.
        """
        return cls(
            id=str(epd.id),
            sel_unit="",
            sel_quantity="",
            name=epd.name,
            category=epd.category.name_en if epd.category else None,
            country=epd.country.name if epd.country else None,
            source=epd.source,
        )


@dataclass
class FilteredEPD:
    id: str
    name: str
    country: str
    conversions: str
    declared_unit: str
    selection_text: str
    selection_unit: str


def get_epd_list(request, component):
    # TODO: can dimension every be None? For new component perhaps?
    filtered_list, dimension = get_filtered_epd_list(request, component.dimension if component else None)
    dimension = dimension if dimension else AssemblyDimension.AREA
    return parse_epds(filtered_list, dimension)


def parse_epds(epd_list: list[EPD], dimension: AssemblyDimension) -> list[FilteredEPD]:
    container = []
    for epd in epd_list:
        sel_text, sel_unit = get_epd_dimension_info(dimension, epd.declared_unit)
        container.append(
            FilteredEPD(
                    selection_text=sel_text,
                    selection_unit=sel_unit,
                    id=epd.pk,
                    name=epd.name,
                    country=epd.country,
                    conversions=[],
                    declared_unit=epd.declared_unit
                )
        )
    
    return container