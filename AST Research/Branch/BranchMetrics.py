#Originally V3
#Originally V3
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from MetricsClasses.MetricsController import MetricsController
from MetricsClasses.MetricsController import supported_metrics
from github import *
from typing import Dict, Any, Optional
from github import Repository, Branch, GitTree, GitTreeElement
import json
from multiprocessing.pool import ThreadPool
from MetricsFileManager import MetricsFileManager
import ast

class BranchMetrics:
    def __init__(self, repo: Repository, branch_name: str = "main", save_online : bool = False, save:bool = False):
        self.repo = repo
        self.branch_name = branch_name
        self.save_online= save_online
        self.save = save
        self.branch = self.repo.get_branch(branch_name)
        self.metric_managers = {
            "Halstead": MetricsFileManager(repo, "Halstead"),
            "Traditional": MetricsFileManager(repo, "Traditional"),
            "OO": MetricsFileManager(repo, "OO")
        }

        # Load existing metrics
        for manager in self.metric_managers.values():
            manager.load_metrics([])
            # Clean up any malformed data
            manager.clean_malformed_data()

    def calculate_file_metrics(self, file_content: GitTreeElement, commit_sha: str) -> tuple[str, Dict]:
        """Calculate metrics for a single file at a specific commit."""
        try:
            full_path = file_content.path
            file_data = self.repo.get_contents(full_path, ref=commit_sha)
            tree = ast.parse(file_data.decoded_content.decode('utf-8'))

            controller = MetricsController(tree)
            metrics = controller.calculate_metrics()

            return full_path, {
                "Halstead": metrics[0],
                "Traditional": metrics[1],
                "OO": metrics[2]
            }
        except Exception as e:
            print(f"Error calculating metrics for {file_content.path} in commit {commit_sha}: {e}")
            return file_content.path, {}

    def commit_needs_calculation(self, commit_sha: str) -> bool:
        """Check if metrics for this commit have already been calculated."""
        for manager in self.metric_managers.values():
            if manager.needs_recalculation_for_commit(commit_sha):
                return True
        return False

    def calculate_metrics(self):
        """Calculate metrics for the history of the main branch."""
        # Get all commits and sort them chronologically (oldest first)
        all_commits = list(self.repo.get_commits(sha=self.branch_name))
        all_commits.reverse()  # Now oldest first
        
        print(f"Processing {len(all_commits)} commits chronologically...")
        
        for i, commit in enumerate(all_commits):
            commit_sha = commit.sha
            commit_date = commit.commit.author.date.isoformat()

            print(f"Processing commit {i+1}/{len(all_commits)}: {commit_sha[:8]} on {commit_date}")

            # Skip if already calculated
            if not self.commit_needs_calculation(commit_sha):
                print(f"Skipping commit {commit_sha[:8]} (already processed)")
                continue

            try:
                tree = self.repo.get_git_tree(commit_sha, recursive=True).tree
                python_files = [item for item in tree if item.path.endswith('.py')]
                
                if not python_files:
                    print(f"No Python files found in commit {commit_sha[:8]}")
                    # Still record the commit info even if no Python files
                    branch_info = {
                        "commit_sha": commit_sha,
                        "commit_date": commit_date,
                        "file_count": 0
                    }
                    for manager in self.metric_managers.values():
                        manager.update_commit_metrics(commit_sha, commit_date, {})
                        manager.update_branch_info(commit_sha, branch_info)
                    continue

                print(f"Found {len(python_files)} Python files")

                # Process files in parallel
                with ThreadPool() as pool:
                    results = [pool.apply_async(self.calculate_file_metrics, (file, commit_sha)) for file in python_files]
                    pool.close()
                    pool.join()

                    # Collect results
                    commit_metrics = {}
                    for result in results:
                        file_path, file_metrics = result.get()
                        if file_metrics:
                            commit_metrics[file_path] = file_metrics

                # Update metrics for each type
                for metric_type in supported_metrics:
                    manager = self.metric_managers[metric_type]
                    
                    # Extract metrics for this type from all files
                    type_metrics = {}
                    for file_path, file_metrics in commit_metrics.items():
                        if metric_type in file_metrics:
                            type_metrics[file_path] = file_metrics[metric_type]
                    
                    # Update the manager with commit-based structure
                    manager.update_commit_metrics(commit_sha, commit_date, type_metrics)

                # Update branch info
                branch_info = {
                    "commit_sha": commit_sha,
                    "commit_date": commit_date,
                    "file_count": len(commit_metrics)
                }

                for manager in self.metric_managers.values():
                    manager.update_branch_info(commit_sha, branch_info)

                print(f"Processed {len(commit_metrics)} files in commit {commit_sha[:8]}")

            except Exception as e:
                print(f"Error processing commit {commit_sha[:8]}: {e}")
                continue

        # Save depending on configuration
        for metric_type, manager in self.metric_managers.items():
            print(f"Saving {metric_type} metrics...")
            if self.save_online:
                manager.save_metrics()
            if self.save:
                manager.save_local_metrics()

        print("Historical metrics calculation completed.")

    def format_metrics_for_json(self, metrics_dict: Dict) -> Dict:
        """
        This method is now less relevant since we're using commit-based structure,
        but keeping for backward compatibility.
        """
        return metrics_dict

    def compare_to_main(self, other_branch_name: str = "main") -> Dict:
        """Compare metrics from this branch with the main branch."""
        metrics = BranchMetrics(self.repo, branch_name=other_branch_name)
        metrics.load_existing_only()

        comparison = {}
        for metric_type in supported_metrics:
            current = self.metric_managers[metric_type].metrics
            main = metrics.metric_managers[metric_type].metrics

            diff = {}
            # Compare commit by commit
            for commit_sha in current:
                if commit_sha == "branch_info":
                    continue
                    
                current_commit = current.get(commit_sha, {})
                main_commit = main.get(commit_sha, {})
                
                if not isinstance(current_commit, dict) or not isinstance(main_commit, dict):
                    continue
                
                commit_diff = {}
                current_metrics = current_commit.get("metrics", {})
                main_metrics = main_commit.get("metrics", {})
                
                for file_path in current_metrics:
                    self_val = current_metrics.get(file_path, {})
                    main_val = main_metrics.get(file_path, {})
                    delta = {k: self_val.get(k, 0) - main_val.get(k, 0) for k in self_val}

                    commit_diff[file_path] = {
                        "self": self_val,
                        "main": main_val,
                        "delta": delta
                    }
                
                if commit_diff:
                    diff[commit_sha] = commit_diff

            comparison[metric_type] = diff

        return comparison

    def get_metric_file_path(self, metric_type: str) -> str:
        if metric_type in self.metric_managers:
            return self.metric_managers[metric_type].get_metrics_path()
        raise ValueError(f"Unsupported metric type: {metric_type}")

    def load_existing_only(self):
        for manager in self.metric_managers.values():
            manager.load_existing_metrics()

class MainBranchMetrics(BranchMetrics):
    def __init__(self, repo, save_online : bool = False, save:bool = False):
        super().__init__(repo, branch_name="main", save_online=save_online,save=save)
# from datetime import datetime
# import sys
# import os
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# from MetricsClasses.MetricsController import MetricsController
# from MetricsClasses.MetricsController import supported_metrics
# from github import *
# from typing import Dict, Any, Optional
# from github import Repository, Branch, GitTree, GitTreeElement
# import json
# from multiprocessing.pool import ThreadPool
# from MetricsFileManager import MetricsFileManager
# import ast

# class BranchMetrics:
#     def __init__(self, repo: Repository, branch_name: str = "main", save_online : bool = False, save:bool = False):
#         self.repo = repo
#         self.branch_name = branch_name
#         self.save_online= save_online
#         self.save = save
#         self.branch = self.repo.get_branch(branch_name)
#         self.metric_managers = {
#             "Halstead": MetricsFileManager(repo, "Halstead"),
#             "Traditional": MetricsFileManager(repo, "Traditional"),
#             "OO": MetricsFileManager(repo, "OO")
#         }

#         # Load existing metrics
#         for manager in self.metric_managers.values():
#             manager.load_metrics([])

#     def calculate_file_metrics(self, file_content: GitTreeElement, commit_sha: str) -> tuple[str, Dict]:
#         """Calculate metrics for a single file at a specific commit."""
#         try:
#             full_path = file_content.path
#             file_data = self.repo.get_contents(full_path, ref=commit_sha)
#             tree = ast.parse(file_data.decoded_content.decode('utf-8'))

#             controller = MetricsController(tree)
#             metrics = controller.calculate_metrics()

#             return full_path, {
#                 "Halstead": metrics[0],
#                 "Traditional": metrics[1],
#                 "OO": metrics[2]
#             }
#         except Exception as e:
#             print(f"Error calculating metrics for {file_content.path} in commit {commit_sha}: {e}")
#             return file_content.path, {}

#     def file_needs_calculation(self, file_path: str, commit_sha: str, commit_date: str) -> bool:
#         """Check if metrics for this file at this commit have already been calculated."""
#         for manager in self.metric_managers.values():
#             metrics = manager.metrics
#             # Check if metrics exist for this commit date and file
#             if (commit_date in metrics and 
#                 file_path in metrics.get(commit_date, {}) and 
#                 metrics[commit_date][file_path]):
#                 continue
#             # Also check if the commit is in the formatted metrics (branch_info)
#             elif "branch_info" in metrics and commit_sha in metrics.get("branch_info", {}):
#                 continue
#             else:
#                 # If any manager doesn't have metrics for this file, we need to calculate
#                 return True
#         # All managers have metrics for this file at this commit
#         return False

#     def calculate_metrics(self):
#         """Calculate metrics for the history of the main branch."""
#         commits = self.repo.get_commits(sha=self.branch_name)
#         for commit in commits:
#             commit_sha = commit.sha
#             commit_date = commit.commit.author.date.isoformat()

#             # Skip if already calculated
#             if all(not manager.needs_recalculation_for_commit(commit_sha) for manager in self.metric_managers.values()):
#                 print(f"Skipping commit {commit_sha} (already processed)")
#                 continue

#             print(f"Processing commit: {commit_sha} on {commit_date}")
#             tree = self.repo.get_git_tree(commit_sha, recursive=True).tree
#             python_files = [item for item in tree if item.path.endswith('.py')]
            
#             # Filter out files that don't need calculation
#             files_to_process = []
#             for file in python_files:
#                 if self.file_needs_calculation(file.path, commit_sha, commit_date):
#                     files_to_process.append(file)
#                 else:
#                     print(f"Skipping file {file.path} (already processed in commit {commit_sha})")
            
#             if not files_to_process:
#                 print(f"All files in commit {commit_sha} already processed")
#                 continue

#             with ThreadPool() as pool:
#                 results = [pool.apply_async(self.calculate_file_metrics, (file, commit_sha)) for file in files_to_process]

#                 pool.close()
#                 pool.join()

#                 for result in results:
#                     file_path, file_metrics = result.get()
#                     if file_metrics:
#                         for metric_type in supported_metrics:
#                             if metric_type in file_metrics:
#                                 manager = self.metric_managers[metric_type]
#                                 manager.update_file_metrics(commit_date, file_path, file_metrics[metric_type])

#             branch_info = {
#                 "commit_sha": commit_sha,
#                 "commit_date": commit_date
#             }

#             for manager in self.metric_managers.values():
#                 manager.update_branch_info(commit_sha, branch_info)

#         # Save depending on configuration
#         for manager in self.metric_managers.values():
#             manager.metrics = self.format_metrics_for_json(manager.metrics)
#             if self.save_online:
#                 manager.save_metrics()
#             if self.save:
#                 manager.save_local_metrics()

#         print("Historical metrics calculation completed.")

#     def format_metrics_for_json(self, metrics_dict: Dict) -> Dict:
#         """
#         Reformat the collected metrics so that each commit SHA becomes a key,
#         containing the commit date and associated metrics.
#         """
#         formatted = {}
#         branch_info = metrics_dict.get("branch_info", {})

#         for key, value in branch_info.items():
#             # Skip special metadata keys
#             if key in {"commit_sha", "tree_sha", "last_update", "commit_date"}:
#                 continue

#             # Each actual commit is a dictionary under its SHA key
#             if isinstance(value, dict):
#                 commit_sha = value.get("commit_sha")
#                 commit_date = value.get("commit_date")

#                 # If both are valid and we have corresponding metrics
#                 if commit_sha and commit_date and commit_date in metrics_dict:
#                     formatted[commit_sha] = {
#                         "date": commit_date,
#                         "metrics": metrics_dict[commit_date]
#                     }

#         return formatted

#     def compare_to_main(self, other_branch_name: str = "main") -> Dict:
#         """Compare metrics from this branch with the main branch."""
#         metrics = BranchMetrics(self.repo, branch_name=other_branch_name)
#         metrics.load_existing_only()

#         comparison = {}
#         for metric_type in supported_metrics:
#             current = self.metric_managers[metric_type].metrics
#             main = metrics.metric_managers[metric_type].metrics

#             diff = {}
#             for commit_date in current:
#                 for file_path in current[commit_date]:
#                     self_val = current[commit_date][file_path]
#                     main_val = main.get(commit_date, {}).get(file_path, {})
#                     delta = {k: self_val.get(k, 0) - main_val.get(k, 0) for k in self_val}

#                     diff[file_path] = {
#                         "self": self_val,
#                         "main": main_val,
#                         "delta": delta
#                     }

#             comparison[metric_type] = diff

#         return comparison

#     def get_metric_file_path(self, metric_type: str) -> str:
#         if metric_type in self.metric_managers:
#             return self.metric_managers[metric_type].get_metrics_path()
#         raise ValueError(f"Unsupported metric type: {metric_type}")

#     def load_existing_only(self):
#         for manager in self.metric_managers.values():
#             manager.load_existing_metrics()

# class MainBranchMetrics(BranchMetrics):
#     def __init__(self, repo, save_online : bool = False, save:bool = False):
#         super().__init__(repo, branch_name="main", save_online=save_online,save=save)

# auth = Auth.Token("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")
# g = Github(auth=auth)

# repo = g.get_repo("dipenarathod/Python_Metrics")    
# main_branch_metrics=MainBranchMetrics(repo=repo)
# main_branch_metrics.calculate_metrics() 
# # print(main_branch_metrics.metric_managers["Traditional"].metrics)

# # with open('traditional_metrics.json', 'w') as fp:
# #     json.dump(main_branch_metrics.metric_managers["Traditional"].metrics, fp)

# with open('halstead_metrics.json', 'w') as fp:
#     json.dump(main_branch_metrics.metric_managers["Halstead"].metrics, fp)
    
# with open('oo_metrics.json', 'w') as fp:
#     json.dump(main_branch_metrics.metric_managers["OO"].metrics, fp)