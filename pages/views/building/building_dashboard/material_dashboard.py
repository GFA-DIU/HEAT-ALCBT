import json
import logging

from plotly.offline import plot
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pages.views.building.building_dashboard.utility import (
    _generate_discrete_colors,
    prep_building_dashboard_df,
)

logger = logging.getLogger(__name__)

with open(
    "pages/views/building/building_dashboard/material_category_mapping.json", "r"
) as f:
    material_mapping = json.load(f)


def building_dashboard_material(user, building_id, simulation):
    """
    UPDATED: Material view shows ONLY embodied carbon distributed by materials
    No operational carbon included in material view
    """
    logger.info("Starting material dashboard.")
    df = prep_building_dashboard_df(user, building_id, simulation)

    # ADDED: Filter to only structural (embodied) carbon - NO operational carbon
    df_filtered = df[df["type"] == "structural"]
    df_filtered["mapped_material_category"] = df_filtered["material_category"].apply(
        map_category
    )

    df_bar = (
        df_filtered.groupby("mapped_material_category")["gwp"]
        .sum()
        .reset_index(name="gwp_abs")
    )
    df_bar["gwp_per"] = df_bar["gwp_abs"] / df_bar["gwp_abs"].sum() * 100
    df_bar = df_bar.sort_values("gwp_per", ascending=False)

    return _building_dashboard_base(df_bar, "mapped_material_category")


def map_category(original_category):
    return (
        material_mapping[original_category]
        if original_category in material_mapping.keys()
        else "Others"
    )


def _building_dashboard_base(df_bar, key_column: str):
    # Preset colors
    colors = ["rgb(244, 132, 67)", "rgb(150, 150, 150)"]

    # Create a 1x2 layout: top row for pies, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=1,
        specs=[
            [{"type": "xy"}],
            [{"type": "domain"}],
        ],
        subplot_titles=[
            "<b>Embodied Carbon</b><br>by material<br> ",  # UPDATED: Changed from "LCA Carbon"
            "",
        ],
        # Give more vertical space to top row
        row_heights=[0.6, 0.3],
        vertical_spacing=0.05,
    )

    # Update all annotations (including subplot titles)
    for annotation in fig["layout"]["annotations"]:
        annotation["font"] = dict(size=20)

    # Stacking 2 bars on top of each other to have grey bars be behind orange bars
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=[100] * len(df_bar),
            orientation="h",
            marker=dict(
                color="rgba(200,200,200,0.3)",
                cornerradius=8,
            ),
            showlegend=False,
            hoverinfo="none",
            cliponaxis=False,
            # use the grey bars to carry the text
            text=[
                f"{cat} - {val:.1f}%"
                for cat, val in zip(df_bar[key_column], df_bar["gwp_per"])
            ],
            textposition="outside",
            textfont=dict(size=12, color="black"),
        ),
        row=1,
        col=1,
    )

    # 2) Overlay the actual % bars in orange
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=df_bar["gwp_per"],
            customdata=df_bar["gwp_abs"],
            orientation="h",
            marker=dict(
                cornerradius=8,
                color=colors[0],
            ),
            showlegend=False,
            hovertemplate="%{customdata:,.1f} kg CO₂eq/m²<extra></extra>",
            hoverlabel=dict(font=dict(color="white")),
        ),
        row=1,
        col=1,
    )

    # 4a) Flip the y-order so your biggest bars sit at the top
    fig.update_yaxes(
        autorange="reversed",
        showticklabels=False,  # no labels on the left
        side="right",  # ticks would go on the right
        row=1,
        col=1,
    )

    # 4c) Clean up the x-axis (no grid, no numbers)
    fig.update_xaxes(
        range=[0, 100],
        automargin=True,
        showgrid=False,
        showticklabels=False,
        row=1,
        col=1,
    )

    # Update pies formatting
    fig.update_traces(
        hoverinfo="label+value",
        hovertemplate="%{label}<extra></extra>",
        hoverlabel=dict(font_color="white", namelength=-1),
        textposition="auto",
        textfont=dict(
            size=14,
            family="Arial, sans-serif",
            color="white",
        ),
        texttemplate="<b>%{percent:.0%}</b>",
        selector=dict(type="pie"),
    )

    fig.update_traces(cliponaxis=False, selector=dict(type="bar"))

    fig.update_layout(
        height=500,
        width=900,
        margin=dict(l=50, r=220, t=100, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.05,
        bargroupgap=0.5,
        uniformtext=dict(mode="show", minsize=12),
        yaxis=dict(showticklabels=False),
        barmode="overlay",
        legend=dict(
            orientation="h",
            x=0.25,
            xanchor="center",
            y=0.30,
            yanchor="bottom",
            font=dict(size=14),
        ),
    )

    # Calculate initial sums
    gwp_sum = df_bar["gwp_abs"].sum()

    # Add Indicators (make them larger)
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_sum,
            title={"text": "<b>Total embodied carbon</b>", "font": {"size": 20}},
            number={
                "font": {"size": 20, "weight": "bold"},
                "valueformat": ",.0f",
                "suffix": " kg CO₂eq/m²",
            },
        ),
        row=2,
        col=1,
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot
