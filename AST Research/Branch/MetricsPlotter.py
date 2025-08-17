import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
#from MetricsDataFrames import load_and_process_metrics


class MetricsPlotter:
    def __init__(self, metrics_df, metric_type):
        self.metrics_df = metrics_df
        self.metric_type = metric_type.lower()
        self.plot_functions = {
            'halstead': self._plot_flat_metrics,
            'traditional': self._plot_traditional_metrics,
            'oo': self._plot_oo_metrics
        }

    def plot_metrics(self):
        plot_func = self.plot_functions.get(self.metric_type)
        if not plot_func:
            raise ValueError(f"Unknown metric type: {self.metric_type}")
        return plot_func()

    def _plot_flat_metrics(self):
        figures = []
        for metric in self.metrics_df.columns:
            x = self.metrics_df.index
            y = self.metrics_df[metric]
            fig = go.Figure(data=[go.Scatter(x=x, y=y, mode='lines+markers', name=metric)])
            fig.update_layout(
                title=f"{self.metric_type.capitalize()} - {metric}",
                xaxis_title="Date",
                yaxis_title="Value",
                template="plotly_white"
            )
            figures.append(fig)
        return figures

    def _plot_traditional_metrics(self):
        figures = []
        for metric_type, df in self.metrics_df.items():
            if metric_type == 'flat_metrics':
                for metric in df.columns:
                    x = df.index
                    y = df[metric]
                    fig = go.Figure(data=[go.Scatter(x=x, y=y, mode='lines+markers', name=metric)])
                    fig.update_layout(
                        title=f"Traditional - {metric}",
                        xaxis_title="Date",
                        yaxis_title="Value",
                        template="plotly_white"
                    )
                    figures.append(fig)
            else:
                for column in df.columns:
                    x = df.index
                    y = df[column]
                    fig = go.Figure(data=[go.Scatter(x=x, y=y, mode='lines+markers', name=column)])
                    fig.update_layout(
                        title=f"Traditional - {metric_type} - {column}",
                        xaxis_title="Date",
                        yaxis_title="Value",
                        template="plotly_white"
                    )
                    figures.append(fig)
        return figures

    def _plot_oo_metrics(self):
        figures = []
        for metric_type, df in self.metrics_df.items():
            for column in df.columns:
                x = df.index
                y = df[column]
                fig = go.Figure(data=[go.Scatter(x=x, y=y, mode='lines+markers', name=column)])
                fig.update_layout(
                    title=f"OO - {metric_type} - {column}",
                    xaxis_title="Date",
                    yaxis_title="Value",
                    template="plotly_white"
                )
                figures.append(fig)
        return figures



