import logging

from django.db.models import Prefetch, Q
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
import pandas as pd
from plotly.offline import plot
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pages.forms.building_general_info import BuildingGeneralInformation
from pages.models.building import Building, BuildingAssembly
from pages.models.assembly import Assembly, AssemblyImpact

logger = logging.getLogger(__name__)


def plotly_graph(structural_components):
    # Prepare DataFrame
    rows = []
    for assembly in structural_components:
        row = {
            "assemblybuilding_id": assembly["assemblybuilding_id"],
            "assembly_name": assembly["assembly_name"],
        }
        for impact in assembly["impacts"]:
            row[impact["impact_name"]] = impact["value"]
        rows.append(row)
    df = pd.DataFrame(rows)

    # Generate colors
    colorscale_orange = generate_discrete_colors(
        start_color=(242, 103, 22), end_color=(250, 199, 165), n=df.shape[0]
    )

    colorscale_green = generate_discrete_colors(
        start_color=(36, 191, 91), end_color=(154, 225, 177), n=df.shape[0]
    )

    # Create a 2x2 layout: top row for pies, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "domain"}, {"type": "domain"}],
            [{"type": "domain"}, {"type": "domain"}],
        ],
        subplot_titles=[
            "<b>Embodied Carbon</b><br>[kg CO2eq/m²/a]<br> ",
            "<b>Embodied Energy</b><br>[MJ/m²/a]<br> ",
            "",
            "",
        ],
        # Give more vertical space to top row
        row_heights=[0.6, 0.3],
        vertical_spacing=0.05,
    )

    # Update all annotations (including subplot titles)
    for annotation in fig["layout"]["annotations"]:
        annotation["font"] = dict(size=20)  # Change 20 to your desired font size

    # Add pies
    fig.add_trace(
        go.Pie(
            labels=df["assembly_name"],
            values=df["gwp a1a3"],
            name="GWP A1A3",
            hole=0.4,
            marker=dict(colors=colorscale_orange),
            legendgroup="GWP",
            showlegend=True,
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Pie(
            labels=df["assembly_name"],
            values=df["penrt a1a3"],
            name="PENRT A1A3",
            hole=0.4,
            marker=dict(colors=colorscale_green),
            legendgroup="PENRT",
            showlegend=True,
        ),
        row=1,
        col=2,
    )

    # Update pies formatting
    fig.update_traces(
        hoverinfo="label+value",
        hovertemplate="%{label}<br><b>Value: %{value:.2f}</b><extra></extra>",
        textinfo='label+percent',  # Show assembly names, values, and percentages
        hoverlabel=dict(font_color="white"),
        textfont=dict(
            size=14,        # Increase text size
            family="Arial, sans-serif",  # Use a modern sans-serif font
            color='white'   # Default high contrast text color
        ),
        texttemplate="<b>%{label}</b><br>%{percent:.0%}"
    )

    # Store existing annotations (subplot titles)
    existing_annotations = list(fig.layout.annotations)

    # Calculate centers for pie hole annotations
    first_pie_domain = fig.data[0].domain
    second_pie_domain = fig.data[1].domain

    gwp_annotation = dict(
        text="GWP",
        x=(first_pie_domain.x[0] + first_pie_domain.x[1]) / 2,
        y=(first_pie_domain.y[0] + first_pie_domain.y[1]) / 2,
        font_size=20,
        showarrow=False,
        xanchor="center",
        yanchor="middle",
    )

    penrt_annotation = dict(
        text="PENRT",
        x=(second_pie_domain.x[0] + second_pie_domain.x[1]) / 2,
        y=(second_pie_domain.y[0] + second_pie_domain.y[1]) / 2,
        font_size=20,
        showarrow=False,
        xanchor="center",
        yanchor="middle",
    )

    # Combine original titles + new annotations
    new_annotations = existing_annotations + [gwp_annotation, penrt_annotation]
    fig.update_layout(annotations=new_annotations)

    # Calculate initial sums
    gwp_sum = df["gwp a1a3"].sum()
    penrt_sum = df["penrt a1a3"].sum()

    # Add Indicators (make them larger)
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_sum,
            title={"text": "<b>Total GWP</b>", "font": {"size": 20}},
            number={"font": {"size": 30}},
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=penrt_sum,
            title={"text": "<b>Total PENRT</b>", "font": {"size": 20}},
            number={"font": {"size": 30}},
        ),
        row=2,
        col=2,
    )

    # Increase figure size and reduce margins
    fig.update_layout(
        height=500, width=900, margin=dict(l=50, r=50, t=100, b=50), showlegend=True
    )

    pie_plot = plot(fig, output_type="div")
    return pie_plot


def generate_discrete_colors(
    start_color=(242, 103, 22), end_color=(255, 247, 237), n=5
):
    """
    Generate a list of n discrete colors evenly spaced between start_color and end_color.

    Parameters
    ----------
    start_color : tuple
        A tuple of (R, G, B) for the start color. Each channel should be 0-255.
    end_color : tuple
        A tuple of (R, G, B) for the end color. Each channel should be 0-255.
    n : int
        Number of discrete colors to generate.

    Returns
    -------
    list of str
        A list of n RGB color strings in the format 'rgb(R,G,B)'.
    """
    colors = []
    for i in range(n):
        # Determine fraction along the gradient
        fraction = i / (n - 1) if n > 1 else 0

        # Interpolate each channel
        r = int(start_color[0] + fraction * (end_color[0] - start_color[0]))
        g = int(start_color[1] + fraction * (end_color[1] - start_color[1]))
        b = int(start_color[2] + fraction * (end_color[2] - start_color[2]))

        colors.append(f"rgb({r},{g},{b})")
    return colors


@require_http_methods(["GET", "POST", "DELETE"])
def building(request, building_id):
    print("request user", request.user)
    # General Info
    if request.method == "POST" and request.POST.get("action") == "general_information":
        form = BuildingGeneralInformation(
            request.POST, instance=building
        )  # Bind form to instance
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
        updated_list = BuildingAssembly.objects.filter(
            building__created_by=request.user,
            assembly__created_by=request.user,
            building_id=building_id,
        ).select_related(
            "assembly"
        )  # Optimize query by preloading related Assembly
        structural_components = []
        for component in updated_list:
            impacts = [
                {
                    "impact_id": impact.impact.id,
                    "impact_name": impact.impact.name,
                    "value": impact.value,
                }
                for impact in component.assembly.assemblyimpact_set.all()
            ]

            structural_components.append(
                {
                    "assemblybuilding_id": component.id,
                    "assembly_name": component.assembly.name,
                    "assembly_classification": component.assembly.classification,
                    "quantity": component.quantity,
                    "unit": component.unit,
                    "impacts": impacts,
                }
            )
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
            Building.objects.filter(
                created_by=request.user
            ).prefetch_related(  # Ensure the building belongs to the user
                Prefetch(
                    "buildingassembly_set",
                    queryset=BuildingAssembly.objects.filter(
                        # assembly__created_by=request.user  # Ensure the assembly belongs to the user
                    )
                    .select_related("assembly")
                    .prefetch_related(
                        Prefetch(
                            "assembly__assemblyimpact_set",
                            queryset=AssemblyImpact.objects.select_related("impact"),
                        )
                    ),
                    to_attr="prefetched_components",
                )
            ),
            pk=building_id,
        )

        # Build structural components and impacts in one step
        structural_components = []
        for component in building.prefetched_components:
            impacts = [
                {
                    "impact_id": impact.impact.id,
                    "impact_name": impact.impact.__str__(),
                    "value": impact.value,
                }
                for impact in component.assembly.assemblyimpact_set.all()
            ]

            structural_components.append(
                {
                    "assemblybuilding_id": component.id,
                    "assembly_name": component.assembly.name,
                    "assembly_classification": component.assembly.classification,
                    "quantity": component.quantity,
                    "unit": component.unit,
                    "impacts": impacts,
                }
            )

        context = {
            "building_id": building.id,
            "building": building,
            "structural_components": list(structural_components),
            "dashboard": plotly_graph(structural_components),
        }

        logger.info(
            "Found building: %s with %d structural components",
            building.name,
            len(context["structural_components"]),
        )
        form = BuildingGeneralInformation(instance=building)

    context["form_general_info"] = form
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
