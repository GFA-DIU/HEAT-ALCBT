from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from django.core.paginator import Paginator, Page

from pages.models.assembly import AssemblyDimension, StructuralProduct
from pages.models.epd import EPD
from pages.views.assembly.epd_filtering import (
    get_epd_info,
    get_filtered_epd_list,
)


@dataclass
class SelectedEPD:
    id: str
    selection_unit: Optional[str]
    selection_text: Optional[str]
    selection_quantity: float
    timestamp: str
    name: str
    description: str
    category: Optional[str]
    country: Optional[str]
    source: Optional[str]
    classification: Optional[str]

    @classmethod
    def parse_product(cls, product: StructuralProduct, is_boq_product=False):
        """
        Parses a Product instance into a SelectedEPD dataclass.
        """
        if is_boq_product:
            sel_text = "Quantity"
        else:
            sel_text, _ = get_epd_info(
                product.assembly.dimension, product.epd.declared_unit
            )

        return cls(
            id=str(product.epd.id),
            selection_unit=product.input_unit,
            selection_text=sel_text,
            selection_quantity=float(product.quantity),
            timestamp=datetime.now().strftime("%Y%m%d%H%M%S%f"),
            name=product.epd.name,
            description=product.description,
            category=product.epd.category.name_en if product.epd.category else None,
            country=product.epd.country.name if product.epd.country else "",
            source=product.epd.source,
            classification=product.classification,
        )


@dataclass
class FilteredEPD:
    id: str
    name: str
    type: str
    country: str
    category: Optional[str]
    impact_gwp: float
    impact_penrt: float
    conversions: str
    declared_unit: str
    selection_text: str
    selection_unit: str
    source: Optional[str]


class LazyProcessor:
    def __init__(self, queryset, dimension: AssemblyDimension, operational: bool):
        self.queryset = queryset
        self.dimension = dimension
        if operational:
            self.life_cycle_stage = "b6"
        else:
            self.life_cycle_stage = "a1a3"

    def __iter__(self):
        for epd in self.queryset:
            yield self.epd_parsing(epd)

    def __len__(self):
        # Use the queryset's count method to avoid full evaluation
        return self.queryset.count()

    def __getitem__(self, index):
        """
        Supports slicing for the LazyWrapper.

        Args:
            index (int or slice): The index or slice to retrieve.

        Returns:
            FilteredEPD or list[FilteredEPD]: The preprocessed item(s).
        """
        if isinstance(index, slice):
            # Slicing the queryset and applying preprocessing lazily
            return [self.epd_parsing(epd) for epd in self.queryset[index]]
        elif isinstance(index, int):
            # Single item access
            if index < 0:
                # Handle negative indexing
                index += len(self)
            if index < 0 or index >= len(self):
                raise IndexError("Index out of range")
            return self.epd_parsing(self.queryset[index])
        else:
            raise TypeError("Invalid argument type")

    def epd_parsing(self, epd: EPD):
        """Encapsulates the logic for preprocessing EPDs."""
        if self.life_cycle_stage == "a1a3":
            sel_text, sel_unit = get_epd_info(self.dimension, epd.declared_unit)
        else:
            sel_text = sel_unit = ""
        return FilteredEPD(
            id=epd.pk,
            name=epd.name,
            type=epd.type,
            country=epd.country.name if epd.country else "",
            category=epd.category.name_en if epd.category else None,
            impact_gwp=epd.get_gwp_impact_sum(life_cycle_stage=self.life_cycle_stage),
            impact_penrt=epd.get_penrt_impact_sum(life_cycle_stage=self.life_cycle_stage),
            conversions=[],
            declared_unit=epd.declared_unit,
            selection_text=sel_text,
            selection_unit=sel_unit,
            source=epd.source,
        )


def get_epd_list(request, dimension, operational: bool) -> tuple[Page, AssemblyDimension]:
    # Dimension can never be None, since we need dimension info to parse epds
    filtered_list, dimension = get_filtered_epd_list(request, dimension, operational=operational)
    # Pagination setup for EPD list
    lazy_queryset = LazyProcessor(filtered_list, dimension, operational)
    paginator = Paginator(lazy_queryset, 5)  # Show 10 items per page
    page_number = request.GET.get("page", 1)
    return paginator.get_page(page_number), dimension
