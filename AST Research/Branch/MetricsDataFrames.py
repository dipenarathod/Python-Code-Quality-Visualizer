import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from datetime import datetime
import json
import pandas as pd

class MetricsDataFrames:
    def __init__(self, json_path=None,metrics_dictionary=None, metric_type=""):
        self.json_path = json_path
        self.metric_type = metric_type.lower()
        if(metrics_dictionary is not None):
            self.json_data = metrics_dictionary
        else:
            self.json_data = self._load_json()
        # self.file_names = list(next(iter(self.json_data.values()))["metrics"].keys())
        # Collect all unique file names across all SHAs
        all_files = set()
        for commit in self.json_data.values():
            if isinstance(commit, dict) and "metrics" in commit:
                all_files.update(commit["metrics"].keys())
        self.file_names = list(all_files)

        self.dataframes = self._process_metrics()

    def _load_json(self) -> dict:
        with open(self.json_path, 'r') as f:
            return json.load(f)

    def _parse_datetime(self, sha):
        return pd.to_datetime(self.json_data[sha]['date'])

    def _process_metrics(self):
        processor = {
            'halstead': self._process_halstead,
            'oo': self._process_oo,
            'traditional': self._process_traditional
        }.get(self.metric_type)

        if processor is None:
            raise ValueError(f"Unsupported metric type: {self.metric_type}")
        
        return {file_name: processor(file_name) for file_name in self.file_names}

    def _process_halstead(self, file_name):
        dates, metrics_data = [], []
        for sha, commit_data in self.json_data.items():
            file_metrics = commit_data["metrics"]
            if file_name in file_metrics:
                dates.append(self._parse_datetime(sha))
                metrics_data.append(file_metrics[file_name])
        return pd.DataFrame(metrics_data, index=dates)

    def _process_oo(self, file_name):
        metric_dfs = {}

        # Find first commit that contains this file
        sample_data = None
        for commit in self.json_data.values():
            if "metrics" in commit and file_name in commit["metrics"]:
                sample_data = commit["metrics"][file_name]
                break

        if sample_data is None:
            raise ValueError(f"No data found for file: {file_name}")

        metric_types = list(sample_data.keys())

        for metric_type in metric_types:
            dates, class_data = [], {}
            all_class_names = {
                class_name
                for sha, commit_data in self.json_data.items()
                if file_name in commit_data["metrics"]
                and metric_type in commit_data["metrics"][file_name]
                for class_name in commit_data["metrics"][file_name][metric_type].keys()
            }

            for sha, commit_data in self.json_data.items():
                file_metrics = commit_data["metrics"]
                if file_name in file_metrics:
                    date = self._parse_datetime(sha)
                    metric_values = file_metrics[file_name].get(metric_type, {})
                    dates.append(date)
                    current_data = {name: 0 for name in all_class_names}
                    current_data.update(metric_values)
                    for name, value in current_data.items():
                        class_data.setdefault(name, []).append(value)

            metric_dfs[metric_type] = pd.DataFrame(class_data, index=dates)

        return metric_dfs

    def _process_traditional(self, file_name):
        flat_metrics = ['LOC', 'Length of Identifier']
        nested_metrics = ['Fan in', 'Fan out', 'CC']
        dates = []

        flat_data = {metric: [] for metric in flat_metrics}
        nested_keys = {metric: set() for metric in nested_metrics}

        # Collect all nested keys (e.g., method names)
        for sha, commit_data in self.json_data.items():
            file_metrics = commit_data["metrics"]
            if file_name in file_metrics:
                for metric in nested_metrics:
                    if metric in file_metrics[file_name]:
                        nested_keys[metric].update(file_metrics[file_name][metric].keys())

        nested_dfs_data = {
            metric: {key: [] for key in nested_keys[metric]}
            for metric in nested_metrics
        }

        for sha, commit_data in self.json_data.items():
            file_metrics = commit_data["metrics"]
            if file_name in file_metrics:
                date = self._parse_datetime(sha)
                dates.append(date)

                for metric in flat_metrics:
                    flat_data[metric].append(file_metrics[file_name].get(metric, None))

                for metric in nested_metrics:
                    current_data = file_metrics[file_name].get(metric, {})
                    for key in nested_keys[metric]:
                        nested_dfs_data[metric][key].append(current_data.get(key, 0))

        # Build final result dict with one DataFrame per metric
        result = {}

        for metric in flat_metrics:
            result[metric] = pd.DataFrame({metric: flat_data[metric]}, index=dates)

        for metric in nested_metrics:
            if nested_dfs_data[metric]:
                result[metric] = pd.DataFrame(nested_dfs_data[metric], index=dates)

        return result

    def get_file_data(self, file_name: str):
        return self.dataframes.get(file_name)

    def get_all_files(self):
        return list(self.dataframes.keys())


# Example usage
# def main():
#     # Example for traditional metrics
#     traditional_dfs = load_and_process_metrics('traditional_metrics.json', 'traditional')
    
#     # Print example outputs for HalsteadMetricsClass.py
#     file_name = 'HalsteadMetricsClass.py'
#     if file_name in traditional_dfs:
#         print("\nFlat metrics:")
#         print(traditional_dfs[file_name]['flat_metrics'])
        
#         print("\nFan in metrics:")
#         print(traditional_dfs[file_name]['Fan in'])
        
#         print("\nCyclomatic Complexity (CC):")
#         print(traditional_dfs[file_name]['CC'])

# if __name__ == "__main__":
#     main()