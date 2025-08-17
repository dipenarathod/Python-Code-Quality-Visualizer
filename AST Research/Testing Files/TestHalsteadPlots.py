import json
import pandas as pd
from pathlib import Path
from Branch.MetricsDataFrames import MetricsDataFrames
from Branch.MetricsPlotter import MetricsPlotter
import plotly.io as pio
from datetime import datetime

pio.renderers.default = "browser"


metrics_root = Path("metrics")

halstead_file_path = metrics_root / "halstead_metrics.json"
traditional_file_path = metrics_root / "traditional_metrics.json"
oo_file_path = metrics_root / "oo_metrics.json"

halstead_df_obj = MetricsDataFrames(halstead_file_path, "halstead")
for file_name, df in halstead_df_obj.dataframes.items():
    plotter = MetricsPlotter(df, "halstead")
    halstead_figures = plotter.plot_metrics()
    for fig in halstead_figures:
        fig.show()

# Plot Traditional metrics
traditional_df_obj = MetricsDataFrames(traditional_file_path, "traditional")
for file_name, metrics_dict in traditional_df_obj.dataframes.items():
    plotter = MetricsPlotter(metrics_dict, "traditional")
    traditional_figures = plotter.plot_metrics()
    for fig in traditional_figures:
        fig.show()

# Plot OO metrics
oo_df_obj = MetricsDataFrames(oo_file_path, "oo")
for file_name, metrics_dict in oo_df_obj.dataframes.items():
    plotter = MetricsPlotter(metrics_dict, "oo")
    oo_figures = plotter.plot_metrics()
    for fig in oo_figures:
        fig.show()
