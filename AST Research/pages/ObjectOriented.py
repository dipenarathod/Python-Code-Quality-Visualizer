import json
from dash import html, dcc, Input, Output, State, callback
import plotly.io as pio
from pathlib import Path
import os
from Branch.MetricsDataFrames import MetricsDataFrames
from Branch.MetricsPlotter import MetricsPlotter
import dash
from dash.exceptions import PreventUpdate
from PullRequests.PullRequestMetricsDataFrames import PullRequestMetricsDataFrames
import pandas as pd
import plotly.graph_objects as go
import time
import datetime

pio.renderers.default = "browser"
dash.register_page(__name__, path='/oo', name='Object Oriented')


class OODataManager:
    """
    Singleton class for managing Object-Oriented metrics data.
    Handles loading and processing of OO metrics from JSON files.
    """
    _instance = None
    
    def __init__(self):
        self.repo_name = None
        self.main_data = {}  # Store dataframes by file name
        self.main_data_by_sha = {}  # Maps commit SHAs to dates
        self.pr_data_loader = None
        self.df_objects = {}
        self.all_metrics = ['WMC', 'NOC', 'DIT', 'CBO']  # Default OO metrics
        self.last_refresh_time = None  # Track when we last refreshed data
        self.file_modification_times = {}  # Track file modification times to detect changes
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = OODataManager()
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
            main_path = Path(f"./metrics/{repo_safe}/oo_metrics.json")
            pr_path = Path(f"./pull_request_metrics/{repo_safe}/OO_PRs.json")
            
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
        return key in {'branch_info', 'repository_info', 'generation_info', 'metadata'}

    def load_data(self, repo_name, force_refresh=False):
        if not force_refresh and not self.should_refresh_data(repo_name):
            return False

        self.repo_name = repo_name
        repo_safe = repo_name.replace('/', '_')
        main_path = Path(f"./metrics/{repo_safe}/oo_metrics.json")
        pr_path = Path(f"./pull_request_metrics/{repo_safe}/OO_PRs.json")

        self.main_data = {}
        self.main_data_by_sha = {}
        self.pr_data_loader = None

        if not main_path.exists():
            print(f"[OO MANAGER] File not found: {main_path}")
            self.last_refresh_time = time.time()
            return False

        try:
            with open(main_path, 'r') as f:
                original_json_data = json.load(f)

            self.file_modification_times[str(main_path)] = os.path.getmtime(main_path)

            main_json_data = {}
            skipped_keys = []

            for key, value in original_json_data.items():
                if self._is_metadata_key(key) or not self._is_valid_sha(key):
                    skipped_keys.append(key)
                else:
                    main_json_data[key] = value

            if skipped_keys:
                print(f"[OO MANAGER] Skipped {len(skipped_keys)} invalid/metadata keys: {skipped_keys[:5]}{'...' if len(skipped_keys) > 5 else ''}")

            print(f"[OO MANAGER] Processing {len(main_json_data)} valid commit SHAs")

            for sha, data in main_json_data.items():
                try:
                    if isinstance(data, dict) and "date" in data:
                        self.main_data_by_sha[sha] = pd.to_datetime(data["date"])
                except Exception as e:
                    print(f"[OO MANAGER] Error processing SHA {sha}: {e}")

            df_obj = MetricsDataFrames(metrics_dictionary=main_json_data, metric_type="oo")
            self.df_objects[repo_name] = df_obj

            file_names = df_obj.get_all_files()
            print(f"[OO MANAGER] Found {len(file_names)} files: {file_names}")

            loaded_count = 0
            for file_name in file_names:
                try:
                    df_dict = df_obj.get_file_data(file_name)
                    if isinstance(df_dict, dict):
                        non_empty_metrics = {k: v for k, v in df_dict.items() if isinstance(v, pd.DataFrame) and not v.empty}
                        if non_empty_metrics:
                            self.main_data[file_name] = non_empty_metrics
                            loaded_count += 1
                        else:
                            print(f"[OO MANAGER] Skipped {file_name}: All metric DataFrames are empty")
                    else:
                        print(f"[OO MANAGER] Unexpected data type for {file_name}: {type(df_dict)}")

                except Exception as e:
                    print(f"[OO MANAGER] Error loading file {file_name}: {e}")

            print(f"[OO MANAGER] Loaded {loaded_count} files for {repo_name}")

            if pr_path.exists():
                try:
                    self.pr_data_loader = PullRequestMetricsDataFrames(str(pr_path), "oo")
                    self.file_modification_times[str(pr_path)] = os.path.getmtime(pr_path)
                    print(f"[OO MANAGER] Loaded PR overlay data for {repo_name}")
                except Exception as e:
                    print(f"[OO MANAGER] Error loading PR data: {e}")
                    self.pr_data_loader = None

            self.last_refresh_time = time.time()
            return True

        except Exception as e:
            print(f"[OO MANAGER] Error loading data: {e}")
            self.main_data = {}
            self.last_refresh_time = time.time()
            return False

    # def load_data(self, repo_name, force_refresh=False):
    #     """Load OO metrics data for the specified repository."""
    #     # Check if we need to refresh data
    #     if not force_refresh and not self.should_refresh_data(repo_name):
    #         return False  # No refresh needed
        
    #     self.repo_name = repo_name
    #     repo_safe = repo_name.replace('/', '_')
    #     main_path = Path(f"./metrics/{repo_safe}/oo_metrics.json")
    #     pr_path = Path(f"./pull_request_metrics/{repo_safe}/OO_PRs.json")
        
    #     self.main_data = {}
    #     self.main_data_by_sha = {}
    #     self.pr_data_loader = None
        
    #     if not main_path.exists():
    #         print(f"[OO MANAGER] File not found: {main_path}")
    #         self.last_refresh_time = time.time()  # Update refresh time even if file not found
    #         return False
            
    #     try:
    #         # Load main branch data
    #         with open(main_path, 'r') as f:
    #             main_json_data = json.load(f)
            
    #         # Store file modification time
    #         self.file_modification_times[str(main_path)] = os.path.getmtime(main_path)
                
    #         # Build the SHA to date mapping
    #         for sha, data in main_json_data.items():
    #             if "date" in data:
    #                 self.main_data_by_sha[sha] = pd.to_datetime(data["date"])
            
    #         try:
    #             # Process the data using MetricsDataFrames
    #             df_obj = MetricsDataFrames(str(main_path), "oo")
    #             self.df_objects[repo_name] = df_obj
    #             file_names = df_obj.get_all_files()
                
    #             for file_name in file_names:
    #                 self.main_data[file_name] = df_obj.get_file_data(file_name)
                    
    #             print(f"[OO MANAGER] Loaded {len(self.main_data)} files for {repo_name}")
    #         except Exception as df_error:
    #             print(f"[OO MANAGER] Error in DataFrame processing: {df_error}")
                
    #             # Fallback: Process the data directly if MetricsDataFrames fails
    #             print("[OO MANAGER] Attempting direct JSON processing as fallback")
                
    #             # Get first commit to find files and metrics
    #             first_commit = next(iter(main_json_data.values()))
    #             metrics_data = first_commit.get("metrics", {})
                
    #             # For each file in the metrics
    #             for file_name, file_metrics in metrics_data.items():
    #                 self.main_data[file_name] = {}
                    
    #                 # For each metric type (WMC, NOC, etc.)
    #                 for metric_type, class_data in file_metrics.items():
    #                     # Initialize with empty DataFrame if no classes
    #                     if not class_data:
    #                         self.main_data[file_name][metric_type] = pd.DataFrame(
    #                             index=[pd.to_datetime(first_commit.get("date"))]
    #                         )
    #                         continue
                            
    #                     # Create a dict to collect data across commits
    #                     metric_dict = {class_name: [] for class_name in class_data.keys()}
    #                     dates = []
                        
    #                     # For each commit
    #                     for sha, commit in main_json_data.items():
    #                         if "metrics" not in commit:
    #                             continue
                                
    #                         if file_name not in commit["metrics"]:
    #                             continue
                                
    #                         if metric_type not in commit["metrics"][file_name]:
    #                             continue
                                
    #                         # Add date
    #                         dates.append(pd.to_datetime(commit.get("date")))
                            
    #                         # Process class data
    #                         this_commit_data = commit["metrics"][file_name][metric_type]
    #                         for class_name in metric_dict.keys():
    #                             value = this_commit_data.get(class_name, 0)
    #                             metric_dict[class_name].append(value)
                        
    #                     # Create DataFrame for this metric type
    #                     if dates:
    #                         self.main_data[file_name][metric_type] = pd.DataFrame(
    #                             metric_dict, index=dates
    #                         )
    #                     else:
    #                         # Create empty DataFrame with date index
    #                         self.main_data[file_name][metric_type] = pd.DataFrame(
    #                             index=[pd.to_datetime(first_commit.get("date"))]
    #                         )
                
    #             print(f"[OO MANAGER] Loaded {len(self.main_data)} files using fallback method")
            
    #         # Load PR data if available
    #         if pr_path.exists():
    #             try:
    #                 self.pr_data_loader = PullRequestMetricsDataFrames(str(pr_path), "oo")
    #                 # Store file modification time
    #                 self.file_modification_times[str(pr_path)] = os.path.getmtime(pr_path)
    #                 print(f"[OO MANAGER] Loaded PR overlay data for {repo_name}")
    #             except Exception as pr_error:
    #                 print(f"[OO MANAGER] Error loading PR data: {pr_error}")
    #                 # Could implement similar fallback for PR data if needed
            
    #         # Update refresh time
    #         self.last_refresh_time = time.time()
    #         return True
                
    #     except Exception as e:
    #         print(f"[OO MANAGER] Error loading data: {e}")
    #         self.main_data = {}
    #         # Update refresh time even if there was an error
    #         self.last_refresh_time = time.time()
    #         return False
    
    def get_files(self):
        """Get list of files that have OO metrics."""
        return list(self.main_data.keys())
    
    def get_metrics(self, file_name):
        """Get available metrics for the specified file."""
        if file_name not in self.main_data:
            return []
        
        # Get all available metric types for this file
        metrics = []
        
        # The main_data[file_name] structure contains metric type keys like WMC, NOC, etc.
        for metric_type, df in self.main_data[file_name].items():
            # Each df is a DataFrame with class names as columns
            for column in df.columns:
                if column != 'pr_number':  # Skip non-metric columns
                    metrics.append(f"{metric_type}_{column}")
        
        # If no metrics found but we know they should exist, use default metrics
        if not metrics and file_name in self.main_data:
            # Add default metrics with placeholder class
            metrics = [f"{metric}_Class1" for metric in self.all_metrics]
            print(f"[OO MANAGER] No specific metrics found, using defaults: {metrics}")
        
        return metrics
    
    def get_filtered_df(self, file_name, selected_metrics):
        """Get a DataFrame with only the selected metrics for the specified file."""
        if file_name not in self.main_data:
            return None
        
        # Create a new DataFrame to hold the selected metrics
        result_df = None
        
        for full_metric in selected_metrics:
            # Split the metric name to get the type and class name
            parts = full_metric.split('_', 1)
            if len(parts) != 2:
                continue
                
            metric_type, class_name = parts
            
            # Check if this metric type exists for the file
            if metric_type not in self.main_data[file_name]:
                continue
                
            # Get the DataFrame for this metric type
            df = self.main_data[file_name][metric_type]
            
            # Check if the class exists in this metric
            if class_name not in df.columns:
                continue
                
            # Extract the data for this specific class
            if result_df is None:
                result_df = pd.DataFrame(index=df.index)
            
            # Add the metric data to the result DataFrame
            result_df[full_metric] = df[class_name]
        
        return result_df
    
    def get_pr_overlay_df(self, file_name, selected_metrics):
        """Get PR overlay data for the specified file and metrics."""
        if not self.pr_data_loader:
            return None
        
        # Get all available PR data for this file
        file_data = self.pr_data_loader.get_file_data(file_name)
        if not file_data:
            return None
            
        # Create a new DataFrame to hold the selected metrics
        result_df = None
        
        for full_metric in selected_metrics:
            # Split the metric name to get the type and class name
            parts = full_metric.split('_', 1)
            if len(parts) != 2:
                continue
                
            metric_type, class_name = parts
            
            # Check if this metric type exists for the file
            if metric_type not in file_data:
                continue
                
            # Get the DataFrame for this metric type
            df = file_data[metric_type]
            
            # Check if the class exists in this metric
            if class_name not in df.columns:
                continue
                
            # Extract the data for this specific class
            if result_df is None:
                result_df = pd.DataFrame(index=df.index)
            
            # Add the metric data to the result DataFrame
            result_df[full_metric] = df[class_name]
            
            # Add PR number if available
            if 'pr_number' in df.columns and 'pr_number' not in result_df.columns:
                result_df['pr_number'] = df['pr_number']
        
        # Try to map commit SHAs to dates if the indices are not already dates
        if result_df is not None and not all(isinstance(idx, pd.Timestamp) for idx in result_df.index):
            # Create a new DataFrame with dates where possible
            df_with_dates = pd.DataFrame(result_df)
            
            # If indexes are SHAs, try to map them to dates
            new_indices = []
            for idx in result_df.index:
                if isinstance(idx, str) and idx in self.main_data_by_sha:
                    new_indices.append(self.main_data_by_sha[idx])
                else:
                    # Keep original if not found
                    new_indices.append(idx)
                    
            df_with_dates.index = new_indices
            return df_with_dates
        
        return result_df


# Layout for OO Metrics Visualization
layout = html.Div([
    html.H2("Object-Oriented Metrics Visualization"),
    html.Div(id="oo-loading-info", style={"color": "green"}),
    dcc.Dropdown(id="oo-file-dropdown", placeholder="Select a file"),
    dcc.Dropdown(id="oo-metric-dropdown", placeholder="Select metrics", multi=True),
    dcc.Checklist(
        id="oo-show-pull-requests",
        options=[{"label": "Show Pull Request Overlays", "value": "show"}],
        value=[],
        style={"marginTop": "10px"}
    ),
    html.Button("Debug PR Data", id="oo-debug-pr-button", style={"marginTop": "10px"}),
    html.Div(id="oo-pr-debug-output"),
    html.Div(id="oo-graphs"),
    
    # Add refresh information and auto-refresh interval
    html.Div([
        html.Span("Last refreshed: ", style={"fontWeight": "bold"}),
        html.Span(id="oo-last-refresh-time", children="Never"),
        html.Button("Refresh Now", id="oo-refresh-button", style={"marginLeft": "10px"})
    ], style={"marginTop": "20px", "marginBottom": "10px"}),
    
    # Interval component for auto-refresh
    dcc.Interval(
        id='oo-auto-refresh-interval',
        interval=60*1000,  # in milliseconds, 60 seconds = 1 minute
        n_intervals=0
    )
])

# === Callbacks ===
@callback(
    Output("oo-loading-info", "children"),
    Output("oo-file-dropdown", "options"),
    Output("oo-last-refresh-time", "children"),
    Input("repo-store", "data"),
    Input("token-store", "data"),
    Input("oo-auto-refresh-interval", "n_intervals"),
    Input("oo-refresh-button", "n_clicks")
)
def update_oo_file_dropdown(repo_name, __, n_intervals, n_clicks):
    """Update file dropdown with available files from the repository."""
    if not repo_name:
        return "No repository selected", [], "Never"
    try:
        manager = OODataManager.get_instance()
        data_refreshed = manager.load_data(repo_name)
        files = manager.get_files()
        
        if not files:
            return f"No OO metrics found for {repo_name}", [], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        refresh_message = "Data up to date"
        if data_refreshed:
            refresh_message = f"Data refreshed! Found {len(files)} files"
            
        return refresh_message, [{"label": f, "value": f} for f in files], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return f"Error loading files: {str(e)}", [], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@callback(
    Output("oo-metric-dropdown", "options"),
    Output("oo-loading-info", "children", allow_duplicate=True),
    Input("oo-file-dropdown", "value"),
    State("repo-store", "data"),
    State("oo-loading-info", "children"),
    prevent_initial_call=True
)
def update_oo_metric_dropdown(file_name, repo_name, current_info):
    """Update metric dropdown with available metrics for the selected file."""
    if not file_name or not repo_name:
        return [], current_info
    try:
        manager = OODataManager.get_instance()
        metrics = manager.get_metrics(file_name)
        
        # Add debug info
        debug_info = f"{current_info}<br>Found {len(metrics)} metrics for {file_name}"
        if not metrics:
            debug_info += "<br><span style='color:orange'>No metrics found! Check data structure.</span>"
            # Print the structure of the data for debugging
            if file_name in manager.main_data:
                keys = list(manager.main_data[file_name].keys())
                debug_info += f"<br>Available metric types: {keys}"
                
                # Print first metric type structure
                if keys:
                    first_key = keys[0]
                    if isinstance(manager.main_data[file_name][first_key], pd.DataFrame):
                        cols = list(manager.main_data[file_name][first_key].columns)
                        debug_info += f"<br>Columns in {first_key}: {cols}"
        
        return [{"label": m, "value": m} for m in metrics], debug_info
    except Exception as e:
        error_msg = f"Error getting OO metrics: {str(e)}"
        print(error_msg)
        return [], f"{current_info}<br><span style='color:red'>{error_msg}</span>"

@callback(
    Output("oo-pr-debug-output", "children"),
    Input("oo-debug-pr-button", "n_clicks"),
    State("oo-file-dropdown", "value"),
    State("repo-store", "data"),
    prevent_initial_call=True
)
def debug_oo_pr_data(n_clicks, file_name, repo_name):
    """Debug PR data for the selected file."""
    if n_clicks is None or not file_name or not repo_name:
        return html.Div("No data to debug")
    
    try:
        manager = OODataManager.get_instance()
        
        # Get PR data for the selected file
        if not manager.pr_data_loader:
            return html.Div("No PR data available", style={"color": "red"})
            
        file_data = manager.pr_data_loader.get_file_data(file_name)
        if not file_data:
            return html.Div(f"No PR data for file: {file_name}", style={"color": "orange"})
            
        # Create debug output
        debug_info = [html.H4("PR Data Debug Information")]
        
        # For each metric type
        for metric_type, df in file_data.items():
            if df is None or df.empty:
                debug_info.append(html.Div(f"No data for metric type: {metric_type}", 
                                     style={"color": "orange"}))
                continue
                
            debug_info.append(html.H5(f"Metric Type: {metric_type}"))
            debug_info.append(html.Div(f"Number of data points: {len(df)}"))
            debug_info.append(html.Div(f"Columns: {', '.join(df.columns)}"))
            debug_info.append(html.Div(f"Index type: {type(df.index[0]) if len(df.index) > 0 else 'N/A'}"))
            
            # Sample data (first 5 rows)
            if len(df) > 0:
                debug_info.append(html.H6("Sample Data (first 5 rows)"))
                sample_data = df.head(5).reset_index()
                
                # Create table rows
                table_rows = [html.Tr([html.Th(col) for col in sample_data.columns])]
                for _, row in sample_data.iterrows():
                    table_rows.append(html.Tr([html.Td(str(row[col])) for col in sample_data.columns]))
                    
                debug_info.append(html.Table(table_rows, 
                                      style={"border": "1px solid black", "marginBottom": "20px"}))
            
        return html.Div(debug_info)
    except Exception as e:
        return html.Div(f"Error debugging PR data: {str(e)}", style={"color": "red"})

@callback(
    Output("oo-graphs", "children"),
    Input("oo-file-dropdown", "value"),
    Input("oo-metric-dropdown", "value"),
    Input("oo-show-pull-requests", "value"),
    Input("oo-auto-refresh-interval", "n_intervals"),
    Input("oo-refresh-button", "n_clicks"),
    State("repo-store", "data")
)
def update_oo_graphs(file_name, selected_metrics, show_pr_value, n_intervals, n_clicks, repo_name):
    """Generate and update graphs for the selected file and metrics."""
    if not file_name or not selected_metrics or not repo_name:
        return []
    
    # Check for data refreshes on auto interval or manual refresh
    manager = OODataManager.get_instance()
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
            if metric not in df_main.columns:
                debug_info.append(html.Div(f"Metric {metric} not found in data", 
                                     style={"color": "orange"}))
                continue
                
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
            
            # Parse metric name to create a better title
            metric_parts = metric.split('_', 1)
            metric_type = metric_parts[0] if len(metric_parts) > 0 else metric
            class_name = metric_parts[1] if len(metric_parts) > 1 else ""
            title = f'{metric_type} for {class_name}' if class_name else metric
            
            # Update layout with improved datetime handling
            fig.update_layout(
                title=title,
                xaxis_title='Date',
                yaxis_title=metric_type,
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
                        hover_text = []
                        for i, idx in enumerate(df_pr.index):
                            pr_num = df_pr['pr_number'].iloc[i] if 'pr_number' in df_pr.columns else "N/A"
                            hover_text.append(f"PR: {pr_num}<br>Date: {idx}")
                            
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
                            text=hover_text,
                            hovertemplate='%{text}<br>Value: %{y:.2f}<extra></extra>'
                        ))
                    else:
                        # Fallback for non-datetime indices
                        # Create hover text with PR info
                        hover_text = []
                        for i, idx in enumerate(df_pr.index):
                            pr_num = df_pr['pr_number'].iloc[i] if 'pr_number' in df_pr.columns else "N/A"
                            hover_text.append(f"PR: {pr_num}<br>SHA: {idx}")
                            
                        # Use the first date in the main data as a temporary placeholder
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
                            text=hover_text,
                            hovertemplate='%{text}<br>Value: %{y:.2f}<extra></extra>'
                        ))
                        
                        debug_info.append(html.Div("Warning: PR data does not have proper datetime indices", 
                                              style={"color": "orange"}))
        
            figures.append(fig)
        
        # Return debug info and figures
        return debug_info + [dcc.Graph(figure=fig) for fig in figures]
    
    except Exception as e:
        return html.Div(f"Error generating graphs: {str(e)}", style={"color": "red"})