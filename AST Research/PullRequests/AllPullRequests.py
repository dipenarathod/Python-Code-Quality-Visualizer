from collections.abc import Set
from pathlib import Path
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from github import Repository
from typing import Any, Dict, List
from PullRequestMetrics import PullRequestMetrics
import json
import os
from concurrent.futures import ThreadPoolExecutor

class AllPullRequestMetrics:
    def __init__(self, repo: Repository, save_online : bool = False, save: bool = False, output_dir: str = "pull_request_metrics"):
        self.repo = repo
        self.save_online = save_online
        self.save = save
        self.pull_request_metrics: List[PullRequestMetrics] = []
        self.repo_name = repo.full_name  # e.g., "owner/repo"
        self.repo_safe_name = self.repo_name.replace('/', '_')
        self.output_dir = Path(output_dir) / self.repo_safe_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.processed_pr_numbers = []  # Track the PR numbers processed in this run

    def calculate_all(self, skip_pr_numbers: Set[int] = None, pr_state: str = "open"):
        """
        Calculate metrics for pull requests.
        
        Args:
            skip_pr_numbers: Set of PR numbers to skip (already processed)
            pr_state: State of PRs to process ('open', 'closed', or 'all')
        """
        skip_pr_numbers = skip_pr_numbers or set()
        
        # Get pull requests based on state
        pull_requests = self.repo.get_pulls(state=pr_state)
        
        # Counter for tracking processed and skipped PRs
        processed_count = 0
        skipped_count = 0
        
        for pr in pull_requests:
            if pr.number in skip_pr_numbers:
                skipped_count += 1
                continue
                
            pr_metrics = PullRequestMetrics(self.repo, pr, save_online=False, save=False)
            pr_metrics.calculate_metrics()
            self.pull_request_metrics.append(pr_metrics)
            self.processed_pr_numbers.append(pr.number)
            processed_count += 1
            
        print(f"Finished processing {processed_count} new PRs. Skipped {skipped_count} already processed PRs.")

    def get_processed_pr_numbers(self) -> List[int]:
        """Return the list of PR numbers processed in this run."""
        return self.processed_pr_numbers

    def save_by_metric_type(self):
        """Save metrics split by metric type (Halstead, Traditional, OO, etc) into per-repo folders.
        If save_online is True, also commits the metrics to the GitHub repository."""
        # Only proceed if there are PRs to save
        if not self.pull_request_metrics:
            print("No new PRs to save.")
            return
            
        metric_type_data = {}
        # Organize data
        for pr_metrics in self.pull_request_metrics:
            pr_data = pr_metrics.get_metrics()
            pr_number = pr_data["pr_number"]
            files = pr_data["files"]
            for file_name, metrics_per_file in files.items():
                for metric_type, metric_values in metrics_per_file.items():
                    if metric_type not in metric_type_data:
                        metric_type_data[metric_type] = {}
                
                    if pr_number not in metric_type_data[metric_type]:
                        metric_type_data[metric_type][pr_number] = {
                            "pr_number": pr_number,
                            "pr_date": pr_data["pr_date"],
                            "pr_title": pr_data["pr_title"],
                            "commit_sha": pr_data["commit_sha"],
                            "files": {}
                        }
                
                    if file_name not in metric_type_data[metric_type][pr_number]["files"]:
                        metric_type_data[metric_type][pr_number]["files"][file_name] = {}
                    metric_type_data[metric_type][pr_number]["files"][file_name] = metric_values
    
        # Save all metric types asynchronously
        saved_files = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for metric_type, data in metric_type_data.items():
                # Read existing data if available
                output_path = self.output_dir / f"{metric_type}_PRs.json"
                existing_data = self._read_existing_json(output_path)
                
                # Merge new data with existing data
                if existing_data:
                    for pr_number, pr_data in data.items():
                        existing_data[str(pr_number)] = pr_data
                    merged_data = existing_data
                else:
                    merged_data = data
                    
                futures.append(executor.submit(self._save_json, output_path, merged_data))
                saved_files.append((metric_type, str(output_path)))
            
            for future in futures:
                future.result()
    
        print(f"Finished saving metrics locally split by type under {self.output_dir}.")
    
        # Save online if requested
        if self.save_online:
            self._save_metrics_online(metric_type_data, saved_files)
        
    def _read_existing_json(self, path: Path) -> dict:
        """Read existing JSON data from file if it exists."""
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading existing file {path}: {e}")
        return {}
    
    def _save_metrics_online(self, metric_type_data, saved_files):
        """Save metrics to the GitHub repository."""
        try:
            # Define the target directory in the repo for metrics
            metrics_dir = "pull_request_metrics"
        
            # Check if the metrics directory exists, create if not
            try:
                self.repo.get_contents(metrics_dir)
            except Exception:
                # Directory doesn't exist, create it
                try:
                    self.repo.create_file(
                        f"{metrics_dir}/.gitkeep",
                        "Create pull_request_metrics directory",
                        "",
                        branch="main"
                    )
                except Exception as e:
                    print(f"Error creating directories: {e}")
        
            # Upload each metric file
            for metric_type, data in metric_type_data.items():
                # Include the repo name in the filename for uniqueness
                file_path = f"{metrics_dir}/{self.repo_safe_name}_{metric_type}_PRs.json"
                
                # Try to get existing data
                try:
                    contents = self.repo.get_contents(file_path)
                    # File exists, get its content
                    existing_data = json.loads(contents.decoded_content.decode('utf-8'))
                    # Merge new data with existing data
                    for pr_number, pr_data in data.items():
                        existing_data[str(pr_number)] = pr_data
                    file_content = json.dumps(existing_data, indent=4)
                    
                    # Update the file
                    self.repo.update_file(
                        file_path,
                        f"Update {metric_type} metrics for {self.repo_name}",
                        file_content,
                        contents.sha,
                        branch="main"
                    )
                except Exception:
                    # File doesn't exist or can't be read, create it with new data only
                    file_content = json.dumps(data, indent=4)
                    self.repo.create_file(
                        file_path,
                        f"Add {metric_type} metrics for {self.repo_name}",
                        file_content,
                        branch="main"
                    )
        
            print(f"Successfully uploaded metrics to GitHub repository at {metrics_dir}/")
        except Exception as e:
            print(f"Error saving metrics online to pull_request_metrics directory: {e}")

    def _save_json(self, path: Path, data: dict):
        """Save JSON data to local file."""
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
