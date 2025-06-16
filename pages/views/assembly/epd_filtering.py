from django.db.models import Q
from django.db.models.manager import BaseManager
from django.shortcuts import get_object_or_404

from pages.models.assembly import AssemblyDimension
from pages.models.epd import EPD, EPDType, MaterialCategory, Unit


def filter_by_dimension(epds: BaseManager[EPD], dimension: AssemblyDimension):
    """Logic for filering EPDs from DB by Assembly Dimension.

    This is the logic:
    | **    Declared unit   ** | **    Area Assembly   ** | **    Volume Assembly   ** | **    Mass Assembly   ** | **    Length Assembly   ** |
    |--------------------------|--------------------------|----------------------------|--------------------------|----------------------------|
    |     m3                   |     Yes                  |     Yes                    |     w. Volume density    |     Yes                    |
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
            additional_filters = (
                Q(declared_unit=Unit.KG) & Q(conversions__contains=[{"unit": "kg/m^3"}])
            ) | ~Q(declared_unit=Unit.KG)
        case AssemblyDimension.VOLUME:
            declared_units = [Unit.M3, Unit.KG, Unit.PCS]
            # Limit to KG EPDs that have gross density
            additional_filters = (
                Q(declared_unit=Unit.KG) & Q(conversions__contains=[{"unit": "kg/m^3"}])
            ) | ~Q(declared_unit=Unit.KG)
        case AssemblyDimension.MASS:
            declared_units = [Unit.M3, Unit.KG, Unit.PCS]
            additional_filters = (
                Q(declared_unit=Unit.M3) & Q(conversions__contains=[{"unit": "kg/m^3"}])
            ) | ~Q(declared_unit=Unit.M3)
        case AssemblyDimension.LENGTH:
            declared_units = [Unit.M3, Unit.M, Unit.KG, Unit.PCS]
            # Limit to KG EPDs that have gross density
            additional_filters = (
                Q(declared_unit=Unit.KG) & Q(conversions__contains=[{"unit": "kg/m^3"}])
            ) | ~Q(declared_unit=Unit.KG)
        case _:
            raise ValueError(f"Unsupported dimension '{dimension}'")

    return epds.filter(declared_unit__in=declared_units).filter(additional_filters)


def get_filtered_epd_list(request, dimension=None, operational=False):
    # Start with the base queryset
    filtered_epds = EPD.objects.exclude(declared_unit=Unit.UNKNOWN).order_by("id")
    if operational:
        # TODO: Adapt with Ökobaudat operational EPDs are added
        filtered_epds = filtered_epds.filter(
            category__parent__category_id="9.2",
            declared_unit=Unit.KWH,
            type=EPDType.GENERIC,
        )
    else:
        filtered_epds = filtered_epds.filter(
            ~(Q(category__parent__category_id="9.2") | Q(declared_unit=Unit.KWH))
        )

    if (
        request.method == "POST"
        and request.POST.get("action") == "filter"
        or request.method == "GET"
        and request.GET.get("page")
    ):
        req = request.POST if request.method == "POST" else request.GET
        # Add filters conditionally
        dimension = req.get("dimension")
        if dimension and dimension != "None":
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

        if type := req.get("type"):
            filtered_epds = filtered_epds.filter(type=type)
    elif dimension:
        filtered_epds = filter_by_dimension(filtered_epds, dimension)
    return filtered_epds, dimension
