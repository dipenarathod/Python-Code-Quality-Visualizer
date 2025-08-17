# Python Code Quality Visualizer
Tool developed for my SEET 2025 research paper

Code in folder 'AST Research'
- Use .venv in the folder
- You need to generate a GitHub Personal Access token and paste the token in: main_branch_metrics_server_config.json and pr_config.json

'AST Research' Structure:
- Folder 'Branch' - Logic to handle main branch code files (calculate metrics, storage, data frames creation, and plotting)
- Folder 'metrics' - Calculated (main branch) metrics will be stored here. The metriocs for code files discussed in the paper are stored here for example purposes
- Folder 'MetricsClasses' - Calculator classes to calculate code qulaity metrics using AST analysis. You need to modify the files in this folder to change the calculation logic. Each calculator class has some example usage code as well
- Folder 'pages' - Folder that stores the various pages for the multi page Dash application. Each page also has a singleton metrics manager
- Folder 'pul'_request_metrics' - Like folder 'metrics' but for pull requests
- Folder 'PullRequests' - Like folder 'Branch' but for pull requests
- Folder 'Testing Files' - Simple scripts to test various parts of the program
- File 'app.py' - Dash app configuration

The code works as a proof of concept, but many aspects of it are hard coded and need changing
