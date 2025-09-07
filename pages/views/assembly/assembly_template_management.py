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
    """
    Dedicated view for managing assembly templates.
    Provides CRUD operations for user's templates.
    """
    # Handle filter requests
    if request.method == "POST" and request.POST.get("action") == "filter":
        # Get filtered templates
        user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)
        
        # Add pagination with LazyProcessor
        page_number = request.POST.get('page', request.GET.get('page', 1))
        try:
            page_obj = get_paginated_templates(user_templates, page_number, 12)
        except Exception as e:
            logger.error(f"Pagination error: {str(e)}")
            # Fallback to regular pagination
            from django.core.paginator import Paginator
            paginator = Paginator(user_templates, 12)
            page_obj = paginator.get_page(page_number)
        
        # Create filter form to preserve state
        template_filters_form = AssemblyTemplateFilterForm(request.POST)
        
        context = {
            'user_templates': page_obj,
            'generic_templates': generic_templates[:6],  # Show first 6 generic templates
            'template_filters_form': template_filters_form,
            'is_management_view': True,  # Flag for conditional dropdowns
        }
        return render(request, 'pages/assembly/management_template_cards.html', context)
    
    # Get all user templates for full page load
    user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)
    
    # Add pagination with LazyProcessor
    page_number = request.GET.get('page', 1)
    page_obj = get_paginated_templates(user_templates, page_number, 12)
    
    # Create filter form
    req = request.POST if request.method == "POST" else request.GET
    template_filters_form = AssemblyTemplateFilterForm(req)
    
    context = {
        'user_templates': page_obj,
        'generic_templates': generic_templates[:6],  # Show first 6 generic templates
        'template_filters_form': template_filters_form,
        'filters': req,
    }
    
    return render(request, 'pages/assembly/template_management.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_template_status(request, assembly_id):
    """
    Toggle the template status of an assembly.
    """
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
    """
    Delete an assembly template.
    Only allows deletion if it's not used in any buildings or if user confirms.
    """
    assembly = get_object_or_404(Assembly, pk=assembly_id, created_by=request.user, is_template=True)
    
    try:
        # Check if template is being used in any buildings
        building_usage_count = assembly.buildingassembly_set.count() + assembly.buildingassemblysimulated_set.count()
        
        force_delete = request.POST.get('force_delete', 'false') == 'true'
        
        if building_usage_count > 0 and not force_delete:
            return JsonResponse({
                "warning": True,
                "message": f"This template is used in {building_usage_count} building(s). Are you sure you want to delete it?",
                "usage_count": building_usage_count
            })
        
        # Delete the template
        template_name = assembly.name
        with transaction.atomic():
            # If force delete, we need to handle the building assemblies
            if force_delete and building_usage_count > 0:
                # Convert building assemblies to regular assemblies (remove template relationship)
                for building_assembly in assembly.buildingassembly_set.all():
                    # Create a copy of the template for each building usage
                    new_assembly = assembly.copy_as_template_instance(
                        new_name=assembly.name,
                        user=request.user
                    )
                    building_assembly.assembly = new_assembly
                    building_assembly.save()
                
                for building_assembly_sim in assembly.buildingassemblysimulated_set.all():
                    new_assembly = assembly.copy_as_template_instance(
                        new_name=assembly.name,
                        user=request.user
                    )
                    building_assembly_sim.assembly = new_assembly
                    building_assembly_sim.save()
            
            assembly.delete()
        
        messages.success(request, f"Template '{template_name}' deleted successfully")
        return JsonResponse({"message": f"Template '{template_name}' deleted successfully"})
        
    except Exception as e:
        logger.error(f"Error deleting template {assembly_id}: {str(e)}")
        return JsonResponse({"error": f"Failed to delete template: {str(e)}"}, status=400)


@login_required
@require_http_methods(["POST"])
def duplicate_template(request, assembly_id):
    """
    Create a duplicate of a template.
    """
    original_template = get_object_or_404(Assembly, pk=assembly_id, is_template=True)
    
    try:
        # Create a copy with a new name
        new_name = request.POST.get('new_name', f"{original_template.name} (Copy)")
        
        new_template = original_template.copy_as_template_instance(
            new_name=new_name,
            user=request.user
        )
        
        # Make the copy a template as well
        new_template.is_template = True
        new_template.save()
        
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