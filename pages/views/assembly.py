import logging
from collections import defaultdict
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional

from django.core.paginator import Paginator
from django.db.models import Prefetch,  Q
from django.db.models.manager import BaseManager
from django.http import HttpResponseServerError, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.forms import ValidationError

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import Assembly, AssemblyDimension, Product
from pages.models.building import Building, BuildingAssembly
from pages.models.epd import EPD, EPDImpact, MaterialCategory, Unit
from pages.forms.assembly_form import AssemblyForm


logger = logging.getLogger(__name__)


@dataclass
class SelectedEPD:
    id: str
    available_units: list[str]
    sel_unit: Optional[str]
    sel_quantity: float
    name: str
    category: Optional[str]
    country: Optional[str]
    source: Optional[str]

    @classmethod
    def parse_product(cls, product):
        """
        Parses a Product instance into a SelectedEPD dataclass.
        """
        available_units = [i["unit"] for i in product.epd.conversions]
        available_units.append(product.epd.declared_unit)

        return cls(
            id=str(product.epd.id),
            sel_unit=product.input_unit,
            available_units=available_units,
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
        available_units = [i["unit"] for i in epd.conversions]
        available_units.append(epd.declared_unit)

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
    pk: str
    name: str
    country: str
    conversions: str
    declared_unit: str
    selection_text: str
    selection_unit: str
    

@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, building_id, assembly_id=None):
    """
    View to either edit an existing component or create a new one with pagination for EPDs.
    """
    component = None
    if assembly_id:
        building_assembly = get_object_or_404(BuildingAssembly.objects.select_related(), assembly_id=assembly_id, building_id=building_id)
        # If there's non it will already throw an error so no need for checking
        component = building_assembly.assembly
    context = {
        "assembly_id": assembly_id,
        "building_id": building_id,
        "epd_list": get_epd_list(request, component),
        "epd_filters_form": EPDsFilterForm(request.POST),
        "dimension": request.POST.get("dimension")
    }
    building_instance = get_object_or_404(Building, pk=building_id)

    if request.method == "POST" and request.POST.get("action") == "form_submission":
        if not component:
            component = Assembly()
        save_assembly(request, component, building_instance)
        # The redirect shortcut is not working properly with HTMX
        # return redirect("building", building_id=building_instance.id)
        # instead use the following:
        response = JsonResponse({"message": "Redirecting"})
        response["HX-Redirect"] = reverse(
            "building", kwargs={"building_id": building_id}
        )
        return response

    elif (
        request.method == "GET"
        and request.GET.get("page")
        or request.method == "POST"
        and request.POST.get("action") == "filter"
    ):
        # Handle partial rendering for HTMX
        return render(request, "pages/building/component_add/epd_list.html", context)

    elif request.method == "GET" and request.GET.get("add_component") == "step_1":
        # TODO: Only makes sense for new component
        return render(
            request, "pages/building/component_add/modal_step_1.html", context
        )

    else:
        if component:
            products = Product.objects.filter(assembly=component).select_related("epd")
            selected_epds = [SelectedEPD.parse_product(p) for p in products]
            context["selected_epds"] = selected_epds
        context["form"] = AssemblyForm(instance=component)
        context["dimension"] = (
            component.dimension if component else AssemblyDimension.AREA
        )

    # Render full template for non-HTMX requests
    return render(request, "pages/building/component_add/editor_own_page.html", context)


def save_assembly(request, assembly: Assembly, building_instance: Building):
    print("This is a form submission")
    print(request.POST)
    # Bind the form to the existing Assembly instance
    form = AssemblyForm(request.POST, instance=assembly)
    if form.is_valid():
        # Save the updated Assembly instance
        assembly = form.save()

        # Create clean slate
        Product.objects.filter(assembly=assembly).delete()
        # AssemblyImpact.objects.filter(assembly=assembly).delete()

        # Identify selected EPDs
        selected_epds = {}
        for key, value in request.POST.items():
            if key.startswith("material_") and "_quantity" in key:
                epd_id = key.split("_")[1]
                selected_epds[epd_id] = {
                    "quantity": Decimal(value),
                    "unit": request.POST[f"material_{epd_id}_unit"],
                }

        # Pre-fetch EPDImpact and Impact objects
        epds = EPD.objects.filter(pk__in=selected_epds.keys()).prefetch_related(
            Prefetch(
                "epdimpact_set",
                queryset=EPDImpact.objects.select_related("impact"),
                to_attr="prefetched_impacts",
            )
        )
        epd_map = {str(epd.id): epd for epd in epds}
        # Save to products
        # TODO: Does this undermine the pre-fetching of the EPD data?
        products = []
        for k, v in selected_epds.items():
            products.append(
                Product.objects.create(
                    epd=epd_map[k],
                    assembly=assembly,
                    quantity=v.get("quantity"),
                    input_unit=v.get("unit"),
                )
            )
        
        # It doesn't duplicate if the assembly already is in structural_components
        building_instance.structural_components.add(assembly)


def get_epd_list(request, component):
    # TODO: can dimension every be None? For new component perhaps?
    filtered_list, dimension = get_filtered_epd_list(request, component.dimension if component else None)
    dimension = dimension if dimension else AssemblyDimension.AREA
    return parse_epds(filtered_list, dimension)


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


def parse_epds(epd_list: list[EPD], dimension: AssemblyDimension) -> list[FilteredEPD]:
    container = []
    for epd in epd_list:
        sel_text, sel_unit = get_epd_dimension_info(dimension, epd.declared_unit)
        container.append(
            FilteredEPD(
                    selection_text=sel_text,
                    selection_unit=sel_unit,
                    pk=epd.pk,
                    name=epd.name,
                    country=epd.country,
                    conversions=[],
                    declared_unit=epd.declared_unit
                )
        )
    
    return container


def get_epd_dimension_info(dimension: AssemblyDimension, unit: Unit):
    """Rule for input texts and units depending on Dimension."""
    match (dimension, unit):
        case (_, Unit.PCS):
            # 'Pieces' EPD is treated the same across all assembly dimensions
            selection_text = "Quantity"
            selection_unit = Unit.PCS
        case (AssemblyDimension.AREA, _):
            selection_text = "Layer Thickness"
            selection_unit = Unit.CM
        case (AssemblyDimension.VOLUME, _):
            selection_text = "Share of volume"
            selection_unit = Unit.PERCENT
        case (AssemblyDimension.MASS, _):
            selection_text = "Share of mass"
            selection_unit = Unit.KG
        case (AssemblyDimension.LENGTH, _):
            selection_text = "Share of cross-section"
            selection_unit = Unit.CM2
        case _:
            raise ValueError(
                f"Unsupported combination: dimension '{dimension}', declared_unit '{unit}'"
            )
    
    return selection_text, selection_unit    
            
                
