import json
import logging

from plotly.offline import plot
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pages.views.building.building_dashboard.utility import _generate_discrete_colors, prep_building_dashboard_df

logger = logging.getLogger(__name__)

with open("pages/views/building/building_dashboard/material_category_mapping.json", "r") as f:
    material_mapping = json.load(f)


def building_dashboard_material(user, building_id, simulation):
    """
    UPDATED: Material view shows ONLY embodied carbon distributed by materials
    No operational carbon included in material view
    """
    logger.info("Starting material dashboard.")
    df = prep_building_dashboard_df(user, building_id, simulation)
    
    # ADDED: Filter to only structural (embodied) carbon - NO operational carbon
    df_embodied_only = df[df["type"] == "structural"].copy()
    
    return _building_dashboard_base(df_embodied_only, "material_category")


def map_category(original_category):
    return material_mapping[original_category] if original_category in material_mapping.keys() else "Others"


def material_categories(df):
    df['mapped_material_category'] = df['material_category'].apply(map_category)
    return df


def _get_color_ordering(df, unit):
    # UPDATED: Simplified since material view only contains structural materials now
    df_sorted = df.sort_values(["gwp"], ascending=[False]).reset_index(drop=True)
    
    # REMOVED: Separation of structural vs operational since only structural exists
    if unit == "carbon":  
        color_list = _generate_discrete_colors(
            start_color=(244, 132, 67), end_color=(250, 199, 165), n=df_sorted.shape[0]
        )
    elif unit == "energy":
        color_list = _generate_discrete_colors(
            start_color=(36, 191, 91), end_color=(154, 225, 177), n=df_sorted.shape[0]
        )
        
    return df_sorted, color_list


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
            "<b>Embodied Carbon</b><br>by material<br> ",  # UPDATED: Changed from "LCA Carbon"
            "<b>Embodied Energy</b><br>by material<br> ",  # UPDATED: Changed from "LCA Energy"
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
            title={"text": "<b>Total Embodied Carbon</b>", "font": {"size": 20}},  # UPDATED: Changed from "Total GWP"
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " kg CO₂eq/m²"},
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=penrt_sum,
            title={"text": "<b>Total Embodied Energy</b>", "font": {"size": 20}},  # UPDATED: Changed from "Total PENRT"
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " MJ/m²"},
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


def _building_dashboard_material_bar(df_bar, df_full, key_column: str):
    """
    NEW FUNCTION: Material dashboard showing ONLY bar chart for embodied carbon by materials
    Similar to assembly view but only showing bar chart, no pie chart
    """
    
    # Create a 2x1 layout: top row for bar chart, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "xy", "colspan": 2}, None],
            [{"type": "domain"}, {"type": "domain"}],
        ],
        subplot_titles=[
            "<b>Embodied carbon by material</b><br> ",
            "",
            "",
            "",
        ],
        # Give more vertical space to top row
        row_heights=[0.7, 0.25],
        vertical_spacing=0.3,
    )

    # Update all annotations (including subplot titles)
    for annotation in fig["layout"]["annotations"]:
        annotation["font"] = dict(size=20)  

    # Stacking 2 bars on top of each other to have grey bars be behind orange bars
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=[100] * len(df_bar),
            orientation='h',
            marker=dict(
                color="rgba(200,200,200,0.3)",
                cornerradius=8,
            ),
            showlegend=False,
            hoverinfo='none',
            cliponaxis=False,
            # use the grey bars to carry the text
            text=[f"{cat} - {val:.1f}%" 
                for cat,val in zip(df_bar[key_column], df_bar["gwp_per"])],
            textposition='outside',
            textfont=dict(size=12, color='black'),
        ),
        row=1, col=1
    )
    
    # 2) Overlay the actual % bars in orange
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=df_bar["gwp_per"],
            customdata=df_bar["gwp_abs"],
            orientation='h',
            marker=dict(
                cornerradius=8,
                color="rgb(244, 132, 67)",  # Orange color for embodied carbon
            ),
            showlegend=False,
            hovertemplate="%{customdata:,.1f} kg CO₂eq/m²<extra></extra>",
            hoverlabel=dict(
                font=dict(color="white")
            )
        ),
        row=1, col=1
    )
    
    # 4a) Flip the y-order so your biggest bars sit at the top
    fig.update_yaxes(autorange='reversed',
        showticklabels=False,       # no labels on the left
        side='right',               # ticks would go on the right
        row=1, col=1
        )

    # 4c) Clean up the x-axis (no grid, no numbers)
    fig.update_xaxes(
        range=[0, 100],
        automargin=True,
        showgrid=False,
        showticklabels=False,
        row=1, col=1
    )

    fig.update_traces(cliponaxis=False, selector=dict(type='bar'))
    
    fig.update_layout(
        height=500, 
        width=900,
        margin=dict(l=50, r=200, t=100, b=50),
        paper_bgcolor='rgba(0,0,0,0)',  
        plot_bgcolor='rgba(0,0,0,0)',
        bargap=0.05,
        bargroupgap=0.5,
        uniformtext=dict(mode='show', minsize=12),
        yaxis=dict(showticklabels=False),
        barmode='overlay',
    )

    # Calculate sums for indicators
    gwp_sum = df_full["gwp"].sum()
    penrt_sum = df_full["penrt"].sum()

    # Add Indicators (make them larger)
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_sum,
            title={"text": "<b>Total Embodied Carbon</b>", "font": {"size": 20}},
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " kg CO₂eq/m²"},
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=penrt_sum,
            title={"text": "<b>Total Embodied Energy</b>", "font": {"size": 20}},
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " MJ/m²"},
        ),
        row=2,
        col=2,
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot
