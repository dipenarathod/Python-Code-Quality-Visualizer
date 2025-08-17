import json
import os
import time
import datetime
import pandas as pd
from pathlib import Path
from dash import html, dcc, Input, Output, State, callback
import plotly.graph_objects as go
import dash
from dash.exceptions import PreventUpdate
from Branch.MetricsDataFrames import MetricsDataFrames
from PullRequests.PullRequestMetricsDataFrames import PullRequestMetricsDataFrames
import plotly.io as pio
pio.renderers.default = "browser"
dash.register_page(__name__, path='/traditional', name='Traditional')

class TraditionalDataManager:
    _instance = None

    def __init__(self):
        self.repo_name = None
        self.main_data = {}
        self.main_data_by_sha = {}
        self.pr_data_loader = None
        self.df_objects = {}
        self.file_modification_times = {}
        self.last_refresh_time = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TraditionalDataManager()
        return cls._instance

    def _is_valid_sha(self, key):
        return isinstance(key, str) and len(key) == 40 and all(c in '0123456789abcdef' for c in key.lower())

    def _is_metadata_key(self, key):
        return key in {'branch_info', 'repository_info', 'generation_info', 'metadata'}

    def should_refresh_data(self, repo_name):
        current_time = time.time()
        if self.repo_name != repo_name or self.last_refresh_time is None:
            return True

        if current_time - self.last_refresh_time >= 60:
            repo_safe = repo_name.replace('/', '_')
            project_root = Path(__file__).parent.parent
            main_path = project_root / f"metrics/{repo_safe}/traditional_metrics.json"
            pr_path = project_root / f"pull_request_metrics/{repo_safe}/Traditional_PRs.json"

            files_changed = False
            if main_path.exists():
                current_mtime = os.path.getmtime(main_path)
                if current_mtime > self.file_modification_times.get(str(main_path), 0):
                    files_changed = True
            if pr_path.exists():
                current_mtime = os.path.getmtime(pr_path)
                if current_mtime > self.file_modification_times.get(str(pr_path), 0):
                    files_changed = True
            return files_changed
        return False

    def load_data(self, repo_name, force_refresh=False):
        if not force_refresh and not self.should_refresh_data(repo_name):
            return False

        self.repo_name = repo_name
        repo_safe = repo_name.replace('/', '_')
        project_root = Path(__file__).parent.parent
        main_path = project_root / f"metrics/{repo_safe}/traditional_metrics.json"
        pr_path = project_root / f"pull_request_metrics/{repo_safe}/Traditional_PRs.json"

        self.main_data = {}
        self.main_data_by_sha = {}
        self.pr_data_loader = None

        if not main_path.exists():
            print(f"[TRADITIONAL MANAGER] File not found: {main_path}")
            self.last_refresh_time = time.time()
            return False

        try:
            with open(main_path, 'r') as f:
                original_json_data = json.load(f)

            self.file_modification_times[str(main_path)] = os.path.getmtime(main_path)

            main_json_data = {}
            for key, value in original_json_data.items():
                if not self._is_metadata_key(key) and self._is_valid_sha(key):
                    main_json_data[key] = value

            for sha, data in main_json_data.items():
                if "date" in data:
                    self.main_data_by_sha[sha] = pd.to_datetime(data["date"])

            df_obj = MetricsDataFrames(metrics_dictionary=main_json_data, metric_type="traditional")
            self.df_objects[repo_name] = df_obj

            for file_name in df_obj.get_all_files():
                try:
                    df_dict = df_obj.get_file_data(file_name)
                    valid_data = {}
                    for metric_type, df in df_dict.items():
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            valid_data[metric_type] = df

                    if valid_data:
                        self.main_data[file_name] = valid_data
                    else:
                        print(f"[TRADITIONAL MANAGER] Skipped {file_name}: All metric DataFrames are empty")

                except Exception as e:
                    print(f"[TRADITIONAL MANAGER] Error loading file {file_name}: {e}")

            if pr_path.exists():
                try:
                    self.pr_data_loader = PullRequestMetricsDataFrames(str(pr_path), "traditional")
                    self.file_modification_times[str(pr_path)] = os.path.getmtime(pr_path)
                except Exception as e:
                    print(f"[TRADITIONAL MANAGER] Error loading PR data: {e}")

            self.last_refresh_time = time.time()
            return True

        except Exception as e:
            print(f"[TRADITIONAL MANAGER] Error loading data: {e}")
            self.main_data = {}
            self.last_refresh_time = time.time()
            return False

    def get_files(self):
        return list(self.main_data.keys())

    def get_metrics(self, file_name):
        if file_name not in self.main_data:
            return []
        
        # Define flat metrics that don't need prefixing
        flat_metrics = ['LOC', 'Length of Identifier']
        
        result = []
        for metric_type, df in self.main_data[file_name].items():
            for col in df.columns:
                # For flat metrics, use just the column name
                if metric_type in flat_metrics:
                    result.append(col)
                else:
                    # For nested metrics, use the prefixed format
                    result.append(f"{metric_type}_{col}")
        return result

    def get_filtered_df(self, file_name, selected_metrics):
        if file_name not in self.main_data:
            return None
        
        # Define flat metrics that don't need prefixing
        flat_metrics = ['LOC', 'Length of Identifier']
        
        result_df = None
        for metric in selected_metrics:
            found = False
            
            # First, check if it's a flat metric (no underscore needed)
            for metric_type, df in self.main_data[file_name].items():
                if metric_type in flat_metrics and metric in df.columns:
                    if result_df is None:
                        result_df = pd.DataFrame(index=df.index)
                    result_df[metric] = df[metric]
                    found = True
                    break
            
            # If not found, try the prefixed format
            if not found and '_' in metric:
                metric_type, col_name = metric.split('_', 1)
                df = self.main_data[file_name].get(metric_type)
                if df is not None and col_name in df.columns:
                    if result_df is None:
                        result_df = pd.DataFrame(index=df.index)
                    result_df[metric] = df[col_name]
        
        return result_df

    def get_pr_overlay_df(self, file_name, selected_metrics):
        if not self.pr_data_loader:
            print(f"[TRADITIONAL PR] No PR data loader available")
            return None
            
        try:
            file_data = self.pr_data_loader.get_file_data(file_name)
            if not file_data:
                print(f"[TRADITIONAL PR] No file data returned for {file_name}")
                return None
            
            print(f"[TRADITIONAL PR] Available metric types: {list(file_data.keys())}")
            
            # Define flat metrics that don't need prefixing
            flat_metrics = ['LOC', 'Length of Identifier']
            
            result_df = None
            for metric in selected_metrics:
                found = False
                print(f"[TRADITIONAL PR] Looking for metric: {metric}")
                
                # First, check if it's a flat metric (no underscore needed)
                for metric_type, df in file_data.items():
                    if df is None or df.empty:
                        continue
                        
                    print(f"[TRADITIONAL PR] Checking metric_type: {metric_type}, columns: {list(df.columns)}")
                    
                    # For flat metrics like 'LOC', 'Length of Identifier'
                    if metric_type in flat_metrics and metric in df.columns:
                        if result_df is None:
                            result_df = pd.DataFrame(index=df.index)
                        result_df[metric] = df[metric]
                        # Also preserve pr_number if it exists
                        if 'pr_number' in df.columns and 'pr_number' not in result_df.columns:
                            result_df['pr_number'] = df['pr_number']
                        found = True
                        print(f"[TRADITIONAL PR] Found flat metric {metric} in {metric_type}")
                        break
                    
                    # For the special case where the PR data structure might be different
                    # Check if the metric exists directly in any dataframe
                    elif metric in df.columns:
                        if result_df is None:
                            result_df = pd.DataFrame(index=df.index)
                        result_df[metric] = df[metric]
                        # Also preserve pr_number if it exists
                        if 'pr_number' in df.columns and 'pr_number' not in result_df.columns:
                            result_df['pr_number'] = df['pr_number']
                        found = True
                        print(f"[TRADITIONAL PR] Found direct metric {metric} in {metric_type}")
                        break
                
                # If not found, try the prefixed format
                if not found and '_' in metric:
                    metric_type, col_name = metric.split('_', 1)
                    df = file_data.get(metric_type)
                    if df is not None and not df.empty and col_name in df.columns:
                        if result_df is None:
                            result_df = pd.DataFrame(index=df.index)
                        result_df[metric] = df[col_name]
                        # Also preserve pr_number if it exists
                        if 'pr_number' in df.columns and 'pr_number' not in result_df.columns:
                            result_df['pr_number'] = df['pr_number']
                        found = True
                        print(f"[TRADITIONAL PR] Found prefixed metric {metric} -> {metric_type}.{col_name}")
                
                if not found:
                    print(f"[TRADITIONAL PR] Metric {metric} not found in PR data")
            
            if result_df is not None and not result_df.empty:
                print(f"[TRADITIONAL PR] Final PR dataframe shape: {result_df.shape}")
                print(f"[TRADITIONAL PR] Final PR dataframe columns: {list(result_df.columns)}")
                print(f"[TRADITIONAL PR] Final PR dataframe index type: {type(result_df.index[0]) if len(result_df) > 0 else 'empty'}")
                
                # Map commit SHAs to dates using the main data mapping
                new_indices = []
                for idx in result_df.index:
                    if isinstance(idx, str) and idx in self.main_data_by_sha:
                        new_indices.append(self.main_data_by_sha[idx])
                        print(f"[TRADITIONAL PR] Mapped SHA {idx[:8]}... to date")
                    else:
                        new_indices.append(idx)
                        print(f"[TRADITIONAL PR] Could not map index {idx}")
                
                result_df.index = new_indices
                return result_df
            else:
                print(f"[TRADITIONAL PR] No valid PR data found for selected metrics")
                return None
                
        except Exception as e:
            print(f"[TRADITIONAL PR] Error in get_pr_overlay_df: {e}")
            import traceback
            traceback.print_exc()
            return None

layout = html.Div([
    html.H2("Traditional Metrics Visualization"),
    html.Div(id="traditional-loading-info", style={"color": "green"}),
    dcc.Dropdown(id="traditional-file-dropdown", placeholder="Select a file"),
    dcc.Dropdown(id="traditional-metric-dropdown", placeholder="Select metrics", multi=True),
    dcc.Checklist(
        id="traditional-show-pull-requests",
        options=[{"label": "Show Pull Request Overlays", "value": "show"}],
        value=[],
        style={"marginTop": "10px"}
    ),
    html.Button("Debug PR Data", id="traditional-debug-pr-button", style={"marginTop": "10px"}),
    html.Div(id="traditional-pr-debug-output"),
    html.Button("Refresh Now", id="traditional-refresh-button", style={"marginTop": "10px"}),
    html.Span("Last refreshed: ", style={"fontWeight": "bold"}),
    html.Span(id="traditional-last-refresh-time", children="Never"),
    dcc.Interval(id='traditional-auto-refresh-interval', interval=60 * 1000, n_intervals=0),
    html.Div(id="traditional-graphs")
])

@callback(
    Output("traditional-loading-info", "children"),
    Output("traditional-file-dropdown", "options"),
    Output("traditional-last-refresh-time", "children"),
    Input("repo-store", "data"),
    Input("token-store", "data"),
    Input("traditional-auto-refresh-interval", "n_intervals"),
    Input("traditional-refresh-button", "n_clicks")
)
def update_traditional_dropdown(repo_name, __, n_intervals, n_clicks):
    if not repo_name:
        return "No repository selected", [], "Never"
    manager = TraditionalDataManager.get_instance()
    refreshed = manager.load_data(repo_name)
    files = manager.get_files()
    msg = f"Data refreshed! Found {len(files)} files" if refreshed else "Data up to date"
    return msg, [{"label": f, "value": f} for f in files], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@callback(
    Output("traditional-metric-dropdown", "options"),
    Input("traditional-file-dropdown", "value"),
    State("repo-store", "data")
)
def update_metric_dropdown(file_name, repo_name):
    if not file_name or not repo_name:
        return []
    manager = TraditionalDataManager.get_instance()
    return [{"label": m, "value": m} for m in manager.get_metrics(file_name)]

@callback(
    Output("traditional-pr-debug-output", "children"),
    Input("traditional-debug-pr-button", "n_clicks"),
    State("traditional-file-dropdown", "value"),
    State("repo-store", "data"),
    prevent_initial_call=True
)
def debug_traditional_pr_data(n_clicks, file_name, repo_name):
    if not n_clicks or not file_name:
        return []
    manager = TraditionalDataManager.get_instance()
    if not manager.pr_data_loader:
        return html.Div("No PR data loader initialized", style={"color": "red"})
    file_data = manager.pr_data_loader.get_file_data(file_name)
    if not file_data:
        return html.Div(f"No PR data for file: {file_name}", style={"color": "orange"})
    debug_info = [html.H4("PR Data Debug Information")]
    for metric_type, df in file_data.items():
        if df is None or df.empty:
            continue
        debug_info.append(html.H5(f"Metric Type: {metric_type}"))
        debug_info.append(html.Pre(df.head().to_string()))
    return html.Div(debug_info)

@callback(
    Output("traditional-graphs", "children"),
    Input("traditional-file-dropdown", "value"),
    Input("traditional-metric-dropdown", "value"),
    Input("traditional-show-pull-requests", "value"),
    Input("traditional-auto-refresh-interval", "n_intervals"),
    Input("traditional-refresh-button", "n_clicks"),
    State("repo-store", "data")
)
def update_traditional_graphs(file_name, selected_metrics, show_pr_value, n_intervals, n_clicks, repo_name):
    if not file_name or not selected_metrics or not repo_name:
        return []
    
    manager = TraditionalDataManager.get_instance()
    manager.load_data(repo_name)
    
    # Get main branch data
    df_main = manager.get_filtered_df(file_name, selected_metrics)
    if df_main is None or df_main.empty:
        return html.Div("No data available", style={"color": "red"})

    # Get PR data if requested
    df_pr = None
    if "show" in show_pr_value:
        df_pr = manager.get_pr_overlay_df(file_name, selected_metrics)
        if df_pr is not None:
            print(f"[TRADITIONAL GRAPH] PR data loaded with {len(df_pr)} rows")
        else:
            print(f"[TRADITIONAL GRAPH] No PR data returned")

    graphs = []
    for metric in selected_metrics:
        if metric not in df_main.columns:
            continue
            
        fig = go.Figure()
        
        # Add main branch data
        fig.add_trace(go.Scatter(
            x=df_main.index, 
            y=df_main[metric], 
            mode='lines+markers', 
            name=f"Main - {metric}",
            line=dict(color='blue'),
            marker=dict(size=8)
        ))
        
        # Add PR data if available
        if df_pr is not None and metric in df_pr.columns:
            print(f"[TRADITIONAL GRAPH] Adding PR overlay for {metric}")
            
            # Prepare hover text
            hover_text = None
            if 'pr_number' in df_pr.columns:
                hover_text = [f"PR: {pr}" for pr in df_pr['pr_number']]
                hover_template = '%{text}<br>Date: %{x}<br>Value: %{y:.2f}<extra></extra>'
            else:
                hover_template = 'Date: %{x}<br>Value: %{y:.2f}<extra></extra>'
            
            fig.add_trace(go.Scatter(
                x=df_pr.index,
                y=df_pr[metric],
                mode='markers',
                name=f"PR - {metric}",
                marker=dict(
                    size=15,
                    symbol='star',
                    color='red',
                    line=dict(width=2, color='black')
                ),
                text=hover_text,
                hovertemplate=hover_template
            ))
        else:
            if df_pr is not None:
                print(f"[TRADITIONAL GRAPH] Metric {metric} not found in PR columns: {list(df_pr.columns)}")
        
        # Update layout
        fig.update_layout(
            title=f'{metric} over time',
            xaxis_title='Date',
            yaxis_title=metric,
            xaxis=dict(
                type='date',
                tickformat='%Y-%m-%d',
                tickangle=45
            ),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            hovermode='closest'
        )
        
        graphs.append(dcc.Graph(figure=fig))
    
    return graphs
# import json
# import os
# import time
# import datetime
# import pandas as pd
# from pathlib import Path
# from dash import html, dcc, Input, Output, State, callback
# import plotly.graph_objects as go
# import dash
# from dash.exceptions import PreventUpdate
# from Branch.MetricsDataFrames import MetricsDataFrames
# from PullRequests.PullRequestMetricsDataFrames import PullRequestMetricsDataFrames
# import plotly.io as pio
# pio.renderers.default = "browser"
# dash.register_page(__name__, path='/traditional', name='Traditional')

# class TraditionalDataManager:
#     _instance = None

#     def __init__(self):
#         self.repo_name = None
#         self.main_data = {}
#         self.main_data_by_sha = {}
#         self.pr_data_loader = None
#         self.df_objects = {}
#         self.file_modification_times = {}
#         self.last_refresh_time = None

#     @classmethod
#     def get_instance(cls):
#         if cls._instance is None:
#             cls._instance = TraditionalDataManager()
#         return cls._instance

#     def _is_valid_sha(self, key):
#         return isinstance(key, str) and len(key) == 40 and all(c in '0123456789abcdef' for c in key.lower())

#     def _is_metadata_key(self, key):
#         return key in {'branch_info', 'repository_info', 'generation_info', 'metadata'}

#     def should_refresh_data(self, repo_name):
#         current_time = time.time()
#         if self.repo_name != repo_name or self.last_refresh_time is None:
#             return True

#         if current_time - self.last_refresh_time >= 60:
#             repo_safe = repo_name.replace('/', '_')
#             main_path = Path(f"./metrics/{repo_safe}/traditional_metrics.json")
#             pr_path = Path(f"./pull_request_metrics/{repo_safe}/Traditional_PRs.json")

#             files_changed = False
#             if main_path.exists():
#                 current_mtime = os.path.getmtime(main_path)
#                 if current_mtime > self.file_modification_times.get(str(main_path), 0):
#                     files_changed = True
#             if pr_path.exists():
#                 current_mtime = os.path.getmtime(pr_path)
#                 if current_mtime > self.file_modification_times.get(str(pr_path), 0):
#                     files_changed = True
#             return files_changed
#         return False

#     def load_data(self, repo_name, force_refresh=False):
#         if not force_refresh and not self.should_refresh_data(repo_name):
#             return False

#         self.repo_name = repo_name
#         repo_safe = repo_name.replace('/', '_')
#         main_path = Path(f"./metrics/{repo_safe}/traditional_metrics.json")
#         pr_path = Path(f"./pull_request_metrics/{repo_safe}/Traditional_PRs.json")

#         self.main_data = {}
#         self.main_data_by_sha = {}
#         self.pr_data_loader = None

#         if not main_path.exists():
#             print(f"[TRADITIONAL MANAGER] File not found: {main_path}")
#             self.last_refresh_time = time.time()
#             return False

#         try:
#             with open(main_path, 'r') as f:
#                 original_json_data = json.load(f)

#             self.file_modification_times[str(main_path)] = os.path.getmtime(main_path)

#             main_json_data = {}
#             for key, value in original_json_data.items():
#                 if not self._is_metadata_key(key) and self._is_valid_sha(key):
#                     main_json_data[key] = value

#             for sha, data in main_json_data.items():
#                 if "date" in data:
#                     self.main_data_by_sha[sha] = pd.to_datetime(data["date"])

#             df_obj = MetricsDataFrames(metrics_dictionary=main_json_data, metric_type="traditional")
#             self.df_objects[repo_name] = df_obj

#             for file_name in df_obj.get_all_files():
#                 try:
#                     df_dict = df_obj.get_file_data(file_name)
#                     valid_data = {}
#                     for metric_type, df in df_dict.items():
#                         if isinstance(df, pd.DataFrame) and not df.empty:
#                             valid_data[metric_type] = df

#                     if valid_data:
#                         self.main_data[file_name] = valid_data
#                     else:
#                         print(f"[TRADITIONAL MANAGER] Skipped {file_name}: All metric DataFrames are empty")

#                 except Exception as e:
#                     print(f"[TRADITIONAL MANAGER] Error loading file {file_name}: {e}")

#             if pr_path.exists():
#                 try:
#                     self.pr_data_loader = PullRequestMetricsDataFrames(str(pr_path), "traditional")
#                     self.file_modification_times[str(pr_path)] = os.path.getmtime(pr_path)
#                 except Exception as e:
#                     print(f"[TRADITIONAL MANAGER] Error loading PR data: {e}")

#             self.last_refresh_time = time.time()
#             return True

#         except Exception as e:
#             print(f"[TRADITIONAL MANAGER] Error loading data: {e}")
#             self.main_data = {}
#             self.last_refresh_time = time.time()
#             return False

#     def get_files(self):
#         return list(self.main_data.keys())

#     def get_metrics(self, file_name):
#         if file_name not in self.main_data:
#             return []
        
#         # Define flat metrics that don't need prefixing
#         flat_metrics = ['LOC', 'Length of Identifier']
        
#         result = []
#         for metric_type, df in self.main_data[file_name].items():
#             for col in df.columns:
#                 # For flat metrics, use just the column name
#                 if metric_type in flat_metrics:
#                     result.append(col)
#                 else:
#                     # For nested metrics, use the prefixed format
#                     result.append(f"{metric_type}_{col}")
#         return result

#     def get_filtered_df(self, file_name, selected_metrics):
#         if file_name not in self.main_data:
#             return None
        
#         # Define flat metrics that don't need prefixing
#         flat_metrics = ['LOC', 'Length of Identifier']
        
#         result_df = None
#         for metric in selected_metrics:
#             found = False
            
#             # First, check if it's a flat metric (no underscore needed)
#             for metric_type, df in self.main_data[file_name].items():
#                 if metric_type in flat_metrics and metric in df.columns:
#                     if result_df is None:
#                         result_df = pd.DataFrame(index=df.index)
#                     result_df[metric] = df[metric]
#                     found = True
#                     break
            
#             # If not found, try the prefixed format
#             if not found and '_' in metric:
#                 metric_type, col_name = metric.split('_', 1)
#                 df = self.main_data[file_name].get(metric_type)
#                 if df is not None and col_name in df.columns:
#                     if result_df is None:
#                         result_df = pd.DataFrame(index=df.index)
#                     result_df[metric] = df[col_name]
        
#         return result_df

#     def get_pr_overlay_df(self, file_name, selected_metrics):
#         if not self.pr_data_loader:
#             return None
#         file_data = self.pr_data_loader.get_file_data(file_name)
#         if not file_data:
#             return None
        
#         # Define flat metrics that don't need prefixing
#         flat_metrics = ['LOC', 'Length of Identifier']
        
#         result_df = None
#         for metric in selected_metrics:
#             found = False
            
#             # First, check if it's a flat metric (no underscore needed)
#             for metric_type, df in file_data.items():
#                 if metric_type in flat_metrics and metric in df.columns:
#                     if result_df is None:
#                         result_df = pd.DataFrame(index=df.index)
#                     result_df[metric] = df[metric]
#                     if 'pr_number' in df.columns and 'pr_number' not in result_df.columns:
#                         result_df['pr_number'] = df['pr_number']
#                     found = True
#                     break
            
#             # If not found, try the prefixed format
#             if not found and '_' in metric:
#                 metric_type, col_name = metric.split('_', 1)
#                 df = file_data.get(metric_type)
#                 if df is not None and col_name in df.columns:
#                     if result_df is None:
#                         result_df = pd.DataFrame(index=df.index)
#                     result_df[metric] = df[col_name]
#                     if 'pr_number' in df.columns and 'pr_number' not in result_df.columns:
#                         result_df['pr_number'] = df['pr_number']
        
#         if result_df is not None:
#             new_indices = [self.main_data_by_sha.get(idx, idx) for idx in result_df.index]
#             result_df.index = new_indices
#         return result_df

# layout = html.Div([
#     html.H2("Traditional Metrics Visualization"),
#     html.Div(id="traditional-loading-info", style={"color": "green"}),
#     dcc.Dropdown(id="traditional-file-dropdown", placeholder="Select a file"),
#     dcc.Dropdown(id="traditional-metric-dropdown", placeholder="Select metrics", multi=True),
#     dcc.Checklist(
#         id="traditional-show-pull-requests",
#         options=[{"label": "Show Pull Request Overlays", "value": "show"}],
#         value=[],
#         style={"marginTop": "10px"}
#     ),
#     html.Button("Debug PR Data", id="traditional-debug-pr-button", style={"marginTop": "10px"}),
#     html.Div(id="traditional-pr-debug-output"),
#     html.Button("Refresh Now", id="traditional-refresh-button", style={"marginTop": "10px"}),
#     html.Span("Last refreshed: ", style={"fontWeight": "bold"}),
#     html.Span(id="traditional-last-refresh-time", children="Never"),
#     dcc.Interval(id='traditional-auto-refresh-interval', interval=60 * 1000, n_intervals=0),
#     html.Div(id="traditional-graphs")
# ])

# @callback(
#     Output("traditional-loading-info", "children"),
#     Output("traditional-file-dropdown", "options"),
#     Output("traditional-last-refresh-time", "children"),
#     Input("repo-store", "data"),
#     Input("token-store", "data"),
#     Input("traditional-auto-refresh-interval", "n_intervals"),
#     Input("traditional-refresh-button", "n_clicks")
# )
# def update_traditional_dropdown(repo_name, __, n_intervals, n_clicks):
#     if not repo_name:
#         return "No repository selected", [], "Never"
#     manager = TraditionalDataManager.get_instance()
#     refreshed = manager.load_data(repo_name)
#     files = manager.get_files()
#     msg = f"Data refreshed! Found {len(files)} files" if refreshed else "Data up to date"
#     return msg, [{"label": f, "value": f} for f in files], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# @callback(
#     Output("traditional-metric-dropdown", "options"),
#     Input("traditional-file-dropdown", "value"),
#     State("repo-store", "data")
# )
# def update_metric_dropdown(file_name, repo_name):
#     if not file_name or not repo_name:
#         return []
#     manager = TraditionalDataManager.get_instance()
#     return [{"label": m, "value": m} for m in manager.get_metrics(file_name)]

# @callback(
#     Output("traditional-pr-debug-output", "children"),
#     Input("traditional-debug-pr-button", "n_clicks"),
#     State("traditional-file-dropdown", "value"),
#     State("repo-store", "data"),
#     prevent_initial_call=True
# )
# def debug_traditional_pr_data(n_clicks, file_name, repo_name):
#     if not n_clicks or not file_name:
#         return []
#     manager = TraditionalDataManager.get_instance()
#     if not manager.pr_data_loader:
#         return html.Div("No PR data loader initialized", style={"color": "red"})
#     file_data = manager.pr_data_loader.get_file_data(file_name)
#     if not file_data:
#         return html.Div(f"No PR data for file: {file_name}", style={"color": "orange"})
#     debug_info = [html.H4("PR Data Debug Information")]
#     for metric_type, df in file_data.items():
#         if df is None or df.empty:
#             continue
#         debug_info.append(html.H5(f"Metric Type: {metric_type}"))
#         debug_info.append(html.Pre(df.head().to_string()))
#     return html.Div(debug_info)

# @callback(
#     Output("traditional-graphs", "children"),
#     Input("traditional-file-dropdown", "value"),
#     Input("traditional-metric-dropdown", "value"),
#     Input("traditional-show-pull-requests", "value"),
#     Input("traditional-auto-refresh-interval", "n_intervals"),
#     Input("traditional-refresh-button", "n_clicks"),
#     State("repo-store", "data")
# )
# def update_traditional_graphs(file_name, selected_metrics, show_pr_value, n_intervals, n_clicks, repo_name):
#     if not file_name or not selected_metrics or not repo_name:
#         return []
#     manager = TraditionalDataManager.get_instance()
#     manager.load_data(repo_name)
#     df_main = manager.get_filtered_df(file_name, selected_metrics)
#     if df_main is None or df_main.empty:
#         return html.Div("No data available", style={"color": "red"})

#     df_pr = manager.get_pr_overlay_df(file_name, selected_metrics) if "show" in show_pr_value else None
#     graphs = []
#     for metric in selected_metrics:
#         if metric not in df_main.columns:
#             continue
#         fig = go.Figure()
#         fig.add_trace(go.Scatter(x=df_main.index, y=df_main[metric], mode='lines+markers', name=f"Main - {metric}"))
#         if df_pr is not None and metric in df_pr.columns:
#             fig.add_trace(go.Scatter(
#                 x=df_pr.index,
#                 y=df_pr[metric],
#                 mode='markers',
#                 name=f"PR - {metric}",
#                 marker=dict(size=12, symbol='star', color='red', line=dict(width=2, color='black')),
#                 text=[f"PR: {pr}" for pr in df_pr['pr_number']] if 'pr_number' in df_pr.columns else None,
#                 hovertemplate='%{text}<br>Value: %{y:.2f}<extra></extra>' if 'pr_number' in df_pr.columns else None
#             ))
#         fig.update_layout(title=metric, xaxis_title='Date', yaxis_title=metric, hovermode='closest')
#         graphs.append(dcc.Graph(figure=fig))
#     return graphs
