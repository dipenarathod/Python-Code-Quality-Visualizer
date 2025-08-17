import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from github import Github
from PullRequests.PullRequestMetrics import PullRequestMetrics
from PullRequests.AllPullRequests import AllPullRequestMetrics
from PullRequests.PullRequestMetricsDataFrames import PullRequestMetricsDataFrames

g = Github("GitHub Personal Access Token")
repo = g.get_repo("dipenarathod/desktop-tutorial")

''' Get pull requests and calculate metrics '''

# pr = repo.get_pull(5)  # pull request #5

# # pr_metrics = PullRequestMetrics(repo, pr, save_online=False,save=False)
# # pr_metrics.calculate_metrics()

all_pr_metrics=AllPullRequestMetrics(repo, save_online=True, save=True)
all_pr_metrics.calculate_all()
all_pr_metrics.save_by_metric_type()

# comparison = pr_metrics.compare_to_main()

#Example print out:
# for metric_type, files in comparison.items():
#     print(f"\n=== {metric_type} Metrics ===")
#     for file_path, metrics in files.items():
#         print(f"File: {file_path}")
#         print("Delta:", metrics['delta'])


'''Data Frames test'''

# df_loader = PullRequestMetricsDataFrames(
#     json_path="pull_request_metrics/dipenarathod_desktop-tutorial/Halstead_PRs.json",
#     metric_type="halstead"
# )

# file_list = df_loader.get_all_files()
# print(file_list)  # All files with Halstead metrics across PRs

# df = df_loader.get_file_data("Test1.py")
# print(df)
