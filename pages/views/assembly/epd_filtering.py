from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.manager import BaseManager
from django.shortcuts import get_object_or_404

from django.apps import apps
from pages.models.assembly import AssemblyDimension
from pages.models.epd import EPD, MaterialCategory, Unit


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
            selection_unit = Unit.KG
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


def filter_by_dimension(epds:BaseManager[EPD], dimension: AssemblyDimension):
    """Logic for filering EPDs from DB by Assembly Dimension.
    
    This is the logic:
    | **    Declared unit   ** | **    Area Assembly   ** | **    Volume Assembly   ** | **    Mass Assembly   ** | **    Length Assembly   ** |
    |--------------------------|--------------------------|----------------------------|--------------------------|----------------------------|
    |     m3                   |     Yes                  |     Yes                    |     Yes                  |     Yes                    |
    |     m2                   |     Yes                  |     No                     |     No                   |     No                     |
    |     m                    |     No                   |     No                     |     No                   |     Yes                    |
    |     kg                   |     w. Volume density    |     w. Volume density      |     Yes                  |     w. Volume density      |
    |     pieces               |     Set a quantity       |     Set a quantity         |     Set a quantity       |     Set a quantity         |
    
    """ 
    # Requires postgres backend
    # TODO: uncomment once we have Postgres backend
    additional_filters = None
    match dimension:
        case AssemblyDimension.AREA:
            declared_units = [Unit.M3, Unit.M2, Unit.KG, Unit.PCS]
            # additional_filters = (Q(declared_unit=Unit.KG) & Q(conversions__contains=[{"unit": "kg/m^3"}]) | ~Q(declared_unit=Unit.KG))
        case AssemblyDimension.VOLUME:
            declared_units = [Unit.M3, Unit.KG, Unit.PCS]
            # additional_filters = (Q(declared_unit=Unit.KG) & Q(conversions__contains=[{"unit": "kg/m^3"}]) | ~Q(declared_unit=Unit.KG))
        case AssemblyDimension.MASS:
            declared_units = [Unit.M3, Unit.KG, Unit.PCS]
        case AssemblyDimension.LENGTH:
            declared_units = [Unit.M3, Unit.M, Unit.KG, Unit.PCS]
            # additional_filters = (Q(declared_unit=Unit.KG) & Q(conversions__contains=[{"unit": "kg/m^3"}]) | ~Q(declared_unit=Unit.KG))
        case _:
            return epds
    
    return epds.filter(declared_unit__in=declared_units)


def get_filtered_epd_list(request, dimension = None):
    # Start with the base queryset
    filtered_epds = EPD.objects.all().order_by("id")
    if request.method == "POST" and request.POST.get("action") == "filter":
        # Add filters conditionally
        if dimension := request.POST.get("dimension"):
            filtered_epds = filter_by_dimension(filtered_epds, dimension)

        if childcategory := request.POST.get("childcategory"):
            childcategory_object = get_object_or_404(
                MaterialCategory, pk=int(childcategory)
            )
            filtered_epds = filtered_epds.filter(category=childcategory_object)
        elif subcategory := request.POST.get("subcategory"):
            subcategory_object = get_object_or_404(MaterialCategory, pk=int(subcategory))
            filtered_epds = filtered_epds.filter(
                category__category_id__istartswith=subcategory_object.category_id
            )
        elif category := request.POST.get("category"):
            category_object = get_object_or_404(MaterialCategory, pk=int(category))
            filtered_epds = filtered_epds.filter(
                category__category_id__istartswith=category_object.category_id
            )

        if search_query := request.POST.get("search_query"):
            search_terms = search_query.split()
            query = Q()
            # Add a case-insensitive filter for each search term
            for term in search_terms:
                query &= Q(name__icontains=term)
                
            filtered_epds = filtered_epds.filter(query)
            
        if country := request.POST.get("country"):
            filtered_epds = filtered_epds.filter(
                country=country
            )  # Adjust the field for your model
    elif dimension:
        filtered_epds = filter_by_dimension(
            filtered_epds, dimension
        )
    # Pagination setup for EPD list
    paginator = Paginator(filtered_epds, 10)  # Show 10 items per page
    page_number= request.GET.get("page", 1)
    return paginator.get_page(page_number), dimension