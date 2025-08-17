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
    
    dcc.Store(id="repo-store", storage_type='session'),  
    dcc.Store(id="token-store", storage_type='session'),  
    dcc.Store(id="actual-repo", storage_type='session'),
    dcc.Store(id="actual-git-obj", storage_type='session'),
    dcc.Store(id="main-metrics-dict", storage_type='session'),
    dcc.Store(id="main-metrics-df", storage_type='session'),
    dcc.Store(id="main-file-names", storage_type='session'),
    dcc.Store(id="pull-req-metrics-dict", storage_type='session'),
    dcc.Store(id="pull-req-metrics-df", storage_type='session'),
    dcc.Store(id="pull-req-file-names", storage_type='session'),
    dcc.Store(id="nav-bar-store", storage_type='session'),
    dash.page_container
])

if __name__ == '__main__':
    print("Starting dashboard. Registered pages:", dash.page_registry.keys())
    app.run(debug=True)