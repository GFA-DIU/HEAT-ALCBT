"""
View for handling structural components selection in the add-building wizard.
Provides HTMX endpoints for filtering, selecting, and managing structural EPDs.
"""

import json
import logging
from datetime import datetime
import uuid as uuid_lib

from cities_light.models import Country
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
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
from pages.models.epd import EPD, MaterialCategory, Unit
from pages.views.assembly.epd_dimension_info import get_epd_dimension_info
from pages.views.assembly.epd_filtering import get_filtered_epd_list
from pages.views.assembly.epd_processing import get_epd_list
from pages.views.building.impact_calculation import calculate_impacts, ImpactCalculationError

logger = logging.getLogger(__name__)


def _epd_has_conversion(epd, name):
    """Return the conversion value by name from the EPD's conversions field, or None."""
    if not epd.conversions:
        return None
    for item in epd.conversions:
        if item.get("name") == name:
            try:
                return float(item.get("value", 0)) or None
            except (TypeError, ValueError):
                return None
    return None


def _can_epd_be_used(dimension: str, epd) -> tuple[bool, str]:
    """
    Check whether the EPD can be converted for the given assembly dimension.
    Returns (True, "") if usable, or (False, reason_message) if not.

    Mirrors the logic in _resolve_conversion_factor so we catch mismatches
    before the user adds the EPD rather than only at calculation time.
    """
    declared = epd.declared_unit

    # PCS dimension: accepts pcs EPDs directly; also accepts kg/m²/m³ EPDs if DB has ratio
    if dimension == AssemblyDimension.PCS:
        if declared == Unit.PCS:
            return True, ""
        if declared == Unit.KG:
            if _epd_has_conversion(epd, "conversion factor to 1 kg"):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in kg) to a pcs component: "
                "conversion factor to 1 kg missing from EPD conversions."
            )
        if declared == Unit.M2:
            if _epd_has_conversion(epd, "area density"):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in m²) to a pcs component: "
                "area density (pcs/m²) missing from EPD conversions."
            )
        if declared == Unit.M3:
            if _epd_has_conversion(epd, "volume density"):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in m³) to a pcs component: "
                "volume density (pcs/m³) missing from EPD conversions."
            )
        return False, (
            f"This EPD is declared in '{declared}' and cannot be used in a pcs component."
        )

    # EPD declared in pcs: user enters pieces-per-unit factor — always allowed for any dimension
    if declared == Unit.PCS:
        return True, ""

    # Direct unit match — always fine
    direct_match = {
        AssemblyDimension.AREA: Unit.M2,
        AssemblyDimension.VOLUME: Unit.M3,
        AssemblyDimension.MASS: Unit.KG,
        AssemblyDimension.LENGTH: Unit.M,
    }
    if declared == direct_match.get(dimension):
        return True, ""

    # AREA assembly
    if dimension == AssemblyDimension.AREA:
        if declared == Unit.M3:
            return True, ""  # needs thickness — entered by user
        if declared == Unit.KG:
            if (_epd_has_conversion(epd, "area density") or
                    _epd_has_conversion(epd, "volume density") or
                    _epd_has_conversion(epd, "conversion factor to 1 kg")):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in kg) to an area (m²) component: "
                "no area density, volume density, or conversion factor is available for this EPD."
            )
        if declared == Unit.PCS:
            return True, ""  # user enters pieces per m²

    # VOLUME assembly
    if dimension == AssemblyDimension.VOLUME:
        if declared == Unit.KG:
            if (_epd_has_conversion(epd, "volume density") or
                    _epd_has_conversion(epd, "conversion factor to 1 kg")):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in kg) to a volume (m³) component: "
                "no volume density or conversion factor is available for this EPD."
            )
        if declared == Unit.M2:
            return True, ""  # needs thickness
        if declared == Unit.PCS:
            return True, ""  # user enters pieces per m³

    # MASS assembly
    if dimension == AssemblyDimension.MASS:
        if declared == Unit.M3:
            if _epd_has_conversion(epd, "volume density"):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in m³) to a mass (kg) component: "
                "no volume density is available for this EPD."
            )
        if declared == Unit.M2:
            if _epd_has_conversion(epd, "area density"):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in m²) to a mass (kg) component: "
                "no area density is available for this EPD."
            )
        if declared == Unit.PCS:
            return True, ""  # user enters pieces per kg

    # LENGTH assembly
    if dimension == AssemblyDimension.LENGTH:
        if declared == Unit.M3:
            return True, ""  # needs cross-section
        if declared == Unit.KG:
            if (_epd_has_conversion(epd, "linear density") or
                    _epd_has_conversion(epd, "volume density")):
                return True, ""
            return False, (
                f"Cannot add this EPD (declared in kg) to a length (m) component: "
                "no linear density or volume density is available for this EPD."
            )
        if declared == Unit.PCS:
            return True, ""  # user enters pieces per m

    return False, (
        f"This EPD (declared in '{declared}') is not compatible with a "
        f"'{dimension}' component and no conversion factor exists to bridge the unit mismatch."
    )


@login_required
@require_http_methods(["GET", "POST"])
def building_step_structural_products(request):
    """Handle structural products selection for the add-building wizard."""
    # Check if request has JSON body
    action = None
    if request.method == "POST":
        # Try to parse JSON body first
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                action = data.get("action")
            except json.JSONDecodeError:
                pass

        # Fall back to form data
        if not action:
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
    elif action == "search_templates":
        return handle_search_templates(request)

    elif action == "save_assembly":
        return handle_save_assembly(request)
    elif action == "delete_assembly":
        return handle_delete_assembly(request)
    else:
        return handle_filter_epds(request)


def handle_filter_epds(request):
    """Filter and return structural EPD list."""
    dimension = request.POST.get("dimension") or request.GET.get("dimension")
    mode = request.POST.get("mode") or request.GET.get("mode", "boq")
    epd_list, _ = get_epd_list(request, dimension=dimension, operational=False)

    form = EPDsFilterForm(request.POST if request.method == "POST" else request.GET)

    req = request.POST if request.method == "POST" else request.GET
    filter_params = []
    for key in ['search_query', 'country', 'category', 'subcategory', 'childcategory', 'type', 'dimension', 'mode']:
        value = req.get(key)
        if value:
            filter_params.append(f"{key}={value}")
    filters_str = "&".join(filter_params)

    context = {
        "epd_list": epd_list,
        "filters": filters_str,
        "epd_filters_form": form,
        "dimension": dimension,
        "mode": mode,
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

        available_units = epd.get_available_units()
        if available_units is None:
            available_units = [epd.declared_unit]
        elif isinstance(available_units, set):
            available_units = sorted(list(available_units))

        # For component mode, block the add if no valid conversion path exists.
        if mode == "component":
            ok, reason = _can_epd_be_used(dimension, epd)
            if not ok:
                return HttpResponse(reason, status=422)

        # Derive the correct input label and unit for the quantity field.
        # For component mode: use the assembly dimension via get_epd_dimension_info.
        # For BoQ mode: the user always enters a direct quantity in the EPD's declared unit
        #   (each row is its own material line, not a share of a mixed assembly).
        #   The only exception is pcs EPDs which use a pieces count.
        selection_text = ""
        selection_unit = epd.declared_unit
        if mode == "boq":
            # In BoQ mode the quantity is always the raw quantity in the declared unit.
            # Map the declared unit to a human-readable label for the input placeholder.
            _boq_unit_labels = {
                Unit.M2:  ("Area (m²)", Unit.M2),
                Unit.M3:  ("Volume (m³)", Unit.M3),
                Unit.KG:  ("Mass (kg)", Unit.KG),
                Unit.M:   ("Length (m)", Unit.M),
                Unit.PCS: ("Quantity (pcs)", Unit.PCS),
            }
            label_pair = _boq_unit_labels.get(epd.declared_unit)
            if label_pair:
                selection_text, selection_unit = label_pair
        else:
            try:
                selection_text, selection_unit = get_epd_dimension_info(dimension, epd.declared_unit)
            except (ValueError, KeyError):
                selection_unit = epd.declared_unit

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
            "gwp": epd.get_gwp_impact_sum("a1a3") or 0,
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
    """Get assembly categories (HTMX endpoint). Returns JSON when format=json."""
    categories = list(AssemblyCategory.objects.all().values('id', 'name'))

    if request.GET.get('format') == 'json':
        return JsonResponse({'categories': categories})

    options = ['<option value="">Select category</option>']
    for cat in categories:
        options.append(f'<option value="{cat["id"]}">{cat["name"]}</option>')

    return HttpResponse(''.join(options))


def handle_get_subcategories(request):
    """Get material subcategories/childcategories for a parent category (HTMX endpoint).

    When `parent=subcategory` is passed, the `subcategory` param is used as the
    parent to return child categories (level 3). Otherwise `category` is used to
    return subcategories (level 2).
    """
    req = request.POST if request.method == "POST" else request.GET
    parent_type = req.get("parent", "category")

    if parent_type == "subcategory":
        parent_id = req.get("subcategory")
        empty_label = "All Child Categories"
    else:
        parent_id = req.get("category")
        empty_label = "All Sub-categories"

    if not parent_id:
        return HttpResponse(f'<option value="">{empty_label}</option>')

    try:
        children = MaterialCategory.objects.filter(
            parent_id=parent_id
        ).order_by("name_en").values('id', 'name_en')

        options = [f'<option value="">{empty_label}</option>']
        for child in children:
            options.append(f'<option value="{child["id"]}">{child["name_en"]}</option>')

        return HttpResponse(''.join(options))
    except Exception as e:
        logger.error(f"Error fetching subcategories: {e}")
        return HttpResponse(f'<option value="">Error loading categories</option>')


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
        is_template = assembly_data.get("is_template", False)
        logger.info(f"is_template value from assembly_data: {is_template}, type: {type(is_template)}")

        if mode == "boq":
            assembly.name = assembly_data.get("name", "Untitled BOQ")
            assembly.comment = assembly_data.get("comment", "")
            assembly.is_boq = True
            assembly.mode = AssemblyMode.CUSTOM
            assembly.dimension = AssemblyDimension.AREA  # Default for BOQ
            assembly.is_template = is_template
        else:  # component
            assembly.name = assembly_data.get("title", "Untitled Component")
            assembly.comment = assembly_data.get("comment", "")
            assembly.is_boq = False
            assembly.mode = AssemblyMode.CUSTOM
            assembly.dimension = assembly_data.get("dimension", AssemblyDimension.AREA)
            assembly.is_template = is_template

        logger.info(f"About to save assembly with is_template={assembly.is_template}")
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

        # Compute server-side GWP preview (A1-A3) for the saved assembly
        total_gwp = 0.0
        try:
            floor_area = float(building.total_floor_area) if building.total_floor_area else 1.0
            products = assembly.structuralproduct_set.select_related("epd").prefetch_related(
                "epd__epdimpact_set__impact"
            )
            for sp in products:
                try:
                    impacts = calculate_impacts(
                        dimension=assembly.dimension,
                        assembly_quantity=building_assembly.quantity,
                        total_floor_area=floor_area,
                        p=sp,
                    )
                    for impact in impacts:
                        if (impact["impact_type"].impact_category == "gwp" and
                                impact["impact_type"].life_cycle_stage == "a1a3"):
                            val = float(impact["impact_value"])
                            if val > 0:
                                total_gwp += val
                except (ImpactCalculationError, ValueError, ZeroDivisionError):
                    pass
        except Exception:
            pass

        # Return success with assembly data including server-computed GWP
        return JsonResponse({
            "success": True,
            "message": f"{'BOQ' if mode == 'boq' else 'Component'} saved successfully",
            "assembly": {
                "id": assembly.id,
                "name": assembly.name,
                "mode": mode,
                "materials_count": len(materials),
                "total_gwp": round(total_gwp, 4),
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




def handle_search_templates(request):
    """
    Search and filter templates (assemblies) for selection in building structural components.
    Reuses logic from templates view with same filters.
    """
    # Start with base queryset - show public assemblies and user's custom assemblies
    assemblies = Assembly.objects.filter(
        Q(public=True) | Q(created_by=request.user),
        draft=False,
        is_boq=False,  # Exclude Bill of Quantities
    )

    # Get filter parameters
    search_query = request.GET.get("search_query", "").strip()
    country_id = request.GET.get("country", "").strip()
    category_id = request.GET.get("category", "").strip()
    technique_id = request.GET.get("technique", "").strip()
    mode = request.GET.get("mode", "").strip()  # system or custom
    sort_by = request.GET.get("sort_by", "-created_at")  # Default sort by newest first

    # Apply search filter
    if search_query:
        assemblies = assemblies.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(comment__icontains=search_query)
        )

    # Apply country filter
    if country_id:
        assemblies = assemblies.filter(country_id=country_id)

    # Apply category filter (via StructuralProduct classification)
    if category_id:
        assemblies = assemblies.filter(
            structuralproduct__classification__category_id=category_id
        ).distinct()

    # Apply technique filter
    if technique_id:
        assemblies = assemblies.filter(
            structuralproduct__classification__technique_id=technique_id
        ).distinct()

    # Apply mode filter (System Component vs My Component)
    if mode:
        assemblies = assemblies.filter(mode=mode)

    # Optimize queries with prefetch_related and select_related
    assemblies = assemblies.select_related("country", "city", "created_by").prefetch_related(
        Prefetch(
            "structuralproduct_set",
            queryset=StructuralProduct.objects.select_related(
                "epd", "classification__category", "classification__technique"
            ),
        )
    )

    # Apply sorting
    sort_options = {
        "name": "name",
        "-name": "-name",
        "created_at": "created_at",
        "-created_at": "-created_at",
    }
    assemblies = assemblies.order_by(sort_options.get(sort_by, "name"))

    # Pagination
    paginator = Paginator(assemblies, 10)  # 10 items per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Calculate GWP for each assembly
    assemblies_with_gwp = []
    for assembly in page_obj:
        total_gwp = 0
        classification = None

        # Get total GWP from structural products
        for structural_product in assembly.structuralproduct_set.all():
            if structural_product.epd:
                # Get the quantity
                quantity = structural_product.quantity or 0

                # Calculate GWP for A1-A3 stage (production stage)
                try:
                    gwp_a1a3 = structural_product.epd.get_gwp_impact_sum("a1a3")
                    total_gwp += float(quantity) * float(gwp_a1a3)
                except Exception:
                    # If there's an error getting GWP, just skip this product
                    pass

            # Get classification from first product
            if not classification and structural_product.classification:
                classification = structural_product.classification

        assemblies_with_gwp.append({
            "assembly": assembly,
            "total_gwp": round(total_gwp, 2),
            "classification": classification,
        })

    context = {
        "assemblies_with_gwp": assemblies_with_gwp,
        "page_obj": page_obj,
        "search_query": search_query,
        "selected_country": country_id,
        "selected_category": category_id,
        "selected_technique": technique_id,
        "selected_mode": mode,
        "selected_sort": sort_by,
    }

    return render(
        request,
        "pages/add-building/components/building-structural-components/partials/templates_selection_list.html",
        context
    )
