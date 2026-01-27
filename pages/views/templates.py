import json
from multiprocessing import context

from cities_light.models import Country
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from pages.models.assembly import (Assembly, AssemblyCategory, AssemblyMode,
                                   AssemblyTechnique, StructuralProduct)
from pages.models.epd import EPDType, MaterialCategory
from pages.views.assembly.epd_filtering import get_filtered_epd_list


def templates(request):
    """
    Display reusable assembly templates with search and filter functionality.
    Handles both full page load and HTMX partial updates.
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

                # Calculate GWP for A1-A3 stage (production stage - most common for embodied carbon)
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

    # Get filter options for dropdowns
    countries = Country.objects.all().order_by("name")
    categories = AssemblyCategory.objects.all().order_by("name")
    techniques = AssemblyTechnique.objects.all().order_by("name")

    # EPD categories for modal (top-level only)
    epd_categories = MaterialCategory.objects.filter(parent__isnull=True).order_by("name_en")
    epd_types = [{"value": t[0], "label": t[1]} for t in EPDType.choices]

    context = {
        "assemblies_with_gwp": assemblies_with_gwp,
        "page_obj": page_obj,
        "countries": countries,
        "categories": categories,
        "techniques": techniques,
        "epd_categories": epd_categories,
        "epd_types": epd_types,
        "search_query": search_query,
        "selected_country": country_id,
        "selected_category": category_id,
        "selected_technique": technique_id,
        "selected_mode": mode,
        "selected_sort": sort_by,
    }

    # If HTMX request, return only the list partial
    if request.headers.get("HX-Request"):
        return render(request, "pages/home/partials/templates_list.html", context)

    return render(request, "pages/home/templates.html", context)


def get_template_detail(request, template_id):
    """
    Get template (assembly) details as JSON for the view modal.
    """
    # Get the assembly
    assembly = get_object_or_404(
        Assembly.objects.select_related("country", "city")
        .prefetch_related(
            Prefetch(
                "structuralproduct_set",
                queryset=StructuralProduct.objects.select_related(
                    "epd",
                    "epd__country",
                    "classification__category",
                    "classification__technique",
                ),
            )
        ),
        id=template_id,
    )

    # Check permissions - user must be owner or template must be public
    if not assembly.public and assembly.created_by != request.user:
        return JsonResponse({"error": "Permission denied"}, status=403)

    # Calculate total GWP
    total_gwp = 0
    materials = []

    for structural_product in assembly.structuralproduct_set.all():
        material_gwp = 0

        if structural_product.epd:
            quantity = structural_product.quantity or 0
            try:
                gwp_a1a3 = structural_product.epd.get_gwp_impact_sum("a1a3")
                material_gwp = float(quantity) * float(gwp_a1a3)
                total_gwp += material_gwp
            except Exception:
                pass

        materials.append(
            {
                "id": str(structural_product.id),
                "name": structural_product.epd.name if structural_product.epd else "Unknown",
                "description": structural_product.description or "",
                "quantity": float(structural_product.quantity) if structural_product.quantity else 0,
                "unit": structural_product.input_unit,
                "gwp": round(material_gwp, 2),
                "country_code": structural_product.epd.country.code2 if structural_product.epd and structural_product.epd.country else None,
                "country_name": structural_product.epd.country.name if structural_product.epd and structural_product.epd.country else None,
                "epd_link": f"/epd/{structural_product.epd.id}/" if structural_product.epd else None,
            }
        )

    # Get classification info
    classification = None
    category_id = None
    technique_id = None
    if assembly.structuralproduct_set.first():
        first_product = assembly.structuralproduct_set.first()
        if first_product.classification:
            classification = {
                "category": first_product.classification.category.name,
                "technique": first_product.classification.technique.name
                if first_product.classification.technique
                else None,
            }
            category_id = first_product.classification.category.id
            technique_id = first_product.classification.technique.id if first_product.classification.technique else None

    data = {
        "id": str(assembly.id),
        "name": assembly.name,
        "description": assembly.description or "",
        "comment": assembly.comment or "",
        "country_id": assembly.country.id if assembly.country else None,
        "country_code": assembly.country.code2 if assembly.country else None,
        "country_name": assembly.country.name if assembly.country else None,
        "city": assembly.city.name if assembly.city else None,
        "dimension": assembly.dimension,
        "dimension_display": assembly.get_dimension_display(),
        "mode": assembly.mode,
        "mode_display": "System Component" if assembly.mode == "system" else "My Component",
        "total_gwp": round(total_gwp, 2),
        "classification": classification,
        "category_id": category_id,
        "technique_id": technique_id,
        "materials": materials,
        "can_edit": assembly.created_by == request.user,
        "created_at": assembly.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": assembly.updated_at.strftime("%Y-%m-%d %H:%M"),
    }

    return JsonResponse(data)


@require_http_methods(["POST"])
@transaction.atomic
def update_template(request, template_id):
    """Update an existing template (owner only)."""
    assembly = get_object_or_404(Assembly, id=template_id)

    # Only owner can update
    if assembly.created_by != request.user:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        data = json.loads(request.body)

        # Update assembly fields
        assembly.name = data.get("name", assembly.name)
        assembly.comment = data.get("comment", assembly.comment)

        if data.get("country_id"):
            assembly.country_id = data["country_id"]

        assembly.save()

        # Update/create materials
        materials_data = data.get("materials", [])
        new_materials_data = data.get("new_materials", [])

        # Update existing materials (description and quantity only)
        for material_data in materials_data:
            material_id = material_data.get("id")
            if material_id and not str(material_id).startswith("new_"):
                try:
                    product = StructuralProduct.objects.get(id=material_id, assembly=assembly)
                    product.description = material_data.get("description", product.description)
                    product.quantity = material_data.get("quantity", product.quantity)
                    product.save()
                except StructuralProduct.DoesNotExist:
                    pass

        # Create new materials from EPD modal
        for new_material in new_materials_data:
            epd_id = new_material.get("epd_id")
            if epd_id:
                from pages.models.epd import EPD
                try:
                    epd = EPD.objects.get(id=epd_id)

                    # Get correct unit based on assembly dimension
                    dimension = None if assembly.is_boq else assembly.dimension
                    _, expected_units = epd.get_epd_info(dimension)
                    # Use first expected unit as default
                    input_unit = expected_units[0] if expected_units else epd.declared_unit

                    StructuralProduct.objects.create(
                        assembly=assembly,
                        epd=epd,
                        description=new_material.get("description", ""),
                        quantity=new_material.get("quantity", 0),
                        input_unit=input_unit,
                    )
                except EPD.DoesNotExist:
                    pass

        # Delete materials marked for deletion
        deleted_ids = data.get("deleted_materials", [])
        if deleted_ids:
            # Filter out temp IDs (new_*)
            real_ids = [id for id in deleted_ids if not str(id).startswith("new_")]
            if real_ids:
                StructuralProduct.objects.filter(id__in=real_ids, assembly=assembly).delete()

        return JsonResponse({"success": True, "message": "Template updated successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_http_methods(["POST"])
@transaction.atomic
def duplicate_template(request, template_id):
    """Create a copy of a template."""
    original = get_object_or_404(Assembly, id=template_id)

    # Check permissions
    if not original.public and original.created_by != request.user:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        data = json.loads(request.body)

        # Create copy
        copy = Assembly.objects.create(
            name=f"Copy of {data.get('name', original.name)}",
            description=original.description,
            comment=data.get("comment", original.comment),
            country_id=data.get("country_id", original.country_id),
            city=original.city,
            dimension=original.dimension,
            mode="custom",  # Always custom for duplicates
            public=False,  # Always private for duplicates
            draft=False,
            is_boq=False,
            created_by=request.user,
        )

        # Copy existing materials with updated data
        materials_data = data.get("materials", [])
        material_map = {m["id"]: m for m in materials_data if not str(m["id"]).startswith("new_")}

        for original_product in original.structuralproduct_set.all():
            material_data = material_map.get(str(original_product.id), {})
            StructuralProduct.objects.create(
                assembly=copy,
                epd=original_product.epd,
                classification=original_product.classification,
                description=material_data.get("description", original_product.description),
                quantity=material_data.get("quantity", original_product.quantity),
                input_unit=original_product.input_unit,
            )

        # Add new materials from EPD modal
        new_materials_data = data.get("new_materials", [])
        for new_material in new_materials_data:
            epd_id = new_material.get("epd_id")
            if epd_id:
                from pages.models.epd import EPD
                try:
                    epd = EPD.objects.get(id=epd_id)

                    # Get correct unit based on assembly dimension
                    dimension = None if copy.is_boq else copy.dimension
                    _, expected_units = epd.get_epd_info(dimension)
                    # Use first expected unit as default
                    input_unit = expected_units[0] if expected_units else epd.declared_unit

                    StructuralProduct.objects.create(
                        assembly=copy,
                        epd=epd,
                        description=new_material.get("description", ""),
                        quantity=new_material.get("quantity", 0),
                        input_unit=input_unit,
                    )
                except EPD.DoesNotExist:
                    pass

        return JsonResponse({"success": True, "message": "Template duplicated successfully", "id": str(copy.id)})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_http_methods(["DELETE"])
def delete_template(request, template_id):
    """Delete a template (owner only)."""
    assembly = get_object_or_404(Assembly, id=template_id)

    # Only owner can delete
    if assembly.created_by != request.user:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        assembly.delete()
        return JsonResponse({"success": True, "message": "Template deleted successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def search_epds(request):
    """Search EPDs for adding to templates. Reuses existing EPD filtering logic."""
    # Get filtered EPDs using existing logic
    filtered_epds, _ = get_filtered_epd_list(request, operational=False)

    # Paginate
    page = request.GET.get("page", 1)
    paginator = Paginator(filtered_epds, 10)
    epds = paginator.get_page(page)

    # Build EPD list with GWP calculations and JSON-safe data
    epd_list = []
    for epd in epds:
        gwp = 0
        try:
            gwp = epd.get_gwp_impact_sum("a1a3")
        except Exception:
            pass

        epd_data = {
            "id": str(epd.id),
            "name": epd.name,
            "country": epd.country.name if epd.country else "Unknown",
            "country_code": epd.country.code2 if epd.country else None,
            "category": epd.category.name_en if epd.category else "Unknown",
            "gwp": round(float(gwp), 2) if gwp else 0,
            "unit": epd.declared_unit,
            "type": epd.get_type_display() if epd.type else "Unknown",
        }
        epd_list.append({
            **epd_data,
            "json": json.dumps(epd_data)  # Pre-encode JSON for template
        })

    # Get search parameters for pagination
    search_query = request.GET.get("epd_search_query", "").strip()
    country = request.GET.get("country", "").strip()
    category = request.GET.get("category", "").strip()
    epd_type = request.GET.get("type", "").strip()

    context = {
        "epds": epd_list,
        "page_obj": epds,
        "search_query": search_query,
        "selected_country": country,
        "selected_category": category,
        "selected_type": epd_type,
    }

    # Return HTML partial for HTMX
    return render(request, "pages/home/partials/epd_components_list.html", context)