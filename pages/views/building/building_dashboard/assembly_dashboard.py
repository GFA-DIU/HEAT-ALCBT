import logging

from plotly.offline import plot
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import pandas as pd

from pages.views.building.building_dashboard.utility import prep_building_dashboard_df

logger = logging.getLogger(__name__)


def building_dashboard_assembly(user, building_id, simulation):
    logger.info("Starting assembly dashboard.")
    df = prep_building_dashboard_df(user, building_id, simulation)

    df["category_short"] = df["assembly_category"]
    df.loc[df["type"] == "structural", "category_short"] = (
        df.loc[df["type"] == "structural", "assembly_category"].str.split("- ").str[1]
    )
    df.loc[
        df["category_short"] == "Intermediate Floor Construction", "category_short"
    ] = "Interm. Floor"
    df.loc[df["category_short"] == "Bottom Floor Construction", "category_short"] = (
        "Bottom Floor"
    )
    df.loc[df["category_short"] == "Roof Construction", "category_short"] = (
        "Roof Const."
    )

    # Aggregation for pie chart
    op_gwp_sum = df.loc[df["type"] == "operational", "gwp"].sum()
    op_penrt_sum = df.loc[df["type"] == "operational", "penrt"].sum()
    operational_row = {
        "category_short": "Operational carbon",
        "gwp": op_gwp_sum,
        "penrt": op_penrt_sum,
        "type": "operational",
    }
    st_gwp_sum = df.loc[df["type"] == "structural", "gwp"].sum()
    st_penrt_sum = df.loc[df["type"] == "structural", "penrt"].sum()
    structural_row = {
        "category_short": "Embodied carbon",
        "gwp": st_gwp_sum,
        "penrt": st_penrt_sum,
        "type": "structural",
    }
    df_list = [structural_row, operational_row]
    df_pie = pd.DataFrame(data=df_list)

    # Shorten df for bar chart
    df_filtered = df[df["type"] == "structural"]
    df_bar = (
        df_filtered.groupby("category_short")["gwp"].sum().reset_index(name="gwp_abs")
    )
    df_bar["gwp_per"] = df_bar["gwp_abs"] / df_bar["gwp_abs"].sum() * 100
    df_bar = df_bar.sort_values("gwp_per", ascending=False)

    return _building_dashboard_assembly(df_pie, df_bar, "category_short")


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
            "<b>Whole life cycle carbon</b><br> ",
            "<b>Embodied carbon</b><br> ",
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

    # Add custom labels for legend
    df_pie["Label"] = df_pie.apply(
        lambda x: f"{x[key_column]}: {x['gwp']:.1f} kg CO₂eq/m²", axis=1
    )

    # Add pies
    fig.add_trace(
        go.Pie(
            labels=df_pie["Label"],
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
                f"{val:.1f}% - {cat}"
                for cat, val in zip(df_bar[key_column], df_bar["gwp_per"])
            ],
            textposition="outside",
            textfont=dict(size=12, color="black"),
        ),
        row=1,
        col=2,
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
        col=2,
    )

    # 4a) Flip the y-order so your biggest bars sit at the top
    fig.update_yaxes(
        autorange="reversed",
        showticklabels=False,  # no labels on the left
        side="right",  # ticks would go on the right
        row=1,
        col=2,
    )

    # 4c) Clean up the x-axis (no grid, no numbers)
    fig.update_xaxes(
        range=[0, 100],
        automargin=True,
        showgrid=False,
        showticklabels=False,
        row=1,
        col=2,
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
        margin=dict(l=50, r=200, t=100, b=50),
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
    gwp_sum = df_pie["gwp"].sum()
    gwp_embodied_sum = df_pie.loc[df_pie["type"] == "structural", "gwp"].sum()

    # Add Indicators (make them larger)
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_sum,
            title={"text": "<b>Building carbon footprint</b>", "font": {"size": 20}},
            number={
                "font": {"size": 20, "weight": "bold"},
                "valueformat": ",.0f",
                "suffix": " kg CO₂eq/m²",
            },
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_embodied_sum,
            title={"text": "<b>Total embodied carbon</b>", "font": {"size": 20}},
            number={
                "font": {"size": 20, "weight": "bold"},
                "valueformat": ",.0f",
                "suffix": " kg CO₂eq/m²",
            },
        ),
        row=2,
        col=2,
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot
