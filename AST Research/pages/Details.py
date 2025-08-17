from dash import html, dcc, Input, Output, State, callback
import dash

dash.register_page(__name__, path='/', name='Details')

layout = html.Div(
    style={'maxWidth': '600px', 'margin': 'auto', 'padding': '2rem'},
    children=[
        html.H2("GitHub Metrics Viewer", style={'textAlign': 'center'}),
        html.Label("GitHub Repository (e.g., octocat/Hello-World)"),
        dcc.Input(id='repo-name-input', type='text', placeholder='owner/repo', style={'width': '100%', 'marginBottom': '1rem'}),
        
        html.Label("GitHub Token"),
        dcc.Input(id='github-token-input', type='password', placeholder='your token here', style={'width': '100%', 'marginBottom': '1rem'}),
        
        html.Button('Submit', id='submit-button', n_clicks=0, style={'width': '100%', 'marginBottom': '1rem'}),
        html.Div(id='navigation-buttons'),
        html.Div(id='error-message', style={'color': 'red', 'marginTop': '1rem'})
    ]
)

@callback(
    Output('repo-store', 'data'),
    Output('token-store', 'data'),
    Output('navigation-buttons', 'children'),
    Output('error-message', 'children'),
    Input('submit-button', 'n_clicks'),
    State('repo-name-input', 'value'),
    State('github-token-input', 'value'),
    prevent_initial_call=True
)
def handle_submit(n_clicks, repo_name, token):
    if not repo_name or '/' not in repo_name:
        return dash.no_update, dash.no_update, [], "Please enter a valid repository in the format 'owner/repo'."
    
    if not token or len(token.strip()) < 10:  # simple token check
        return dash.no_update, dash.no_update, [], "Please enter a valid GitHub token."
    
    # Print for debugging
    print(f"[DETAILS DEBUG] Saving repo: {repo_name}")
    print(f"[DETAILS DEBUG] Token available: Yes")
    
    # Save the data and prepare navigation
    nav_buttons = html.Div([
        html.P("Jump to a metric page:"),
        html.Div([
            dcc.Link("📊 Halstead Metrics", href="/halstead", style={'marginRight': '1rem'}),
            dcc.Link("📐 Traditional Metrics", href="/traditional", style={'marginRight': '1rem'}),
            dcc.Link("⚙️ OO Metrics", href="/oo"),
        ])
    ], style={'marginTop': '1rem'})
    
    return repo_name.strip(), token.strip(), nav_buttons, ""