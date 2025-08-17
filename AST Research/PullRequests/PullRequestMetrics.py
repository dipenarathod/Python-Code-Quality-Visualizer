import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from github import PullRequest, Repository
from typing import Dict, Any
from multiprocessing.pool import ThreadPool
import ast
from Branch.MetricsFileManager import MetricsFileManager
from MetricsClasses.MetricsController import MetricsController
from MetricsClasses.MetricsController import supported_metrics


class PullRequestMetrics:
    def __init__(self, repo: Repository, pr: PullRequest.PullRequest, save_online : bool = False, save:bool = False):
        self.repo = repo
        self.pr = pr
        self.save_online = save_online
        self.save=save
        self.branch_name = pr.head.ref
        self.metric_managers = {
            "Halstead": MetricsFileManager(repo, "Halstead", branch_name=self.branch_name),
            "Traditional": MetricsFileManager(repo, "Traditional", branch_name=self.branch_name),
            "OO": MetricsFileManager(repo, "OO", branch_name=self.branch_name)
        }

        # Load existing if any (optional, or we could always recalculate for PRs)
        for manager in self.metric_managers.values():
            manager.load_metrics([])

    def calculate_file_metrics(self, file_path: str, commit_sha: str) -> tuple[str, Dict]:
        try:
            file_content = self.repo.get_contents(file_path, ref=commit_sha)
            tree = ast.parse(file_content.decoded_content.decode('utf-8'))

            controller = MetricsController(tree)
            metrics = controller.calculate_metrics()

            return file_path, {
                "Halstead": metrics[0],
                "Traditional": metrics[1],
                "OO": metrics[2]
            }
        except Exception as e:
            print(f"Error calculating metrics for {file_path} in PR #{self.pr.number}: {e}")
            return file_path, {}

    def calculate_metrics(self):
        """Calculate metrics for all Python files changed in the pull request."""
        files = self.pr.get_files()
        commit_sha = self.pr.head.sha

        python_files = [f.filename for f in files if f.filename.endswith('.py')]

        with ThreadPool() as pool:
            results = [pool.apply_async(self.calculate_file_metrics, (file_path, commit_sha)) for file_path in python_files]

            pool.close()
            pool.join()

            for result in results:
                file_path, file_metrics = result.get()
                if file_metrics:
                    for metric_type in supported_metrics:
                        if metric_type in file_metrics:
                            manager = self.metric_managers[metric_type]
                            manager.update_file_metrics(commit_sha, file_path, file_metrics[metric_type])

        # Save depending on configuration
        if(self.save):
            for manager in self.metric_managers.values():
                if self.save_online:
                    manager.save_metrics()
                else:
                    manager.save_local_metrics()

        print(f"Metrics calculation completed for PR #{self.pr.number}.")

    def get_metric_file_path(self, metric_type: str) -> str:
        if metric_type in self.metric_managers:
            return self.metric_managers[metric_type].get_metrics_path()
        raise ValueError(f"Unsupported metric type: {metric_type}")
    def get_metrics(self) -> Dict[str, Any]:
        """Return calculated metrics for this PR in a clean merged format."""
        # Get the single SHA (always only one in PR head)
        commit_sha = self.pr.head.sha

        # Build a dictionary per file
        files_metrics = {}

        # Go through each metric type
        for metric_type, manager in self.metric_managers.items():
            if commit_sha not in manager.metrics:
                continue  # Skip if no metrics calculated yet

            for file_path, file_metrics in manager.metrics[commit_sha].items():
                if file_path not in files_metrics:
                    files_metrics[file_path] = {}

                # Attach metrics under correct metric type
                files_metrics[file_path][metric_type] = file_metrics

        return {
            "pr_number": self.pr.number,
            "pr_title": self.pr.title,
            "pr_date": self.pr.created_at.isoformat(),
            "commit_sha": commit_sha,
            "files": files_metrics
        }


    def compare_to_main(self) -> Dict[str, Dict[str, Any]]:
        """Compare PR metrics to the main branch metrics for changed files."""
        from Branch.BranchMetrics import BranchMetrics  # import here to avoid circular import

        main_branch_metrics = BranchMetrics(self.repo, branch_name="main")
        main_branch_metrics.load_existing_only()

        comparison = {}

        for metric_type in supported_metrics:
            pr_manager = self.metric_managers[metric_type]
            main_manager = main_branch_metrics.metric_managers[metric_type]

            pr_metrics = pr_manager.metrics
            main_metrics = main_manager.metrics

            commit_sha = self.pr.head.sha  # PR SHA used as key

            diff = {}
            if commit_sha in pr_metrics:
                for file_path, pr_file_metrics in pr_metrics[commit_sha].items():
                    main_file_metrics = {}

                    # Try to find same file metrics in main branch (by filename)
                    for commit_data in main_metrics.values():
                        if isinstance(commit_data, dict) and "metrics" in commit_data:
                            if file_path in commit_data["metrics"]:
                                main_file_metrics = commit_data["metrics"][file_path]
                                break

                    # Calculate delta safely
                    # Calculate delta safely
                    actual_pr_file_metrics = pr_file_metrics.get("metrics", pr_file_metrics)
                    actual_main_file_metrics = main_file_metrics.get("metrics", main_file_metrics)

                    delta = {}

                    for k in actual_pr_file_metrics:
                        pr_value = actual_pr_file_metrics.get(k, 0)
                        main_value = actual_main_file_metrics.get(k, 0)

                        if isinstance(pr_value, (int, float)) and isinstance(main_value, (int, float)):
                            delta[k] = pr_value - main_value
                        else:
                            delta[k] = None  # or whatever you want for non-numeric

                    diff[file_path] = {
                        "pr": actual_pr_file_metrics,
                        "main": actual_main_file_metrics,
                        "delta": delta
                    }


            comparison[metric_type] = diff

        return comparison
