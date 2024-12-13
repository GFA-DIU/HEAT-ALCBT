import logging

from django.db.models import Prefetch, Q
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
import pandas as pd
from plotly.offline import plot
import plotly.express as px

from pages.forms.building_general_info import BuildingGeneralInformation
from pages.models.building import Building, BuildingAssembly
from pages.models.assembly import Assembly, AssemblyImpact

logger = logging.getLogger(__name__)

def plotly_graph(structural_components):
    
    rows = []
    for assembly in structural_components:
        row = {
            'assemblybuilding_id': assembly['assemblybuilding_id'],
            'assembly_name': assembly['assembly_name']
        }
        # Add each impact as a column
        for impact in assembly['impacts']:
            row[impact['impact_name']] = impact['value']
        rows.append(row)

    df = pd.DataFrame(rows)
    gwp_a1a3_df = df[["assembly_name", "gwp a1a3"]]
    
    print(gwp_a1a3_df.shape[0])
    
    colorscale = generate_discrete_colorscale(
        start_color=(242,103,22),  # Orange = #F26716
        end_color=(255,247,237), # Light-Orange = #FFF7ED
        n=gwp_a1a3_df.shape[0])
    print(colorscale)
    colorscale = ["rgb(242,103,22)", "rgb(255,247,237)"]
    
    fig = px.pie(gwp_a1a3_df, names='assembly_name', values='gwp a1a3', 
                    title='Sample Pie Chart', 
                    hole=0.5,
                    color="gwp a1a3")
                 #["#F26716", "#F28749"])
    pie_plot = plot(fig, output_type="div")
    return pie_plot

def generate_discrete_colorscale(start_color=(242, 103, 22), end_color=(242, 135, 73), n=9):
    """
    Generate a discrete colorscale from start_color to end_color with n discrete steps.
    Each discrete color is represented twice in the scale so there's no interpolation 
    between them in Plotly's rendering. The scale starts at 0 and ends at 1.

    Parameters
    ----------
    start_color : tuple of int
        Starting color as (R, G, B).
    end_color : tuple of int
        Ending color as (R, G, B).
    n : int
        Number of discrete colors (including start and end).

    Returns
    -------
    list of [float, str]
        Discrete colorscale in the format:
        [
          [0.000, 'rgb(...)'],
          [0.XXX, 'rgb(...)'],
          [0.XXX, 'rgb(...)'],
          ...
          [1.000, 'rgb(...)']
        ]
    """
    # Interpolate colors linearly between start and end
    colors = []
    for i in range(n):
        fraction = i / (n - 1) if n > 1 else 0
        r = int(round(start_color[0] + fraction * (end_color[0] - start_color[0])))
        g = int(round(start_color[1] + fraction * (end_color[1] - start_color[1])))
        b = int(round(start_color[2] + fraction * (end_color[2] - start_color[2])))
        colors.append((r, g, b))
    
    colorscale = []
    # For each discrete color, create two stops to form a "box"
    for i, (r, g, b) in enumerate(colors):
        frac_start = round(i / n, 3)
        frac_end = round((i + 1) / n, 3)
        # Add the two entries for this discrete "box"
        colorscale.append([frac_start, f"rgb({r},{g},{b})"])
        colorscale.append([frac_end, f"rgb({r},{g},{b})"])

    return colorscale


@require_http_methods(["GET", "POST", "DELETE"])
def building(request, building_id):
    print("request user", request.user)
    # General Info
    if request.method == "POST" and request.POST.get('action') == "general_information":
        form = BuildingGeneralInformation(request.POST, instance=building)  # Bind form to instance
        if form.is_valid():
            print("these fields changed", form.changed_data)
            updated_building = form.save()
            print("Building updated in DB:", updated_building)
        else:
            print("Form is invalid")
            print("Errors:", form.errors)

    elif request.method == "DELETE":
        component_id = request.GET.get("component")
        # component = get_object_or_404(BuildingAssembly, id=item_to_delete)
        # component.delete()
        # context["structural_components"] = [c for c in structural_components if str(c["assembly_id"]) != item_to_delete]
        # print("context: ", context)
        # Get the component and delete it
        component = get_object_or_404(BuildingAssembly, id=component_id)
        component.delete()

        # Fetch the updated list of assemblies for the building
        updated_list = (
            BuildingAssembly.objects.filter(
                building__created_by=request.user,
                assembly__created_by=request.user,
                building_id=building_id
            ).select_related('assembly')  # Optimize query by preloading related Assembly
        )
        structural_components = []
        for component in updated_list:
            impacts = [
                {
                    'impact_id': impact.impact.id,
                    'impact_name': impact.impact.name,
                    'value': impact.value
                }
                for impact in component.assembly.assemblyimpact_set.all()
            ]

            structural_components.append({
                'assemblybuilding_id': component.id,
                'assembly_name': component.assembly.name,
                'assembly_classification': component.assembly.classification,
                'quantity': component.quantity,
                'unit': component.unit,
                'impacts': impacts
            })
        context = {
        "building_id": building_id,
        "structural_components": list(structural_components),
        }
        return render(
            request, "pages/building/structural_info/assemblies_list.html", context
        )  # Partial update for DELETE

    # Full reload
    else:
        building = get_object_or_404(
            Building.objects.filter(created_by=request.user)  # Ensure the building belongs to the user
            .prefetch_related(
                Prefetch(
                    'buildingassembly_set',
                    queryset=BuildingAssembly.objects.filter(
                        # assembly__created_by=request.user  # Ensure the assembly belongs to the user
                    ).select_related('assembly').prefetch_related(
                        Prefetch(
                            'assembly__assemblyimpact_set',
                            queryset=AssemblyImpact.objects.select_related('impact')
                        )
                    ),
                    to_attr='prefetched_components'
                )
            ),
            pk=building_id
        )

        # Build structural components and impacts in one step
        structural_components = []
        for component in building.prefetched_components:
            impacts = [
                {
                    'impact_id': impact.impact.id,
                    'impact_name': impact.impact.__str__(),
                    'value': impact.value
                }
                for impact in component.assembly.assemblyimpact_set.all()
            ]

            structural_components.append({
                'assemblybuilding_id': component.id,
                'assembly_name': component.assembly.name,
                'assembly_classification': component.assembly.classification,
                'quantity': component.quantity,
                'unit': component.unit,
                'impacts': impacts
            })




        context = {
            "building_id": building.id,
            "building": building,
            "structural_components": list(structural_components),
            "dashboard": plotly_graph(structural_components),
        }
        
        
        
        logger.info("Found building: %s with %d structural components", building.name, len(context["structural_components"])) 
        form = BuildingGeneralInformation(instance=building)

    context["form_general_info"] = form
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
