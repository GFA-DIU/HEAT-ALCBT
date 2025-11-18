import logging
import traceback
from itertools import chain

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.models.assembly import Assembly
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.forms.assembly_template_filter_form import AssemblyTemplateFilterForm
from pages.views.assembly.assembly_template_filtering import get_filtered_assembly_templates
from pages.views.assembly.assembly_template_processing import get_paginated_templates, AssemblyTemplateLazyProcessor

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
        
        # Convert querysets to lists and combine
        all_templates_queryset = list(chain(user_templates, generic_templates))
        
        # Use the LazyProcessor to handle data processing
        lazy_processor = AssemblyTemplateLazyProcessor(all_templates_queryset)
        
        # Get page number from POST data or default to 1
        page_number = request.POST.get('page', request.GET.get('page', 1))
        
        # Apply pagination to processed templates
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
    
    # Convert querysets to lists and combine
    all_templates_queryset = list(chain(user_templates, generic_templates))
    
    # Use the LazyProcessor to handle data processing
    lazy_processor = AssemblyTemplateLazyProcessor(all_templates_queryset)
    
    # Get page number
    page_number = request.GET.get('page', 1)
    
    # Apply pagination to processed templates
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
    Redirect to component editor with template data for user to modify before saving.
    """
    building = get_object_or_404(Building, pk=building_id)
    template = get_object_or_404(Assembly, pk=template_id, is_template=True)
    simulation = request.POST.get("simulation") == "True"

    try:
        logger.info(
            "Redirecting to component editor with template - User: %s, Template: %s, Building: %s",
            request.user,
            template,
            building
        )

        # Return JSON response for HTMX redirect to component editor for new component creation
        response = JsonResponse({"message": "Opening component editor with template"})
        redirect_url = reverse(
            "component",
            kwargs={"building_id": building.pk}
        )

        # Add parameters for template loading
        redirect_url += f"?simulation={simulation}&template_id={template_id}"
        response["HX-Redirect"] = redirect_url

        return response

    except Exception as e:
        logger.error(
            "Error redirecting to template editor - User: %s, Template: %s, Building: %s, Error: %s, Traceback: %s",
            request.user,
            template,
            building,
            str(e),
            traceback.format_exc()
        )
        return JsonResponse({"error": f"Failed to open template: {str(e)}"}, status=400)