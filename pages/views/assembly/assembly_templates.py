from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.models.assembly import Assembly
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.forms.assembly_template_filter_form import AssemblyTemplateFilterForm
from pages.views.assembly.assembly_template_filtering import get_filtered_assembly_templates
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
    
    # Handle filter requests
    if (
        request.method == "POST" 
        and request.POST.get("action") == "filter"
    ):
        # Get filtered templates and render only the template list portion
        user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)
        
        context = {
            'building_id': building_id,
            'building': building,
            'user_templates': user_templates,
            'generic_templates': generic_templates,
            'simulation': simulation,
        }
        return render(request, 'pages/assembly/template_cards.html', context)
    
    # Get all templates for full page load
    user_templates, generic_templates = get_filtered_assembly_templates(request, request.user)
    
    # Create filter form
    req = request.POST if request.method == "POST" else request.GET
    template_filters_form = AssemblyTemplateFilterForm(req)
    
    context = {
        'building_id': building_id,
        'building': building,
        'user_templates': user_templates,
        'generic_templates': generic_templates,
        'simulation': simulation,
        'template_filters_form': template_filters_form,
        'filters': req,
    }
    
    return render(request, 'pages/assembly/templates_list.html', context)


@login_required
@require_http_methods(["POST"])
def copy_template(request, building_id, template_id):
    """
    Copy a template assembly and add it to the building.
    """
    building = get_object_or_404(Building, pk=building_id)
    template = get_object_or_404(Assembly, pk=template_id, is_template=True)
    simulation = request.POST.get("simulation") == "True"
    
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly
    
    try:
        # Get quantity and life cycle from form or use defaults
        quantity = float(request.POST.get('quantity', 1.0))
        reporting_life_cycle = int(request.POST.get('reporting_life_cycle', 50))
        
        # Create copy of template
        new_assembly = template.copy_as_template_instance(
            new_name=template.name,
            user=request.user
        )
        
        # Add the new assembly to the building
        building_assembly = BuildingAssemblyModel.objects.create(
            building=building,
            assembly=new_assembly,
            quantity=quantity,
            reporting_life_cycle=reporting_life_cycle,
        )
        
        logger.info(
            "Template copied successfully - User: %s, Template: %s, New Assembly: %s, Building: %s",
            request.user,
            template,
            new_assembly,
            building
        )
        
        # Return JSON response for HTMX redirect
        response = JsonResponse({"message": "Template copied successfully"})
        if simulation:
            response["HX-Redirect"] = reverse(
                "building_simulation", kwargs={"building_id": building.pk}
            )
        else:
            response["HX-Redirect"] = reverse(
                "building", kwargs={"building_id": building.pk}
            )
        
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