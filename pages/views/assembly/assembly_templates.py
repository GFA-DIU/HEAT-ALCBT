from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.models.assembly import Assembly
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.forms.assembly_template_filter_form import AssemblyTemplateFilterForm
from pages.views.assembly.assembly_template_filtering import get_filtered_assembly_templates
from pages.views.assembly.assembly_template_processing import get_paginated_templates
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def assembly_templates_list(request, building_id):
    """
    View to display available assembly templates for selection.
    Shows user's own templates and generic templates with filtering support.
    """
    building = get_object_or_404(Building, pk=building_id)
    simulation = request.GET.get("simulation") == "True"
    
    # Handle filter requests or pagination
    if (
        request.method == "POST" 
        and request.POST.get("action") == "filter"
    ):
        # Get filtered templates with pagination
        user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)
        
        # Process templates using the LazyProcessor for proper data handling
        from pages.views.assembly.assembly_template_processing import AssemblyTemplateLazyProcessor
        from itertools import chain
        
        # Convert querysets to lists and combine
        all_templates_queryset = list(chain(user_templates, generic_templates))
        
        # Use the LazyProcessor to handle data processing
        lazy_processor = AssemblyTemplateLazyProcessor(all_templates_queryset)
        
        # Get page number from POST data or default to 1
        page_number = request.POST.get('page', request.GET.get('page', 1))
        
        # Apply pagination to processed templates
        from django.core.paginator import Paginator
        paginator = Paginator(lazy_processor, 10)
        user_templates_page = paginator.get_page(page_number)
        
        context = {
            'building_id': building_id,
            'building': building,
            'user_templates': user_templates_page,
            'simulation': simulation,
        }
        return render(request, 'pages/assembly/template_cards.html', context)
    
    # Get all templates for full page load with pagination
    user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)
    
    # Process templates using the LazyProcessor for proper data handling
    from pages.views.assembly.assembly_template_processing import AssemblyTemplateLazyProcessor
    from itertools import chain
    
    # Convert querysets to lists and combine
    all_templates_queryset = list(chain(user_templates, generic_templates))
    
    # Use the LazyProcessor to handle data processing
    lazy_processor = AssemblyTemplateLazyProcessor(all_templates_queryset)
    
    # Get page number
    page_number = request.GET.get('page', 1)
    
    # Apply pagination to processed templates
    from django.core.paginator import Paginator
    paginator = Paginator(lazy_processor, 10)
    user_templates_page = paginator.get_page(page_number)
    
    # Create filter form
    req = request.POST if request.method == "POST" else request.GET
    template_filters_form = AssemblyTemplateFilterForm(req)
    
    context = {
        'building_id': building_id,
        'building': building,
        'user_templates': user_templates_page,
        'simulation': simulation,
        'template_filters_form': template_filters_form,
        'filters': req,
    }
    
    return render(request, 'pages/assembly/templates_list.html', context)


@login_required
@require_http_methods(["POST"])
def copy_template(request, building_id, template_id):
    """
    Copy a template assembly, add it to the building, and redirect to component editor.
    """
    building = get_object_or_404(Building, pk=building_id)
    template = get_object_or_404(Assembly, pk=template_id, is_template=True)
    simulation = request.POST.get("simulation") == "True"
    
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly
    
    try:
        # Get quantity from form or use default
        quantity = float(request.POST.get('quantity', 1.0))
        
        # Create copy of template
        new_assembly = template.copy_as_template_instance(
            new_name=template.name,
            user=request.user
        )
        
        # Add the new assembly to the building with default reporting_life_cycle of 50
        building_assembly = BuildingAssemblyModel.objects.create(
            building=building,
            assembly=new_assembly,
            quantity=quantity,
            reporting_life_cycle=50,  # Default value as per CLAUDE.md instructions
        )
        
        logger.info(
            "Template copied and added to building - User: %s, Template: %s, New Assembly: %s, Building: %s",
            request.user,
            template,
            new_assembly,
            building
        )
        
        # Return JSON response for HTMX redirect to component editor with the new assembly
        response = JsonResponse({"message": "Template added to building successfully"})
        redirect_url = reverse(
            "component_edit", 
            kwargs={"assembly_id": new_assembly.id, "building_id": building.pk}
        )
        
        # Add simulation parameter
        redirect_url += f"?simulation={simulation}&from_template=true"
        response["HX-Redirect"] = redirect_url
        
        return response
        
    except Exception as e:
        import traceback
        logger.error(
            "Error copying template - User: %s, Template: %s, Building: %s, Error: %s, Traceback: %s",
            request.user,
            template,
            building,
            str(e),
            traceback.format_exc()
        )
        return JsonResponse({"error": f"Failed to copy template: {str(e)}"}, status=400)