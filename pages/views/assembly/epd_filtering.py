from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.manager import BaseManager
from django.shortcuts import get_object_or_404

from django.apps import apps
from pages.models.assembly import AssemblyDimension
from pages.models.epd import EPD, MaterialCategory, Unit


def get_epd_dimension_info(dimension: AssemblyDimension, declared_unit: Unit, conversions: list[dict]):
    """Rule for input texts and units depending on Dimension."""
    primary_conf = None
    if declared_unit == Unit.KG:
        confs = [c["unit"] for c in conversions]
        
        conversion_map = {
            AssemblyDimension.LENGTH: ["kg/m", "kg/m^3"],
            AssemblyDimension.AREA: ["kg/m^2", "kg/m^3"],
            AssemblyDimension.VOLUME: ["kg/m^3"],
        }
        primary_conf = next((c for c in confs if c in conversion_map[dimension]), None)

 
    match (dimension, declared_unit, primary_conf):
        case (_, Unit.PCS, _):
            # 'Pieces' EPD is treated the same across all assembly dimensions
            selection_text = "Quantity"
            selection_unit = Unit.PCS
        case (AssemblyDimension.AREA, Unit.M2, _):
            selection_text = "Number of layers"
            selection_unit = Unit.UNKNOWN
        case (AssemblyDimension.AREA, Unit.KG, "kg/m^2"):
            selection_text = "Number of layers"
            selection_unit = Unit.UNKNOWN
        case (AssemblyDimension.AREA, _, _):
            selection_text = "Layer Thickness"
            selection_unit = Unit.CM
        case (AssemblyDimension.VOLUME, _, _):
            selection_text = "Share of volume"
            selection_unit = Unit.PERCENT
        case (AssemblyDimension.MASS, _, _):
            selection_text = "Share of mass"
            selection_unit = Unit.PERCENT
        case (AssemblyDimension.LENGTH, Unit.M, _):
            selection_text = "Number of full-length elements"
            selection_unit = Unit.UNKNOWN
        case (AssemblyDimension.LENGTH, Unit.KG, "kg/m"):
            selection_text = "Number of full-length elements"
            selection_unit = Unit.UNKNOWN
        case (AssemblyDimension.LENGTH, _, _):
            selection_text = "Share of cross-section"
            selection_unit = Unit.CM2
        case _:
            raise ValueError(
                f"Unsupported combination: dimension '{dimension}', declared_unit '{declared_unit}', conf '{primary_conf}'"
            )

    return selection_text, selection_unit


def filter_by_dimension(epds: BaseManager[EPD], dimension: AssemblyDimension):
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
    additional_filters = Q()  # Equals no filter
    match dimension:
        case AssemblyDimension.AREA:
            declared_units = [Unit.M3, Unit.M2, Unit.KG, Unit.PCS]
            # Limit to KG EPDs that have gross density
            additional_filters = Q(declared_unit=Unit.KG) & Q(
                conversions__contains=[{"unit": "kg/m^2"}]
            ) | ~Q(declared_unit=Unit.KG)
        case AssemblyDimension.VOLUME:
            declared_units = [Unit.M3, Unit.KG, Unit.PCS]
            # Limit to KG EPDs that have gross density
            additional_filters = Q(declared_unit=Unit.KG) & Q(
                conversions__contains=[{"unit": "kg/m^3"}]
            ) | ~Q(declared_unit=Unit.KG)
        case AssemblyDimension.MASS:
            declared_units = [Unit.M3, Unit.KG, Unit.PCS]
        case AssemblyDimension.LENGTH:
            declared_units = [Unit.M3, Unit.M, Unit.KG, Unit.PCS]
            # Limit to KG EPDs that have gross density
            additional_filters = Q(declared_unit=Unit.KG) & Q(
                conversions__contains=[{"unit": "kg/m"}]
            ) | ~Q(declared_unit=Unit.KG)
        case _:
            return epds

    return epds.filter(declared_unit__in=declared_units).filter(additional_filters)


def get_filtered_epd_list(request, dimension=None):
    # Start with the base queryset
    filtered_epds = EPD.objects.all().order_by("id")
    if (
        request.method == "POST"
        and request.POST.get("action") == "filter"
        or request.method == "GET"
        and request.GET.get("page")
    ):
        req = request.POST if request.method == "POST" else request.GET
        # Add filters conditionally
        if dimension := req.get("dimension"):
            filtered_epds = filter_by_dimension(filtered_epds, dimension)

        if childcategory := req.get("childcategory"):
            childcategory_object = get_object_or_404(
                MaterialCategory, pk=int(childcategory)
            )
            filtered_epds = filtered_epds.filter(category=childcategory_object)
        elif subcategory := req.get("subcategory"):
            subcategory_object = get_object_or_404(
                MaterialCategory, pk=int(subcategory)
            )
            filtered_epds = filtered_epds.filter(
                category__category_id__istartswith=subcategory_object.category_id
            )
        elif category := req.get("category"):
            category_object = get_object_or_404(MaterialCategory, pk=int(category))
            filtered_epds = filtered_epds.filter(
                category__category_id__istartswith=category_object.category_id
            )

        if search_query := req.get("search_query"):
            search_terms = search_query.split()
            query = Q()
            # Add a case-insensitive filter for each search term
            for term in search_terms:
                query &= Q(name__icontains=term)

            filtered_epds = filtered_epds.filter(query)

        if country := req.get("country"):
            filtered_epds = filtered_epds.filter(
                country=country
            )  # Adjust the field for your model
    elif dimension:
        filtered_epds = filter_by_dimension(filtered_epds, dimension)
    return filtered_epds, dimension
