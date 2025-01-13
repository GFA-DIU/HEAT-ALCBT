from collections.abc import Generator
from dataclasses import dataclass
from typing import Optional

from django.core.paginator import Paginator, Page

from pages.models.assembly import AssemblyDimension, Product
from pages.models.epd import EPD
from pages.views.assembly.epd_filtering import (
    get_epd_dimension_info,
    get_filtered_epd_list,
)


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
    def parse_product(cls, product: Product):
        """
        Parses a Product instance into a SelectedEPD dataclass.
        """
        sel_text, _ = get_epd_dimension_info(
            product.assembly.dimension, product.epd.declared_unit
        )

        return cls(
            id=str(product.epd.id),
            sel_unit=product.input_unit,
            sel_text=sel_text,
            sel_quantity=float(product.quantity),
            name=product.epd.name,
            category=product.epd.category.name_en if product.epd.category else None,
            country=product.epd.country.name if product.epd.country else None,
            source=product.epd.source,
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


class LazyProcessor:
    def __init__(self, queryset, dimension: AssemblyDimension):
        self.queryset = queryset
        self.dimension = dimension

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
        sel_text, sel_unit = get_epd_dimension_info(self.dimension, epd.declared_unit)
        return FilteredEPD(
            selection_text=sel_text,
            selection_unit=sel_unit,
            id=epd.pk,
            name=epd.name,
            country=epd.country,
            conversions=[],
            declared_unit=epd.declared_unit,
        )


def get_epd_list(request, component) -> tuple[Page, AssemblyDimension]:
    # Dimension can never be None, since we need dimension info to parse epds
    filtered_list, dimension = get_filtered_epd_list(
        request, component.dimension if component else AssemblyDimension.AREA
    )

    # Pagination setup for EPD list
    lazy_queryset = LazyProcessor(filtered_list, dimension)
    paginator = Paginator(lazy_queryset, 10)  # Show 10 items per page
    page_number = request.GET.get("page", 1)

    return paginator.get_page(page_number), dimension