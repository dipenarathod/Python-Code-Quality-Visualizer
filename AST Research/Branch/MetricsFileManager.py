import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import tempfile
from multiprocessing.pool import ThreadPool
import json
from datetime import datetime
from typing import Dict, Any, Optional
from github import Repository, Branch, GitTree, GitTreeElement
from pathlib import Path

class MetricsFileManager:
    def __init__(self, repo: Repository, metric_type: str, branch_name: str = "main", output_dir: str = "metrics"):
        self.repo = repo
        self.metric_type = metric_type
        self.branch_name = branch_name

        # File naming includes branch and metric type
        self.file_name = f"{self.metric_type}_Metrics.json"
        self.repo_safe_name = repo.full_name.replace("/", "_")
        self.output_dir = Path(output_dir) / self.repo_safe_name
        self.local_file_path = self.output_dir / self.file_name
        self.metrics: Dict = {}
        self.file_sha = None

    def load_metrics(self, tree) -> None:
        """Load metrics data from GitHub metrics folder or local."""
        try:
            metrics_folder = "metrics"
            file_path = f"{metrics_folder}/{self.file_name}"
        
            try:
                # Primary attempt: load from GitHub metrics folder
                file_content = self.repo.get_contents(file_path, ref=self.branch_name)
                self.metrics = json.loads(file_content.decoded_content.decode('utf-8'))
                self.file_sha = file_content.sha
                print(f"Loaded {file_path} from GitHub.")
            except Exception:
                # Secondary attempt: try old path directly in repo root
                try:
                    file_content = self.repo.get_contents(self.file_name, ref=self.branch_name)
                    self.metrics = json.loads(file_content.decoded_content.decode('utf-8'))
                    self.file_sha = file_content.sha
                    print(f"Loaded {self.file_name} from GitHub root (legacy location).")
                except Exception:
                    # Tertiary attempt: search tree if provided
                    if tree:
                        # Look for file in metrics folder
                        match = next((item for item in tree if item.path == file_path), None)
                        if not match:
                            # Look for file in root (legacy location)
                            match = next((item for item in tree if item.path == self.file_name), None)
                        
                        if match:
                            file_content = self.repo.get_contents(match.path, ref=self.branch_name)
                            self.metrics = json.loads(file_content.decoded_content.decode('utf-8'))
                            self.file_sha = file_content.sha
                            print(f"Loaded {match.path} from tree search.")
                            return

                    # Fallback: load from local
                    if os.path.exists(self.local_file_path):
                        with open(self.local_file_path, 'r', encoding='utf-8') as f:
                            self.metrics = json.load(f)
                        print(f"Loaded {self.file_name} from local file.")
                    else:
                        print(f"No existing metrics found for {self.file_name}. Initializing.")
                        self.metrics = {}
        except Exception as e:
            print(f"Error loading {self.file_name}: {e}")
            self.metrics = {}

    def update_metrics(self, new_metrics: Dict) -> None:
        """Update the metrics dictionary with new data, merging with existing data."""
        if isinstance(new_metrics, dict):
            # Deep merge the dictionaries
            self._deep_merge(self.metrics, new_metrics)
        else:
            print("Warning: new_metrics should be a dictionary")

    def _deep_merge(self, target: Dict, source: Dict) -> None:
        """Recursively merge source dictionary into target dictionary."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                self._deep_merge(target[key], value)
            else:
                # Overwrite or add new key-value pairs
                target[key] = value

    def add_metric(self, key: str, value: any) -> None:
        """Add a single metric entry."""
        self.metrics[key] = value

    def add_nested_metric(self, *keys, value) -> None:
        """Add a metric at a nested path. Example: add_nested_metric('commits', '2024-01', 'count', value=42)"""
        current = self.metrics
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                # If existing value is not a dict, convert it
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def save_local_metrics(self) -> None:
        """Save metrics to a local JSON file, merging with existing data."""
        try:
            # Ensure the directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # Load existing data from local file if it exists
            existing_data = {}
            if os.path.exists(self.local_file_path):
                try:
                    with open(self.local_file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception as e:
                    print(f"Warning: Could not load existing local file for merging: {e}")
            
            # Merge existing data with current metrics
            merged_data = existing_data.copy()
            self._deep_merge(merged_data, self.metrics)
            
            # Save the merged data
            with open(self.local_file_path, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, indent=4)
            print(f"Saved metrics locally to {self.local_file_path}")
            
            # Update our internal metrics to reflect the merged state
            self.metrics = merged_data
            
        except Exception as e:
            print(f"Failed to save metrics locally: {e}")

    def save_metrics(self) -> None:
        """Save metrics to GitHub repo in a 'metrics' folder, merging with existing data."""
        try:
            # Define path to include the metrics folder
            metrics_folder = "metrics"
            file_path = f"{metrics_folder}/{self.file_name}"
            
            # Load existing data from GitHub if available
            existing_data = {}
            existing_sha = None
            
            try:
                # Try to get existing file content for merging
                file_content = self.repo.get_contents(file_path, ref=self.branch_name)
                existing_data = json.loads(file_content.decoded_content.decode('utf-8'))
                existing_sha = file_content.sha
            except Exception:
                # Try legacy location
                try:
                    file_content = self.repo.get_contents(self.file_name, ref=self.branch_name)
                    existing_data = json.loads(file_content.decoded_content.decode('utf-8'))
                    existing_sha = file_content.sha
                except Exception:
                    # No existing file found, will create new
                    pass
            
            # Merge existing data with current metrics
            merged_data = existing_data.copy()
            self._deep_merge(merged_data, self.metrics)
            
            content = json.dumps(merged_data, indent=4)
            
            # Check if metrics folder exists, create if not
            try:
                # Try to get contents of the metrics folder
                self.repo.get_contents(metrics_folder, ref=self.branch_name)
            except Exception:
                # Folder doesn't exist, create it
                try:
                    self.repo.create_file(
                        path=f"{metrics_folder}/.gitkeep",
                        message=f"Create metrics folder",
                        content="",
                        branch=self.branch_name
                    )
                    print(f"Created metrics folder in GitHub.")
                except Exception as e:
                    # If folder already exists or other error
                    print(f"Note: {e}")
            
            # Now save the merged metrics file
            if existing_sha:
                response = self.repo.update_file(
                    path=file_path,
                    message=f"Update {self.file_name} (merged with existing data)",
                    content=content,
                    sha=existing_sha,
                    branch=self.branch_name
                )
                self.file_sha = response['content'].sha
                print(f"Updated {file_path} in GitHub with merged data.")
            else:
                # Create new file
                response = self.repo.create_file(
                    path=file_path,
                    message=f"Create {self.file_name}",
                    content=content,
                    branch=self.branch_name
                )
                self.file_sha = response['content'].sha
                print(f"Created {file_path} in GitHub.")
            
            # Update our internal metrics to reflect the merged state
            self.metrics = merged_data
            
        except Exception as e:
            print(f"Error saving {self.file_name} to GitHub: {e}")

    def reload_and_merge_metrics(self, new_metrics: Dict = None) -> None:
        """Reload metrics from source and optionally merge with new metrics before saving."""
        # Store current metrics temporarily
        current_metrics = self.metrics.copy()
        
        # Reload from source
        self.load_metrics(None)
        
        # Merge back the current metrics
        self._deep_merge(self.metrics, current_metrics)
        
        # Merge any additional new metrics
        if new_metrics:
            self._deep_merge(self.metrics, new_metrics)

    def update_file_metrics(self, commit_date: str, file_path: str, metrics_data: Dict) -> None:
        """Add or update metrics for a file at a specific commit date."""
        self.metrics.setdefault(commit_date, {})[file_path] = metrics_data

    def update_commit_metrics(self, commit_sha: str, commit_date: str, metrics_data: Dict) -> None:
        """Add or update metrics for a commit (new commit-based structure)."""
        self.metrics[commit_sha] = {
            "date": commit_date,
            "metrics": metrics_data
        }

    def update_branch_info(self, commit_sha: str, branch_info: Dict) -> None:
        """Track branch-level commit info."""
        self.metrics.setdefault("branch_info", {})[commit_sha] = branch_info

    def needs_recalculation_for_commit(self, commit_sha: str) -> bool:
        """Check if the metrics for a commit already exist."""
        # Check if this commit SHA already exists in the metrics
        return commit_sha not in self.metrics

    def get_metrics_path(self) -> str:
        return self.local_file_path
        
    def load_existing_metrics(self) -> None:
        """Load existing metrics from local file only (no GitHub)."""
        if os.path.exists(self.local_file_path):
            try:
                with open(self.local_file_path, 'r', encoding='utf-8') as f:
                    self.metrics = json.load(f)
                print(f"Loaded existing metrics from {self.local_file_path}")
            except Exception as e:
                print(f"Failed to load existing metrics: {e}")
                self.metrics = {}
        else:
            print(f"No local metrics file found for {self.file_name}")
            self.metrics = {}

    def clean_malformed_data(self) -> None:
        """Clean up malformed data where both date-based and SHA-based keys exist."""
        if not self.metrics:
            return
            
        # Identify date-based keys (ISO format timestamps)
        date_keys = []
        sha_keys = []
        
        for key in self.metrics.keys():
            if isinstance(key, str):
                if key == "branch_info":
                    continue
                # Check if it looks like an ISO timestamp
                elif "T" in key and ":" in key and ("-" in key or "+" in key):
                    date_keys.append(key)
                # Check if it looks like a SHA (40 char hex string)
                elif len(key) == 40 and all(c in '0123456789abcdef' for c in key.lower()):
                    sha_keys.append(key)
                else:
                    # Assume it's a SHA if it's not clearly a date
                    sha_keys.append(key)
        
        # If we have both types, prefer SHA-based structure (remove date-based)
        if date_keys and sha_keys:
            print(f"Found mixed data structure. Removing {len(date_keys)} date-based keys.")
            for date_key in date_keys:
                print(f"Removing malformed date-based key: {date_key}")
                del self.metrics[date_key]
        
        # Also clean up any entries that don't have proper structure
        keys_to_remove = []
        for key, value in self.metrics.items():
            if key == "branch_info":
                continue
            if not isinstance(value, dict) or ("date" not in value and "metrics" not in value):
                # This might be legacy data, check if it should be converted
                if isinstance(value, dict) and all(isinstance(v, dict) for v in value.values()):
                    # This looks like old file-based metrics, convert it
                    print(f"Converting legacy data structure for key: {key}")
                    # We can't easily convert without date info, so we'll remove it
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            print(f"Removing malformed entry: {key}")
            del self.metrics[key]

    def set_metrics_safely(self, new_metrics: Dict) -> None:
        """Safely set metrics by merging with existing data instead of overwriting."""
        if isinstance(new_metrics, dict):
            # Instead of direct assignment, merge the new metrics
            self._deep_merge(self.metrics, new_metrics)
        else:
            print("Warning: new_metrics should be a dictionary")
