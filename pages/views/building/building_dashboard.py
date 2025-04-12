import pandas as pd
import logging

from plotly.offline import plot
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseServerError

from django.shortcuts import get_object_or_404

from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated, OperationalProduct, SimulatedOperationalProduct
from pages.views.building.building import get_assemblies
from pages.views.building.operational_products.operational_products import serialize_operational_products

logger = logging.getLogger(__name__)


def get_building_dashboard(user, building_id, dashboard_type: str, simulation: bool):
    if dashboard_type == "assembly":
        return building_dashboard_assembly(user, building_id, simulation)
    elif dashboard_type == "material":
        return building_dashboard_material(user, building_id, simulation)
    else:
        logger.info("Dashboard type not defined", user, building_id, dashboard_type)
        return HttpResponseServerError()


def building_dashboard_material(user, building_id, simulation):
    df = prep_building_dashboard_df(user, building_id, simulation)
    return _building_dashboard_base(df, "material_category")


def building_dashboard_assembly(user, building_id, simulation):
    df = prep_building_dashboard_df(user, building_id, simulation)

    df["category_short"] = df["assembly_category"]
    df.loc[df["type"] == "structural", "category_short"] = df.loc[df["type"] == "structural", "assembly_category"].str.split("- ").str[1]
    df.loc[df["category_short"] == "Intermediate Floor Construction", "category_short"] = "Interm. Floor"
    df.loc[df["category_short"] == "Bottom Floor Construction", "category_short"] = "Bottom Floor"
    df.loc[df["category_short"] == "Roof Construction", "category_short"] = "Roof Const."
    
    # Aggregation for pie chart
    op_gwp_sum = df.loc[df["type"] == "operational", "gwp"].sum()
    op_penrt_sum = df.loc[df["type"] == "operational", "penrt"].sum()
    operational_row = {'category_short': 'Operational carbon', "gwp": op_gwp_sum, "penrt": op_penrt_sum, "type": "operational"}
    st_gwp_sum = df.loc[df["type"] == "structural", "gwp"].sum()
    st_penrt_sum = df.loc[df["type"] == "structural", "penrt"].sum()
    structural_row = {'category_short': 'Embodied carbon', "gwp": st_gwp_sum, "penrt": st_penrt_sum, "type": "structural"}
    df_list = [structural_row, operational_row]
    df_pie = pd.DataFrame(data=df_list)
    
    # Shorten df for bar chart
    df_filtered = df[df["type"] == "structural"]
    df_bar = (df_filtered.groupby('category_short')['gwp'].sum() / df_filtered['gwp'].sum() * 100).reset_index()
    df_bar.columns = ['category_short', 'gwp_per']
    df_bar = df_bar.sort_values("gwp_per", ascending=False)

    return _building_dashboard_assembly(df_pie, df_bar, "category_short")


def prep_building_dashboard_df(user, building_id, simulation):
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
        relation_name = "buildingassemblysimulated_set"
        BuildingProductModel = SimulatedOperationalProduct
        op_relation_name = "simulated_operational_products"
    else:
        BuildingAssemblyModel = BuildingAssembly
        relation_name = "buildingassembly_set"
        BuildingProductModel = OperationalProduct
        op_relation_name = "operational_products"

    building = get_object_or_404(
        Building.objects.filter(
            created_by=user
        ).prefetch_related(  # Ensure the building belongs to the user
            Prefetch(
                relation_name,
                queryset=BuildingAssemblyModel.objects.filter().select_related("assembly"),
                to_attr="prefetched_components",
            ),
            Prefetch(
                op_relation_name,
                queryset=BuildingProductModel.objects.all(),
                to_attr="prefetched_operational_products",
            ),
        ),
        pk=building_id,
    )

    # Build structural and operational components and impacts in one step
    structural_components, impact_list = get_assemblies(building.prefetched_components)
    operational_impact_list = serialize_operational_products(building.prefetched_operational_products)

    if not structural_components and not operational_impact_list:
        return HttpResponse()
    elif not structural_components:
        df = prep_operational_df(operational_impact_list)
    elif not operational_impact_list:
        df = prep_structural_df(impact_list)
    elif operational_impact_list and structural_components:
        
        df = prep_structural_df(impact_list)
    
        # operational df
        df_op = prep_operational_df(operational_impact_list)

        df = pd.concat([df, df_op], axis=0)[["assembly_category", "material_category", "gwp", "penrt", "type"]]
    return df

def prep_structural_df(impact_list):
    df = pd.DataFrame.from_records(impact_list)
    df["impact_type"] = df["impact_type"].apply(lambda x: x.__str__())
    df["assembly_category"] = df["assembly_category"].apply(lambda x: x.__str__())
    df["material_category"] = df["material_category"].apply(lambda x: x.__str__())
    df = df[df["impact_type"].isin(["gwp a1a3", "penrt a1a3"])]
    df = df.pivot(
            index=["assembly_id", "epd_id", "assembly_category", "material_category"],
            columns="impact_type",
            values="impact_value",
        ).reset_index()
        
        # Decision to only display positive values for embodied carbon and embodied energy, yet indicator below still shows sum.
        # Thus creating a new column
    df["gwp a1a3 pos"] = df["gwp a1a3"]
    df.loc[df["gwp a1a3 pos"] <= 0, "gwp a1a3 pos"] = 0
    df["penrt a1a3 pos"] = df["penrt a1a3"]
    df.loc[df["penrt a1a3 pos"] <= 0, "penrt a1a3 pos"] = 0
    df["type"] = "structural"
    df.rename(columns={"gwp a1a3 pos": "gwp", "penrt a1a3 pos": "penrt"}, inplace=True)
    return df

def prep_operational_df(operational_impact_list):
    df_op = pd.DataFrame.from_records(operational_impact_list)
    df_op["material_category"] = df_op["category"].apply(lambda x: x.__str__())
    df_op["type"] = "operational"
    df_op["assembly_category"] = "Operational Carbon"
    df_op.rename(columns={"gwp_b6": "gwp", "penrt_b6": "penrt"}, inplace=True)
    return df_op


def _building_dashboard_assembly(df_pie, df_bar, key_column: str):
    # Preset colors
    colors = ["rgb(244, 132, 67)", "rgb(150, 150, 150)"]

    # Create a 2x2 layout: top row for pie and bar, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "domain"}, {"type": "xy"}],
            [{"type": "domain"}, {"type": "domain"}],
        ],
        subplot_titles=[
            "<b>Whole life cycle carbon</b><br>[kg CO₂eq/m·yr]<br> ",
            "<b>Embodied carbon</b><br>[kg CO₂eq/m·yr]<br> ",
            "",
            "",
        ],
        # Give more vertical space to top row
        row_heights=[0.6, 0.3],
        vertical_spacing=0.05,
    )

    # Update all annotations (including subplot titles)
    for annotation in fig["layout"]["annotations"]:
        annotation["font"] = dict(size=20)  

    # Add pies
    fig.add_trace(
        go.Pie(
            labels=df_pie[key_column],
            values=df_pie["gwp"],  # using only positive values
            name="GWP",
            hole=0.4,
            marker=dict(colors=colors),
            legendgroup="GWP",
            showlegend=True,
        ),
        row=1,
        col=1,
    )

    # Stacking 2 bars on top of each other to have text appear behind graphs
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=df_bar["gwp_per"],
            orientation='h',
            texttemplate='%{label} - %{value:.0f}%',
            textposition='inside',
            insidetextanchor='start',
            textangle=0,  
            textfont_size=20,
            textfont=dict(color='black'),
            marker_opacity=0.4,  
            showlegend=False,
            hoverinfo="y+x",
            hovertemplate="%{label}<br><b>Value: %{value:.2f}</b>%<extra></extra>",
        ),
        row=1,
        col=2,
    )
    
    # Second bar graph
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=df_bar["gwp_per"],
            orientation='h',
            marker_opacity=0.75, 
            showlegend=False,
            hoverinfo="y+x",
            hovertemplate="%{label}<br><b>Value: %{value:.2f}</b>%<extra></extra>",
        ),
        row=1,
        col=2,
    )
    

    # Update pies formatting
    fig.update_traces(
        hoverinfo="label+value",
        hovertemplate="%{label}<br><b>Value: %{value:.2f}</b><extra></extra>",
        hoverlabel=dict(font_color="white", namelength=-1),
        textposition="auto",
        textfont=dict(
            size=14, 
            family="Arial, sans-serif",  
            color="white",
        ),
        texttemplate="<b>%{label}</b><br>%{percent:.0%}",
        selector=dict(type="pie"),
    )
    
    # Update bar formatting
    fig.update_traces(
        marker_color=colors[0], 
        marker_cornerradius=15,
        hoverlabel_font_color="white", 
        hoverlabel_namelength=-1,
        selector=dict(type='bar')
    )
    
    fig.update_yaxes(autorange='reversed')

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',  
        plot_bgcolor='rgba(0,0,0,0)',
        bargap=0.05,
        bargroupgap=0.5,
        uniformtext=dict(mode='show', minsize=12),
        yaxis=dict(showticklabels=False),
        barmode='overlay'
    )

    # Calculate initial sums
    gwp_sum = df_pie["gwp"].sum()
    gwp_embodied_sum = df_pie.loc[df_pie["type"] == "structural", "gwp"].sum()

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
            value=gwp_embodied_sum,
            title={"text": "<b>Total embodied GWP</b>", "font": {"size": 20}},
            number={"font": {"size": 30}},
        ),
        row=2,
        col=2,
    )

    # Increase figure size and reduce margins
    fig.update_layout(
        height=500, width=900, margin=dict(l=50, r=50, t=100, b=50), showlegend=True
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot



def _building_dashboard_base(df, key_column: str):
    
    # Generate colors & correct ordering
    df_sorted, color_list = _get_color_ordering(df, "carbon")

    # Create a 2x2 layout: top row for pies, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "domain"}, {"type": "domain"}],
            [{"type": "domain"}, {"type": "domain"}],
        ],
        subplot_titles=[
            "<b>LCA Carbon</b><br>by resource<br>[kg CO₂eq/m·yr]<br> ",
            "<b>LCA Energy</b><br>by resource<br>[MJ/m²·yr]<br> ",
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
            labels=df_sorted[key_column],
            values=df_sorted["gwp"],  
            name="GWP",
            direction ='clockwise',
            hole=0.4,
            marker=dict(colors=color_list),
            legendgroup="GWP",
            showlegend=True,
            sort=False,
        ),
        row=1,
        col=1,
    )

    # Generate colors & correct ordering
    df_sorted, color_list = _get_color_ordering(df, "energy")

    fig.add_trace(
        go.Pie(
            labels=df_sorted[key_column],
            values=df_sorted["penrt"],
            sort=False,
            direction ='clockwise',
            name="PENRT",
            hole=0.4,
            marker=dict(colors=color_list),
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
        hoverlabel=dict(font_color="white", namelength=-1),
        textposition="inside",
        textfont=dict(
            size=14,  # Default font size
            family="Arial, sans-serif",  # Use a modern sans-serif font
            color="white",  # Default high contrast text color
        ),
        texttemplate="<b>%{label}</b><br>%{percent:.0%}",
        
        # connector=dict(line=dict(color="black", width=1, dash="solid")),
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
    fig.update_layout(annotations=new_annotations, uniformtext_minsize=12, uniformtext_mode='hide')

    # Calculate initial sums
    gwp_sum = df["gwp"].sum()
    penrt_sum = df["penrt"].sum()

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
        height=500, width=900, margin=dict(l=25, r=25, t=125, b=25), showlegend=True
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot


def _get_color_ordering(df, unit):
    df_sorted = df.sort_values(["type", "gwp"], ascending=[False, False]).reset_index()
    df_struct = df_sorted[df_sorted["type"] == "structural"]
    df_op = df_sorted[df_sorted["type"] == "operational"]
    
    if unit == "carbon":  
        colorscale_struct = _generate_discrete_colors(
            start_color=(244, 132, 67), end_color=(250, 199, 165), n=df_struct.shape[0]
        )
    elif unit == "energy":
        colorscale_struct = _generate_discrete_colors(
            start_color=(36, 191, 91), end_color=(154, 225, 177), n=df_struct.shape[0]
        )
        
    colorscale_op = _generate_discrete_colors(
        start_color=(150, 150, 150), end_color=(180, 180, 180), n=df_op.shape[0]
    )
    
    index_struct = df_sorted[df_sorted['type'] == 'structural'].index.tolist()
    index_op = df_sorted[df_sorted['type'] == 'operational'].index.tolist()
    final_size = max(max(index_struct), max(index_op)) + 1
    color_list = [None] * final_size

    for pos, rgb in zip(index_struct, colorscale_struct):
        color_list[pos] = rgb

    # Place the values from the second rgb list
    for pos, rgb in zip(index_op, colorscale_op):
        color_list[pos] = rgb
        
    return df_sorted, color_list


def _generate_discrete_colors(
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
