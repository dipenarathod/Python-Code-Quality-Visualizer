import json
from pathlib import Path
import pandas as pd


class PullRequestMetricsDataFrames:
    def __init__(self, json_path: str, metric_type: str):
        self.json_path = json_path
        self.metric_type = metric_type.lower()
        self.json_data = self._load_json()
        self.file_names = self._find_first_file_names()
        self.dataframes = self._process_metrics()

    def _load_json(self) -> dict:
        with open(self.json_path, 'r') as f:
            return json.load(f)

    def _parse_datetime(self, pr_data):
        """
        Parse datetime from PR data.
        Use pr_date if available, otherwise fall back to other methods.
        """
        # First try to get the pr_date field
        if "pr_date" in pr_data:
            return pd.to_datetime(pr_data["pr_date"])
        
        # Fall back to date field if pr_date is not available
        elif "date" in pr_data:
            return pd.to_datetime(pr_data["date"])
        
        # If no direct date, we need to look it up from main branch data
        commit_sha = pr_data.get("commit_sha")
        
        # Return commit_sha as a placeholder
        # In a real implementation, you'd do something like:
        # return self.main_branch_data.get(commit_sha, {}).get('date')
        return commit_sha

    def _find_first_file_names(self):
        for pr_data in self.json_data.values():
            files = pr_data.get("files")
            if files:
                return list(files.keys())
        raise ValueError("No valid PR data with 'files' found.")

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
        indices, metrics_data = [], []
        for pr_number, pr_data in self.json_data.items():
            files = pr_data.get("files", {})
            if file_name in files:
                index = self._parse_datetime(pr_data)
                indices.append(index)
                metrics_data.append(files[file_name])
        
        df = pd.DataFrame(metrics_data, index=indices)
        
        # Add pr_number as a column if available
        pr_numbers = []
        for pr_number, pr_data in self.json_data.items():
            files = pr_data.get("files", {})
            if file_name in files:
                # Use the pr_number from the data if available, otherwise use the key
                pr_numbers.append(pr_data.get("pr_number", pr_number))
        
        if indices and len(indices) == len(pr_numbers):
            df['pr_number'] = pr_numbers
            
        return df

    def _process_oo(self, file_name):
        metric_dfs = {}
        sample_file = next(iter(self.json_data.values())).get("files", {}).get(file_name, {})
        metric_types = list(sample_file.keys())

        for metric_type in metric_types:
            indices, class_data = [], {}
            pr_numbers = []

            all_class_names = {
                class_name
                for pr_data in self.json_data.values()
                if file_name in pr_data.get("files", {})
                and isinstance(pr_data["files"][file_name].get(metric_type), dict)
                for class_name in pr_data["files"][file_name][metric_type].keys()
            }

            for pr_number, pr_data in self.json_data.items():
                file_metrics = pr_data.get("files", {}).get(file_name, {})
                metric_values = file_metrics.get(metric_type, {})
                if isinstance(metric_values, dict):
                    index = self._parse_datetime(pr_data)
                    indices.append(index)
                    pr_numbers.append(pr_data.get("pr_number", pr_number))
                    current_data = {name: 0 for name in all_class_names}
                    current_data.update(metric_values)
                    for name, value in current_data.items():
                        class_data.setdefault(name, []).append(value)

            df = pd.DataFrame(class_data, index=indices)
            if indices and len(indices) == len(pr_numbers):
                df['pr_number'] = pr_numbers
            metric_dfs[metric_type] = df
            
        return metric_dfs

    def _process_traditional(self, file_name):
        flat_metrics = ['LOC', 'Length of Identifier']
        nested_metrics = ['Fan in', 'Fan out', 'CC']
        indices, flat_data = [], {metric: [] for metric in flat_metrics}
        pr_numbers = []
        nested_keys = {metric: set() for metric in nested_metrics}

        for pr_data in self.json_data.values():
            file_metrics = pr_data.get("files", {}).get(file_name, {})
            for metric in nested_metrics:
                nested_keys[metric].update(file_metrics.get(metric, {}).keys())

        nested_dfs = {
            metric: {key: [] for key in nested_keys[metric]}
            for metric in nested_metrics
        }

        for pr_number, pr_data in self.json_data.items():
            file_metrics = pr_data.get("files", {}).get(file_name, {})
            if not file_metrics:
                continue
                
            index = self._parse_datetime(pr_data)
            indices.append(index)
            pr_numbers.append(pr_data.get("pr_number", pr_number))

            for metric in flat_metrics:
                flat_data[metric].append(file_metrics.get(metric))

            for metric in nested_metrics:
                current_data = file_metrics.get(metric, {})
                for key in nested_keys[metric]:
                    nested_dfs[metric][key].append(current_data.get(key, 0))

        result = {}
        if indices:
            flat_df = pd.DataFrame(flat_data, index=indices)
            if len(indices) == len(pr_numbers):
                flat_df['pr_number'] = pr_numbers
            result['flat_metrics'] = flat_df
            
            for metric in nested_metrics:
                if nested_dfs[metric]:
                    nested_df = pd.DataFrame(nested_dfs[metric], index=indices)
                    if len(indices) == len(pr_numbers):
                        nested_df['pr_number'] = pr_numbers
                    result[metric] = nested_df
                    
        return result
        
    def get_file_data(self, file_name: str):
        return self.dataframes.get(file_name)

    def get_all_files(self):
        return list(self.dataframes.keys())

