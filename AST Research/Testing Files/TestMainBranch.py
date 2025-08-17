import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from github import Github
from Branch.BranchMetrics import MainBranchMetrics
from Branch.MetricsDataFrames import MetricsDataFrames

# ======== SETUP ========
ACCESS_TOKEN = "GitHub Personal Access Token"  # Replace this when testing
REPO_NAME = "dipenarathod/desktop-tutorial"  # Format: "username/reponame"
SAVE_TO_REPO = False  # Set to True if you want to save results

# ======== STEP 1: INITIALIZE GITHUB + MAIN METRICS PROCESSOR ========
g = Github(ACCESS_TOKEN)
repo = g.get_repo(REPO_NAME)

main_metrics = MainBranchMetrics(repo, save_online=False,save=True)

# # ======== STEP 2: CALCULATE METRICS ========
main_metrics.calculate_metrics()

# ======== STEP 3: READ JSON FILES BACK INTO DATAFRAMES ========
# Use the convenience method to get file paths dynamically for each metric type
# halstead_file_path = main_metrics.get_metric_file_path("Halstead")
# oo_file_path = main_metrics.get_metric_file_path("OO")
# traditional_file_path = main_metrics.get_metric_file_path("Traditional")
# print(halstead_file_path)
# # Initialize DataFrames using the file paths
# halstead_df = MetricsDataFrames(halstead_file_path, "Halstead")
# oo_df = MetricsDataFrames(oo_file_path, "OO")
# traditional_df = MetricsDataFrames(traditional_file_path, "Traditional")

# # # ======== STEP 4: PRINT A SAMPLE FILE'S METRICS ========
# sample_file = halstead_df.get_all_files()[0] if halstead_df.get_all_files() else None

# if sample_file:
#     print("sample halstead metrics:\n", halstead_df.get_file_data(sample_file).head())
#     print("\nsample oo metrics - ck class:\n", oo_df.get_file_data(sample_file)['CBO'].head())  
#     print("\nsample traditional loc metrics:\n", traditional_df.get_file_data(sample_file)['flat_metrics'].head())
# else:
#     print("no python files found or no metrics extracted.")

