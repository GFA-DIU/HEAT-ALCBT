"""
View for handling structural components selection in the add-building wizard.
Provides HTMX endpoints for filtering, selecting, and managing structural EPDs.
"""

import json
import logging
from datetime import datetime
import uuid as uuid_lib

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import (
    Assembly, AssemblyCategory, AssemblyDimension, AssemblyMode,
    AssemblyTechnique, AssemblyCategoryTechnique, StructuralProduct
)
from pages.models.base import ALCBTCountryManager
from pages.models.building import Building, BuildingAssembly
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
    elif action == "save_assembly":
        return handle_save_assembly(request)
    elif action == "delete_assembly":
        return handle_delete_assembly(request)
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


@transaction.atomic
def handle_save_assembly(request):
    """
    Save a structural assembly (BOQ or component) to database.

    Expected POST data (JSON):
    {
        "building_uuid": str,
        "mode": "boq" or "component",
        "assembly_id": int (optional, for updates),
        "assembly_data": {
            # For BOQ:
            "name": str,
            "comment": str,
            "materials": [
                {
                    "epd_id": int,
                    "quantity": float,
                    "unit": str,
                    "description": str,
                    "category": int,  # AssemblyCategory ID
                    "gwp": float
                }
            ]

            # For Component:
            "title": str,
            "category": int,  # AssemblyCategory ID
            "technique": int,  # AssemblyTechnique ID (optional)
            "dimension": str,  # area, length, mass, volume
            "quantity": float,
            "comment": str,
            "materials": [
                {
                    "epd_id": int,
                    "quantity": float,
                    "unit": str,
                    "description": str,
                    "gwp": float
                }
            ]
        }
    }
    """
    try:
        data = json.loads(request.body)
        building_uuid = data.get("building_uuid")
        mode = data.get("mode")  # "boq" or "component"
        assembly_data = data.get("assembly_data", {})
        assembly_id = data.get("assembly_id")  # For updates

        if not building_uuid:
            return JsonResponse({"success": False, "error": "Building UUID is required"}, status=400)

        if not mode or mode not in ["boq", "component"]:
            return JsonResponse({"success": False, "error": "Invalid mode"}, status=400)

        # Get building
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
        except (ValueError, Building.DoesNotExist):
            logger.error(f"Building not found for UUID: {building_uuid}")
            return JsonResponse({"success": False, "error": "Building not found"}, status=404)

        # Validate materials
        materials = assembly_data.get("materials", [])
        if not materials:
            return JsonResponse({"success": False, "error": "At least one material is required"}, status=400)

        # Create or update Assembly
        if assembly_id:
            # Update existing assembly
            try:
                assembly = Assembly.objects.get(id=assembly_id, created_by=request.user)
                # Delete existing structural products
                StructuralProduct.objects.filter(assembly=assembly).delete()
            except Assembly.DoesNotExist:
                return JsonResponse({"success": False, "error": "Assembly not found"}, status=404)
        else:
            # Create new assembly
            assembly = Assembly(created_by=request.user)

        # Set assembly fields based on mode
        if mode == "boq":
            assembly.name = assembly_data.get("name", "Untitled BOQ")
            assembly.comment = assembly_data.get("comment", "")
            assembly.is_boq = True
            assembly.mode = AssemblyMode.CUSTOM
            assembly.dimension = AssemblyDimension.AREA  # Default for BOQ
        else:  # component
            assembly.name = assembly_data.get("title", "Untitled Component")
            assembly.comment = assembly_data.get("comment", "")
            assembly.is_boq = False
            assembly.mode = AssemblyMode.CUSTOM
            assembly.dimension = assembly_data.get("dimension", AssemblyDimension.AREA)

        assembly.save()

        # Create StructuralProduct records for each material
        for material in materials:
            epd_id = material.get("epd_id")
            if not epd_id:
                continue

            try:
                epd = EPD.objects.get(id=epd_id)
            except EPD.DoesNotExist:
                logger.warning(f"EPD {epd_id} not found, skipping")
                continue

            # Get classification (category + technique)
            classification = None
            if mode == "boq":
                # BOQ mode: each material can have its own category
                category_id = material.get("category")
                if category_id:
                    try:
                        classification = AssemblyCategoryTechnique.objects.get(
                            category_id=category_id,
                            technique__isnull=True  # BOQ doesn't use techniques
                        )
                    except AssemblyCategoryTechnique.DoesNotExist:
                        logger.warning(f"Classification not found for category {category_id}")
            else:
                # Component mode: all materials share the same category + technique
                category_id = assembly_data.get("category")
                technique_id = assembly_data.get("technique") or None

                if category_id:
                    try:
                        classification = AssemblyCategoryTechnique.objects.get(
                            category_id=category_id,
                            technique_id=technique_id
                        )
                    except AssemblyCategoryTechnique.DoesNotExist:
                        logger.warning(f"Classification not found for category {category_id}, technique {technique_id}")

            StructuralProduct.objects.create(
                epd=epd,
                assembly=assembly,
                quantity=material.get("quantity", 0),
                input_unit=material.get("unit", epd.declared_unit),
                description=material.get("description", ""),
                classification=classification
            )

        # Create or update BuildingAssembly join record
        if mode == "component":
            # Component mode has quantity at assembly level
            assembly_quantity = assembly_data.get("quantity", 1)
        else:
            # BOQ mode doesn't have assembly-level quantity
            assembly_quantity = 1

        building_assembly, created = BuildingAssembly.objects.update_or_create(
            building=building,
            assembly=assembly,
            defaults={
                "quantity": assembly_quantity,
                "reporting_life_cycle": 50  # Default lifecycle
            }
        )

        logger.info(f"Saved assembly {assembly.id} ({mode}) for building {building.id}")

        # Return success with assembly data
        return JsonResponse({
            "success": True,
            "message": f"{'BOQ' if mode == 'boq' else 'Component'} saved successfully",
            "assembly": {
                "id": assembly.id,
                "name": assembly.name,
                "mode": mode,
                "materials_count": materials.__len__()
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.exception(f"Error saving assembly: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@transaction.atomic
def handle_delete_assembly(request):
    """
    Delete a structural assembly.

    Expected POST data (JSON):
    {
        "building_uuid": str,
        "assembly_id": int
    }
    """
    try:
        data = json.loads(request.body)
        building_uuid = data.get("building_uuid")
        assembly_id = data.get("assembly_id")

        if not building_uuid or not assembly_id:
            return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)

        # Get building
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
        except (ValueError, Building.DoesNotExist):
            return JsonResponse({"success": False, "error": "Building not found"}, status=404)

        # Delete BuildingAssembly (cascades to delete assembly if not used elsewhere)
        try:
            building_assembly = BuildingAssembly.objects.get(
                building=building,
                assembly_id=assembly_id
            )
            assembly_name = building_assembly.assembly.name
            building_assembly.delete()

            # Also delete the assembly itself if it's custom and only belonged to this building
            assembly = Assembly.objects.filter(id=assembly_id, created_by=request.user)
            if assembly.exists() and not BuildingAssembly.objects.filter(assembly_id=assembly_id).exists():
                assembly.delete()

            logger.info(f"Deleted assembly {assembly_id} from building {building.id}")

            return JsonResponse({
                "success": True,
                "message": f"Assembly '{assembly_name}' deleted successfully"
            })

        except BuildingAssembly.DoesNotExist:
            return JsonResponse({"success": False, "error": "Assembly not found"}, status=404)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.exception(f"Error deleting assembly: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
