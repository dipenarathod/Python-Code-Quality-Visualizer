from dash import html, dcc, Input, Output, State, callback
import plotly.io as pio
from pathlib import Path
import os
from Branch.MetricsDataFrames import MetricsDataFrames
from Branch.MetricsPlotter import MetricsPlotter
import dash
from dash.exceptions import PreventUpdate
from PullRequests.PullRequestMetricsDataFrames import PullRequestMetricsDataFrames
import json
import pandas as pd
import plotly.graph_objects as go
import time
from dash import html, dcc, callback, Input, Output, State
import datetime

pio.renderers.default = "browser"
dash.register_page(__name__, path='/halstead', name='Halstead')

# === Global Singleton Manager ===
class HalsteadDataManager:
    _instance = None

    def __init__(self):
        self.repo_name = None
        self.main_data = {}
        self.main_data_by_sha = {}  # Map commit SHAs to dates
        self.pr_data_loader = None
        self.df_objects = {}
        self.last_refresh_time = None  # Track when we last refreshed data
        self.file_modification_times = {}  # Track file modification times to detect changes

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HalsteadDataManager()
        return cls._instance

    def should_refresh_data(self, repo_name):
        """Determine if data should be refreshed based on time or file changes"""
        current_time = time.time()
        
        # If it's the first load or repo changed, definitely refresh
        if self.repo_name != repo_name or self.last_refresh_time is None:
            return True
            
        # Check if it's been at least one minute since the last refresh
        if current_time - self.last_refresh_time >= 60:  # 60 seconds = 1 minute
            repo_safe = repo_name.replace('/', '_')
            main_path = Path(f"./metrics/{repo_safe}/halstead_metrics.json")
            pr_path = Path(f"./pull_request_metrics/{repo_safe}/Halstead_PRs.json")
            
            # Check if files exist and have been modified since last check
            files_changed = False
            
            if main_path.exists():
                current_mtime = os.path.getmtime(main_path)
                previous_mtime = self.file_modification_times.get(str(main_path), 0)
                if current_mtime > previous_mtime:
                    files_changed = True
            
            if pr_path.exists():
                current_mtime = os.path.getmtime(pr_path)
                previous_mtime = self.file_modification_times.get(str(pr_path), 0)
                if current_mtime > previous_mtime:
                    files_changed = True
            
            return files_changed
            
        return False

    def _is_valid_sha(self, key):
        """Check if a key looks like a valid commit SHA (40 character hex string)"""
        return isinstance(key, str) and len(key) == 40 and all(c in '0123456789abcdef' for c in key.lower())

    def _is_metadata_key(self, key):
        """Check if a key is a metadata key that should be skipped"""
        metadata_keys = {'branch_info', 'repository_info', 'generation_info', 'metadata'}
        return key in metadata_keys

    def load_data(self, repo_name, force_refresh=False):
        # Check if we need to refresh data
        if not force_refresh and not self.should_refresh_data(repo_name):
            return False  # No refresh needed
        
        self.repo_name = repo_name
        repo_safe = repo_name.replace('/', '_')
        main_path = Path(f"./metrics/{repo_safe}/halstead_metrics.json")
        pr_path = Path(f"./pull_request_metrics/{repo_safe}/Halstead_PRs.json")

        # Reset data containers
        self.main_data = {}
        self.main_data_by_sha = {}
        self.pr_data_loader = None

        if not main_path.exists():
            print(f"[HALSTEAD MANAGER] File not found: {main_path}")
            self.last_refresh_time = time.time()  # Update refresh time even if file not found
            return False

        try:
            # Load main branch data
            with open(main_path, 'r') as f:
                original_json_data = json.load(f)
                
            # Store file modification time
            self.file_modification_times[str(main_path)] = os.path.getmtime(main_path)
            
            # Create a cleaned copy of the JSON data (don't modify original file)
            main_json_data = {}
            skipped_keys = []
            
            for key, value in original_json_data.items():
                if self._is_metadata_key(key) or not self._is_valid_sha(key):
                    skipped_keys.append(key)
                else:
                    main_json_data[key] = value
            
            if skipped_keys:
                print(f"[HALSTEAD MANAGER] Skipped {len(skipped_keys)} invalid/metadata keys: {skipped_keys[:5]}{'...' if len(skipped_keys) > 5 else ''}")
            
            print(f"[HALSTEAD MANAGER] Processing {len(main_json_data)} valid commit SHAs")
                
            # Build the SHA to date mapping
            for sha, data in main_json_data.items():
                try:
                    if isinstance(data, dict) and "date" in data:
                        self.main_data_by_sha[sha] = pd.to_datetime(data["date"])
                except Exception as e:
                    print(f"[HALSTEAD MANAGER] Error processing SHA {sha}: {e}")
                    continue
            
            # Load DataFrame objects using cleaned data dictionary
            df_obj = MetricsDataFrames(metrics_dictionary=main_json_data, metric_type="halstead")
            self.df_objects[repo_name] = df_obj
            file_names = df_obj.get_all_files()
            print(f"[HALSTEAD MANAGER] Found {len(file_names)} files: {file_names}")

            loaded_count = 0
            for file_name in file_names:
                df = df_obj.get_file_data(file_name)
                if df is not None and not df.empty:
                    self.main_data[file_name] = df
                    loaded_count += 1
                else:
                    print(f"[HALSTEAD MANAGER] Skipped {file_name}: No data found")

            print(f"[HALSTEAD MANAGER] Loaded {loaded_count} files for {repo_name}")
            # file_names = df_obj.get_all_files()
            # print(f"[HALSTEAD MANAGER] Found {len(file_names)} files: {file_names}")
            
            # for file_name in file_names:
            #     try:
            #         self.main_data[file_name] = df_obj.get_file_data(file_name)
            #     except Exception as e:
            #         print(f"[HALSTEAD MANAGER] Error loading file {file_name}: {e}")
            #         continue

            # print(f"[HALSTEAD MANAGER] Loaded {len(self.main_data)} files for {repo_name}")

            # Load PR data if available
            if pr_path.exists():
                try:
                    self.pr_data_loader = PullRequestMetricsDataFrames(str(pr_path), "halstead")
                    # Store file modification time
                    self.file_modification_times[str(pr_path)] = os.path.getmtime(pr_path)
                    print(f"[HALSTEAD MANAGER] Loaded PR overlay data for {repo_name}")
                except Exception as e:
                    print(f"[HALSTEAD MANAGER] Error loading PR data: {e}")
                    self.pr_data_loader = None

            # Update refresh time
            self.last_refresh_time = time.time()
            return True

        except Exception as e:
            print(f"[HALSTEAD MANAGER] Error loading data: {e}")
            self.main_data = {}
            # Update refresh time even if there was an error
            self.last_refresh_time = time.time()
            return False

    def get_files(self):
        return list(self.main_data.keys())

    def get_metrics(self, file_name):
        if file_name not in self.main_data:
            return []
        return list(self.main_data[file_name].columns)

    def get_filtered_df(self, file_name, selected_metrics):
        if file_name not in self.main_data:
            return None
        valid_metrics = [m for m in selected_metrics if m in self.main_data[file_name].columns]
        if not valid_metrics:
            return None
        return self.main_data[file_name][valid_metrics]

    def get_pr_overlay_df(self, file_name, selected_metrics):
        if not self.pr_data_loader:
            return None
        df = self.pr_data_loader.get_file_data(file_name)
        if df is None or df.empty:
            return None
        valid_metrics = [m for m in selected_metrics if m in df.columns]
        if not valid_metrics:
            return None
            
        # Try to map commit SHAs to dates
        # Create a new DataFrame with dates for PRs if possible
        df_with_dates = pd.DataFrame(df[valid_metrics])
        
        # If indexes are SHAs, try to map them to dates
        new_indices = []
        for idx in df.index:
            if isinstance(idx, str) and idx in self.main_data_by_sha:
                new_indices.append(self.main_data_by_sha[idx])
            else:
                # Keep original if not found
                new_indices.append(idx)
                
        df_with_dates.index = new_indices
        return df_with_dates
        
    def debug_pr_data(self, file_name):
        """Debug function for PR data issues."""
        debug_info = []
    
        # Check if PR data loader exists
        if not self.pr_data_loader:
            debug_info.append(html.Div("PR data loader not initialized", style={"color": "red"}))
            return debug_info
    
        try:
            # Try to get PR data
            df = self.pr_data_loader.get_file_data(file_name)
        
            if df is None:
                debug_info.append(html.Div(f"No PR data found for file: {file_name}", style={"color": "red"}))
                return debug_info
        
            if df.empty:
                debug_info.append(html.Div(f"PR data exists but is empty for file: {file_name}", style={"color": "red"}))
                return debug_info
        
            # Basic PR data info
            debug_info.append(html.Div(f"PR data loaded with {len(df)} rows", style={"color": "green"}))
            debug_info.append(html.Div(f"PR data columns: {', '.join(df.columns)}", style={"color": "blue"}))
            debug_info.append(html.Div(f"PR data index type: {type(df.index[0])}", style={"color": "blue"}))
        
            # Display SHA to date mapping statistics
            shas_mapped = 0
            for idx in df.index:
                if isinstance(idx, str) and idx in self.main_data_by_sha:
                    shas_mapped += 1
            
            debug_info.append(html.Div(f"PR SHAs mapped to dates: {shas_mapped}/{len(df)}", 
                                    style={"color": "green" if shas_mapped > 0 else "orange"}))
            
            # Sample of PR data
            debug_info.append(html.H4("Sample PR data:"))
            debug_info.append(html.Pre(df.head().to_string()))
        
            return debug_info
        except Exception as e:
            debug_info.append(html.Div(f"Error in debug_pr_data: {str(e)}", style={"color": "red"}))
            return debug_info


# === Layout ===
layout = html.Div([
    html.H2("Halstead Metrics Visualization"),
    html.Div(id="halstead-loading-info", style={"color": "green"}),
    dcc.Dropdown(id="halstead-file-dropdown", placeholder="Select a file"),
    dcc.Dropdown(id="halstead-metric-dropdown", placeholder="Select metrics", multi=True),
    dcc.Checklist(
        id="show_pull_requests",
        options=[{"label": "Show Pull Request Overlays", "value": "show"}],
        value=[],
        style={"marginTop": "10px"}
    ),
    html.Button("Debug PR Data", id="debug-pr-button", style={"marginTop": "10px"}),
    html.Div(id="pr-debug-output"),
    html.Div(id="halstead-graphs"),
    
    # Add refresh information and auto-refresh interval
    html.Div([
        html.Span("Last refreshed: ", style={"fontWeight": "bold"}),
        html.Span(id="last-refresh-time", children="Never"),
        html.Button("Refresh Now", id="refresh-button", style={"marginLeft": "10px"})
    ], style={"marginTop": "20px", "marginBottom": "10px"}),
    
    # Interval component for auto-refresh
    dcc.Interval(
        id='auto-refresh-interval',
        interval=60*1000,  # in milliseconds, 60 seconds = 1 minute
        n_intervals=0
    )
])

# === Callbacks ===
@callback(
    Output("halstead-loading-info", "children"),
    Output("halstead-file-dropdown", "options"),
    Output("last-refresh-time", "children"),
    Input("repo-store", "data"),
    Input("token-store", "data"),
    Input("auto-refresh-interval", "n_intervals"),
    Input("refresh-button", "n_clicks")
)
def update_file_dropdown(repo_name, __, n_intervals, n_clicks):
    if not repo_name:
        return "No repository selected", [], "Never"
    
    try:
        manager = HalsteadDataManager.get_instance()
        data_refreshed = manager.load_data(repo_name)
        files = manager.get_files()
        
        if not files:
            return f"No Halstead metrics found for {repo_name}", [], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        refresh_message = "Data up to date"
        if data_refreshed:
            refresh_message = f"Data refreshed! Found {len(files)} files"
            
        return refresh_message, [{"label": f, "value": f} for f in files], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return f"Error loading files: {str(e)}", [], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@callback(
    Output("halstead-metric-dropdown", "options"),
    Input("halstead-file-dropdown", "value"),
    State("repo-store", "data")
)
def update_metric_dropdown(file_name, repo_name):
    if not file_name or not repo_name:
        return []
    try:
        manager = HalsteadDataManager.get_instance()
        metrics = manager.get_metrics(file_name)
        return [{"label": m, "value": m} for m in metrics]
    except Exception as e:
        print(f"Error getting metrics: {e}")
        return []

@callback(
    Output("pr-debug-output", "children"),
    Input("debug-pr-button", "n_clicks"),
    State("halstead-file-dropdown", "value"),
    prevent_initial_call=True
)
def debug_pr_data(n_clicks, file_name):
    if not n_clicks or not file_name:
        return []
        
    manager = HalsteadDataManager.get_instance()
    return manager.debug_pr_data(file_name)

@callback(
    Output("halstead-graphs", "children"),
    Input("halstead-file-dropdown", "value"),
    Input("halstead-metric-dropdown", "value"),
    Input("show_pull_requests", "value"),
    Input("auto-refresh-interval", "n_intervals"),
    Input("refresh-button", "n_clicks"),
    State("repo-store", "data")
)
def update_graphs(file_name, selected_metrics, show_pr_value, n_intervals, n_clicks, repo_name):
    if not file_name or not selected_metrics or not repo_name:
        return []

    # Check for data refreshes on auto interval or manual refresh
    manager = HalsteadDataManager.get_instance()
    manager.load_data(repo_name)  # Check for updates

    debug_info = []
    
    try:
        # Get main data
        df_main = manager.get_filtered_df(file_name, selected_metrics)
        if df_main is None or df_main.empty:
            return html.Div("No main branch data available", style={"color": "red"})
        
        # Initialize figures list
        figures = []
        
        # Create a figure for each metric
        for metric in selected_metrics:
            fig = go.Figure()
            
            # Add main branch data with actual datetime as x-axis
            fig.add_trace(go.Scatter(
                x=df_main.index,  # Use the datetime index
                y=df_main[metric],
                mode='lines+markers',
                name=f'Main - {metric}',
                line=dict(color='blue'),
                marker=dict(size=8)
            ))
            
            # Update layout with improved datetime handling
            fig.update_layout(
                title=f'{metric} over time',
                xaxis_title='Date',
                yaxis_title=metric,
                xaxis=dict(
                    type='date',
                    tickformat='%Y-%m-%d',  # Custom date format
                    tickangle=45,  # Angle the dates for better readability
                ),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                hovermode='closest'
            )
            
            # Add PR data if requested
            if "show" in show_pr_value:
                df_pr = manager.get_pr_overlay_df(file_name, selected_metrics)
                
                if df_pr is not None and not df_pr.empty and metric in df_pr.columns:
                    debug_info.append(html.Div(f"Found {len(df_pr)} PR data points for {metric}", 
                                         style={"color": "green"}))
                    
                    # Check if indices are datetime objects
                    datetime_indices = all(isinstance(idx, pd.Timestamp) for idx in df_pr.index)
                    
                    if datetime_indices:
                        # Add PR trace with datetime x-axis
                        fig.add_trace(go.Scatter(
                            x=df_pr.index,  # Use datetime indices
                            y=df_pr[metric],
                            mode='markers',
                            name=f'PR - {metric}',
                            marker=dict(
                                size=15,
                                symbol='star',
                                color='red',
                                line=dict(width=2, color='black')
                            ),
                            hovertemplate='Date: %{x}<br>Value: %{y:.2f}<extra></extra>'
                        ))
                    else:
                        # Fallback for non-datetime indices
                        # Use the first date in the main data as a temporary placeholder
                        # In real usage, you should map PR SHAs to dates properly
                        pr_data = df_pr[metric].reset_index()
                        
                        fig.add_trace(go.Scatter(
                            x=[df_main.index[0]] * len(df_pr),  # Temporary fix
                            y=df_pr[metric],
                            mode='markers',
                            name=f'PR - {metric}',
                            marker=dict(
                                size=15,
                                symbol='star',
                                color='red',
                                line=dict(width=2, color='black')
                            ),
                            text=[f"PR SHA: {idx}" for idx in df_pr.index],
                            hovertemplate='%{text}<br>Value: %{y:.2f}<extra></extra>'
                        ))
                        
                        debug_info.append(html.Div("Warning: PR data does not have proper datetime indices", 
                                              style={"color": "orange"}))
        
            figures.append(fig)
        
        # Return debug info and figures
        return debug_info + [dcc.Graph(figure=fig) for fig in figures]
    
    except Exception as e:
        return html.Div(f"Error generating graphs: {str(e)}", style={"color": "red"})
