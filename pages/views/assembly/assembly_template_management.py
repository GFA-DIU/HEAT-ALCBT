from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction

from pages.models.assembly import Assembly
from pages.forms.assembly_template_filter_form import AssemblyTemplateFilterForm
from pages.views.assembly.assembly_template_filtering import get_filtered_assembly_templates
from pages.views.assembly.assembly_template_processing import get_paginated_templates
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def assembly_template_management(request):
    # Provides CRUD operations for user's templates.
    # Handle filter requests
    if request.method == "POST" and request.POST.get("action") == "filter":
        user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)

        from pages.views.assembly.assembly_template_processing import AssemblyTemplateLazyProcessor
        from itertools import chain

        all_templates_queryset = list(chain(user_templates, generic_templates))

        lazy_processor = AssemblyTemplateLazyProcessor(all_templates_queryset)

        page_number = request.POST.get('page', request.GET.get('page', 1))
        try:
            from django.core.paginator import Paginator
            paginator = Paginator(lazy_processor, 12)
            page_obj = paginator.get_page(page_number)
        except Exception as e:
            logger.error(f"Pagination error: {str(e)}")
            from django.core.paginator import Paginator
            paginator = Paginator(lazy_processor, 12)
            page_obj = paginator.get_page(page_number)

        template_filters_form = AssemblyTemplateFilterForm(request.POST)
        
        context = {
            'user_templates': page_obj,
            'template_filters_form': template_filters_form,
            'is_management_view': True,
        }
        return render(request, 'pages/assembly/management_template_cards.html', context)

    user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)

    from pages.views.assembly.assembly_template_processing import AssemblyTemplateLazyProcessor
    from itertools import chain

    all_templates_queryset = list(chain(user_templates, generic_templates))
    

    lazy_processor = AssemblyTemplateLazyProcessor(all_templates_queryset)

    page_number = request.GET.get('page', 1)
    from django.core.paginator import Paginator
    paginator = Paginator(lazy_processor, 12)
    page_obj = paginator.get_page(page_number)

    req = request.POST if request.method == "POST" else request.GET
    template_filters_form = AssemblyTemplateFilterForm(req)
    
    context = {
        'user_templates': page_obj,
        'template_filters_form': template_filters_form,
        'filters': req,
    }
    
    return render(request, 'pages/assembly/template_management.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_template_status(request, assembly_id):

    assembly = get_object_or_404(Assembly, pk=assembly_id, created_by=request.user)
    
    try:
        assembly.is_template = not assembly.is_template
        assembly.save()
        
        status = "enabled" if assembly.is_template else "disabled"
        messages.success(request, f"Template status {status} for '{assembly.name}'")
        
        return JsonResponse({
            "message": f"Template status {status}",
            "is_template": assembly.is_template
        })
        
    except Exception as e:
        logger.error(f"Error toggling template status for assembly {assembly_id}: {str(e)}")
        return JsonResponse({"error": f"Failed to update template status: {str(e)}"}, status=400)


@login_required
@require_http_methods(["POST"])
def delete_template(request, assembly_id):
    # Since templates are used by copying them, deletion should not affect existing building assemblies.
    assembly = get_object_or_404(Assembly, pk=assembly_id, created_by=request.user, is_template=True)

    try:
        template_name = assembly.name
        with transaction.atomic():
            assembly.delete()

        messages.success(request, f"Template '{template_name}' deleted successfully")
        return JsonResponse({"message": f"Template '{template_name}' deleted successfully"})

    except Exception as e:
        logger.error(f"Error deleting template {assembly_id}: {str(e)}")
        return JsonResponse({"error": f"Failed to delete template: {str(e)}"}, status=400)


@login_required
@require_http_methods(["POST"])
def duplicate_template(request, assembly_id):
    original_template = get_object_or_404(Assembly, pk=assembly_id, is_template=True)
    
    try:
        # Create a copy with a new name
        new_name = request.POST.get('new_name', f"{original_template.name} (Copy)")

        new_template = original_template.create_template_copy(
            template_name=new_name,
            user=request.user
        )
        
        messages.success(request, f"Template duplicated as '{new_name}'")
        return JsonResponse({
            "message": f"Template duplicated as '{new_name}'",
            "new_template_id": new_template.id
        })
        
    except Exception as e:
        logger.error(f"Error duplicating template {assembly_id}: {str(e)}")
        return JsonResponse({"error": f"Failed to duplicate template: {str(e)}"}, status=400)


@login_required
@require_http_methods(["GET"])
def convert_assembly_to_template(request, assembly_id):
    """
    Convert a regular assembly to a template.
    """
    assembly = get_object_or_404(Assembly, pk=assembly_id, created_by=request.user)
    
    if assembly.is_template:
        messages.info(request, f"'{assembly.name}' is already a template")
        return redirect('assembly_template_management')
    
    try:
        assembly.is_template = True
        assembly.save()
        
        messages.success(request, f"'{assembly.name}' converted to template successfully")
        return redirect('assembly_template_management')
        
    except Exception as e:
        logger.error(f"Error converting assembly {assembly_id} to template: {str(e)}")
        messages.error(request, f"Failed to convert assembly to template: {str(e)}")
        return redirect('assembly_template_management')