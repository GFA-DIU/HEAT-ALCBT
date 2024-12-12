import dash
import plotly.express as px
import pandas as pd
from dash import dcc, html
from django_plotly_dash import DjangoDash

# Sample data
data = {
    'Category': ['A', 'B', 'C', 'D'],
    'Values': [10, 20, 30, 40]
}
df = pd.DataFrame(data)

# Example: Extracting data from structural_components
def extract_data_for_graph(structural_components):
    # Initialize the data structure for the graph
    data = {
        'Assembly Name': [],
        'Quantity': [],
        'Impact Name': [],
        'Impact Value': []
    }

    # Loop through each component in structural_components
    for component in structural_components:
        # For each impact in the component, extract and append the data
        for impact in component['impacts']:
            data['Assembly Name'].append(component['assembly_name'])
            data['Quantity'].append(float(component['quantity']))  # Convert Decimal to float
            data['Impact Name'].append(impact['impact_name'])
            data['Impact Value'].append(impact['value'])

    # Return as a pandas DataFrame for use in Plotly
    return pd.DataFrame(data)


app = DjangoDash('BuildingDashboard')   # replaces dash.Dash

app.layout = html.Div([
    html.H1('Simple Pie Chart'),
    dcc.Graph(
        id='pie-chart',
        figure=px.pie(df, names='Category', values='Values', title='Sample Pie Chart')
    )
])