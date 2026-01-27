"""
View for handling structural components selection in the add-building wizard.
Provides HTMX endpoints for filtering, selecting, and managing structural EPDs.
"""

import logging
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import AssemblyCategory, AssemblyTechnique, AssemblyCategoryTechnique
from pages.models.base import ALCBTCountryManager
from pages.models.epd import EPD, MaterialCategory
from pages.views.assembly.epd_filtering import get_filtered_epd_list
from pages.views.assembly.epd_processing import get_epd_list

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def building_step_structural_products(request):
    """Handle structural products selection for the add-building wizard."""
    if request.method == "POST":
        action = request.POST.get("action", "list")
    else:
        action = request.GET.get("action", "list")

    if action == "filter":
        return handle_filter_epds(request)
    elif action == "select_structural_product":
        return handle_select_product(request)
    elif action == "get_techniques":
        return handle_get_techniques(request)
    elif action == "get_categories":
        return handle_get_categories(request)
    elif action == "get_subcategories":
        return handle_get_subcategories(request)
    else:
        return handle_filter_epds(request)


def handle_filter_epds(request):
    """Filter and return structural EPD list."""
    dimension = request.POST.get("dimension") or request.GET.get("dimension")
    epd_list, _ = get_epd_list(request, dimension=dimension, operational=False)

    form = EPDsFilterForm(request.POST if request.method == "POST" else request.GET)

    req = request.POST if request.method == "POST" else request.GET
    filter_params = []
    for key in ['search_query', 'country', 'category', 'subcategory', 'childcategory', 'type', 'dimension']:
        value = req.get(key)
        if value:
            filter_params.append(f"{key}={value}")
    filters_str = "&".join(filter_params)

    context = {
        "epd_list": epd_list,
        "filters": filters_str,
        "epd_filters_form": form,
        "dimension": dimension,
    }

    return render(
        request,
        "pages/add-building/components/building-structural-components/_epd_list.html",
        context
    )


def handle_select_product(request):
    """Add an EPD to the selected materials list."""
    epd_id = request.POST.get("epd_id")
    mode = request.POST.get("mode", "boq")  # 'boq' or 'component'
    dimension = request.POST.get("dimension", "area")

    if not epd_id:
        return HttpResponse("EPD ID required", status=400)

    try:
        epd = EPD.objects.select_related('country', 'category').get(id=epd_id)
        epd_info = epd.get_epd_info(dimension)

        available_units = epd.get_available_units()
        if available_units is None:
            available_units = [epd.declared_unit]
        elif isinstance(available_units, set):
            available_units = sorted(list(available_units))

        # epd_info returns (selection_text, selection_unit) tuple or None
        selection_text = ""
        selection_unit = epd.declared_unit
        if epd_info and isinstance(epd_info, (list, tuple)) and len(epd_info) >= 2:
            selection_text = epd_info[0] or ""
            selection_unit = epd_info[1] or epd.declared_unit

        epd_data = {
            "id": str(epd.id),
            "name": epd.name,
            "country": epd.country.code2 if epd.country else "",
            "country_name": epd.country.name if epd.country else "Unknown",
            "category": epd.category.name_en if epd.category else "Unknown",
            "declared_unit": epd.declared_unit,
            "selection_unit": selection_unit,
            "selection_text": selection_text,
            "timestamp": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "available_units": available_units,
            "gwp": epd.get_gwp_impact_sum("A1-A3") or 0,
        }

        # Get assembly categories for BOQ mode
        categories = []
        if mode == "boq":
            categories = list(AssemblyCategory.objects.values('id', 'name'))

        context = {
            "epd": epd_data,
            "mode": mode,
            "categories": categories,
        }

        return render(
            request,
            "pages/add-building/components/building-structural-components/_selected_material.html",
            context
        )

    except EPD.DoesNotExist:
        return HttpResponse("EPD not found", status=404)


def handle_get_techniques(request):
    """Get techniques for a category (HTMX endpoint)."""
    category_id = request.POST.get("category_id") or request.GET.get("category_id")

    if not category_id:
        return HttpResponse('<option value="">Select a category first</option>')

    try:
        techniques = AssemblyCategoryTechnique.objects.filter(
            category_id=category_id
        ).select_related('technique').values_list('technique__id', 'technique__name')

        options = ['<option value="">Select technique</option>']
        for tech_id, tech_name in techniques:
            if tech_name:
                options.append(f'<option value="{tech_id}">{tech_name}</option>')

        return HttpResponse(''.join(options))
    except Exception as e:
        logger.error(f"Error fetching techniques: {e}")
        return HttpResponse('<option value="">Error loading techniques</option>')


def handle_get_categories(request):
    """Get assembly categories (HTMX endpoint)."""
    categories = AssemblyCategory.objects.all().values('id', 'name')

    options = ['<option value="">Select category</option>']
    for cat in categories:
        options.append(f'<option value="{cat["id"]}">{cat["name"]}</option>')

    return HttpResponse(''.join(options))


def handle_get_subcategories(request):
    """Get material subcategories for a parent category (HTMX endpoint)."""
    category_id = request.POST.get("category") or request.GET.get("category")

    if not category_id:
        return HttpResponse('<option value="">Select category first</option>')

    try:
        subcategories = MaterialCategory.objects.filter(
            parent_id=category_id
        ).order_by("name_en").values('id', 'name_en')

        options = ['<option value="">All Sub-categories</option>']
        for subcat in subcategories:
            options.append(f'<option value="{subcat["id"]}">{subcat["name_en"]}</option>')

        return HttpResponse(''.join(options))
    except Exception as e:
        logger.error(f"Error fetching subcategories: {e}")
        return HttpResponse('<option value="">Error loading subcategories</option>')
