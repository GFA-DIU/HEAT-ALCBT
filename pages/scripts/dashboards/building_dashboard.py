import pandas as pd
from plotly.offline import plot
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def building_dashboard(structural_components):
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
        hoverlabel=dict(font_color="white", namelength=-1),
        textfont=dict(
            size=14,        # Default font size
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
