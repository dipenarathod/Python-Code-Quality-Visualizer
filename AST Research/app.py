import dash
from dash import Dash, dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc

# Initialize the app
app = Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Create navbar items from registered pages
nav_items = [dbc.NavItem(dbc.NavLink(page["name"], href=page["path"])) 
             for page in dash.page_registry.values()]

# Define the app layout
app.layout = html.Div([
    dcc.Location(id="url"),
    dbc.NavbarSimple(
        id="navbar",
        children=nav_items,  # Add navigation links automatically
        brand="GitHub Metrics Dashboard",
        color="primary",
        dark=True,
    ),
    html.Div(id="details-div"),
    
    dcc.Store(id="repo-store", storage_type='session'),  # Changed to session storage
    dcc.Store(id="token-store", storage_type='session'),  # Changed to session storage
    dcc.Store(id="actual-repo"),
    dcc.Store(id="actual-git-obj"),
    dcc.Store(id="main-metrics-dict"),
    dcc.Store(id="main-metrics-df"),
    dcc.Store(id="main-file-names"),
    dcc.Store(id="pull-req-metrics-dict"),
    dcc.Store(id="pull-req-metrics-df"),
    dcc.Store(id="pull-req-file-names"),
    dcc.Store(id="nav-bar-store"),
    dash.page_container
])

if __name__ == '__main__':
    print("Starting dashboard. Registered pages:", dash.page_registry.keys())
    app.run(debug=True)