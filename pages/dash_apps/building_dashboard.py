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

app = DjangoDash('BuildingDashboard')   # replaces dash.Dash

app.layout = html.Div([
    html.H1('Simple Pie Chart'),
    dcc.Graph(
        id='pie-chart',
        figure=px.pie(df, names='Category', values='Values', title='Sample Pie Chart')
    )
])