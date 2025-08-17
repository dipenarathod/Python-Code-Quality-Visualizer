import os
import time
import json
import logging
import argparse
import schedule
from pathlib import Path
from datetime import datetime
from github import Github
from typing import Dict, List, Optional, Set

#Import your existing classes
from PullRequests.AllPullRequests import AllPullRequestMetrics

#Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pr_metrics_server.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("PRMetricsServer")

class PRMetricsServer:
    """
    Server that periodically calculates metrics for pull requests in specified repositories.
    """
    def __init__(self, config_file: str = "pr_config.json"):
        """
        Initialize the PR metrics server with configuration.
        
        Args:
            config_file: Path to the configuration file.
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.github_client = Github(self.config["access_token"])
        self.running = False
        
        #Track processed PRs to avoid recalculation
        self.processed_prs: Dict[str, List[int]] = {}
        
        #Load previously processed PRs
        self._load_processed_prs()
        
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            #Validate required fields
            required_fields = ["access_token", "repositories", "interval_hours"]
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field in config: {field}")
                    
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            #Provide default configuration
            return {
                "access_token": os.environ.get("GITHUB_ACCESS_TOKEN", ""),
                "repositories": [],
                "interval_hours": 6,
                "output_dir": "pr_metrics_output",
                "pr_state": "open",  #Can be "open", "closed", or "all"
                "days_lookback": 30  #Number of days to look back for PRs (kept for backwards compatibility)
            }
    
    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def _load_processed_prs(self):
        """Load the list of already processed PRs to avoid redundant calculations."""
        processed_prs_file = "processed_prs.json"
        try:
            if os.path.exists(processed_prs_file):
                with open(processed_prs_file, 'r') as f:
                    self.processed_prs = json.load(f)
                logger.info(f"Loaded previously processed PRs from {processed_prs_file}")
            else:
                logger.info("No previous PR processing history found.")
                self.processed_prs = {}
        except Exception as e:
            logger.error(f"Error loading processed PRs: {e}")
            self.processed_prs = {}
    
    def _save_processed_prs(self):
        """Save the list of processed PRs to avoid redundant calculations."""
        processed_prs_file = "processed_prs.json"
        try:
            with open(processed_prs_file, 'w') as f:
                json.dump(self.processed_prs, f, indent=4)
            logger.info(f"Saved processed PRs to {processed_prs_file}")
        except Exception as e:
            logger.error(f"Error saving processed PRs: {e}")
    
    def process_repository(self, repo_name: str):
        """
        Process pull requests for a single repository.
        
        Args:
            repo_name: Full name of the repository (e.g., "owner/repo").
        """
        logger.info(f"Processing pull requests for repository: {repo_name}")
        try:
            #Get the repository from GitHub
            repo = self.github_client.get_repo(repo_name)
            
            #Initialize repo in processed PRs if not exists
            if repo_name not in self.processed_prs:
                self.processed_prs[repo_name] = []
            
            #Get list of already processed PRs for this repository
            processed_pr_numbers = set(self.processed_prs.get(repo_name, []))
            
            #Get PR state from config (defaults to "open")
            pr_state = self.config.get("pr_state", "open")
            
            #Log the processing strategy
            logger.info(f"Processing all {pr_state} PRs for {repo_name} (skipping {len(processed_pr_numbers)} already processed)")
            
            #Create PR metrics calculator
            pr_metrics = AllPullRequestMetrics(
                repo, 
                save_online=self.config.get("save_online", False),
                save=True
            )
            
            #Calculate metrics for unprocessed PRs only
            pr_metrics.calculate_all(
                skip_pr_numbers=processed_pr_numbers, 
                pr_state=pr_state
            )
            
            #Save metrics by type if any PRs were processed
            if pr_metrics.pull_request_metrics:
                pr_metrics.save_by_metric_type()
                logger.info(f"Saved metrics for {len(pr_metrics.pull_request_metrics)} PRs from {repo_name}")
            
            #Update processed PRs
            new_pr_numbers = pr_metrics.get_processed_pr_numbers()
            if new_pr_numbers:
                self._update_processed_prs(repo_name, new_pr_numbers)
                logger.info(f"Added {len(new_pr_numbers)} new PRs to processed list for {repo_name}")
            
            #Log completion
            if pr_metrics.pull_request_metrics:
                logger.info(f"Completed PR metrics calculation for {repo_name} - processed {len(pr_metrics.pull_request_metrics)} new PRs")
            else:
                logger.info(f"No new PRs to process for {repo_name}")
                
        except Exception as e:
            logger.error(f"Error processing repository {repo_name}: {e}")
    
    def _update_processed_prs(self, repo_name: str, pr_numbers: List[int]):
        """Update the list of processed PRs for a repository."""
        #Convert existing list to set for faster lookup
        existing_prs = set(self.processed_prs.get(repo_name, []))
        
        #Add new PR numbers
        new_count = 0
        for pr_num in pr_numbers:
            if pr_num not in existing_prs:
                existing_prs.add(pr_num)
                new_count += 1
        
        #Update the stored list
        self.processed_prs[repo_name] = list(existing_prs)
        
        #Save updated list
        self._save_processed_prs()
        
        if new_count > 0:
            logger.info(f"Added {new_count} new PRs to processed list for {repo_name}")
    
    def process_all_repositories(self):
        """Process all repositories in the configuration."""
        logger.info("Starting PR metrics calculation for all repositories")
        start_time = time.time()
        
        #Record run start in status file
        self._update_status("running")
        
        try:
            #Process each repository
            for repo_name in self.config["repositories"]:
                self.process_repository(repo_name)
                
            #Update the last run time in configuration
            self.config["last_run"] = datetime.now().isoformat()
            self.save_config()
            
            #Record run completion in status file
            duration = time.time() - start_time
            self._update_status("idle", {
                "last_run_duration": duration,
                "last_run_completed": datetime.now().isoformat()
            })
            
            logger.info(f"Completed all repositories in {duration:.2f} seconds")
        except Exception as e:
            logger.error(f"Error in processing repositories: {e}")
            self._update_status("error", {"error": str(e)})
    
    def _update_status(self, status: str, additional_info: Optional[Dict] = None):
        """
        Update the status file with current server status.
        
        Args:
            status: Current status (running, idle, error).
            additional_info: Additional information to include.
        """
        status_info = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "config_file": self.config_file,
            "repositories": self.config["repositories"],
            "interval_hours": self.config["interval_hours"],
            "pr_state": self.config.get("pr_state", "open")
        }
        
        if additional_info:
            status_info.update(additional_info)
            
        try:
            with open("pr_server_status.json", 'w') as f:
                json.dump(status_info, f, indent=4)
        except Exception as e:
            logger.error(f"Error updating status file: {e}")
    
    def add_repository(self, repo_name: str):
        """
        Add a repository to the configuration.
        
        Args:
            repo_name: Full name of the repository to add.
        """
        if repo_name not in self.config["repositories"]:
            self.config["repositories"].append(repo_name)
            self.save_config()
            logger.info(f"Added repository: {repo_name}")
        else:
            logger.info(f"Repository already in configuration: {repo_name}")
    
    def remove_repository(self, repo_name: str):
        """
        Remove a repository from the configuration.
        
        Args:
            repo_name: Full name of the repository to remove.
        """
        if repo_name in self.config["repositories"]:
            self.config["repositories"].remove(repo_name)
            self.save_config()
            logger.info(f"Removed repository: {repo_name}")
        else:
            logger.info(f"Repository not in configuration: {repo_name}")
    
    def reset_processed_prs(self, repo_name: Optional[str] = None):
        """
        Reset the processed PRs list for a specific repository or all repositories.
        
        Args:
            repo_name: Specific repository to reset, or None to reset all.
        """
        if repo_name:
            if repo_name in self.processed_prs:
                self.processed_prs[repo_name] = []
                logger.info(f"Reset processed PRs for repository: {repo_name}")
            else:
                logger.info(f"Repository not found in processed PRs: {repo_name}")
        else:
            self.processed_prs = {}
            logger.info("Reset all processed PRs")
        
        self._save_processed_prs()
    
    def start(self):
        """Start the PR metrics server."""
        if self.running:
            logger.warning("Server is already running")
            return
            
        self.running = True
        logger.info(f"Starting PR metrics server with {self.config['interval_hours']} hour interval")
        logger.info(f"Processing all {self.config.get('pr_state', 'open')} PRs for configured repositories")
        
        #Set up the schedule
        schedule.every(self.config["interval_hours"]).hours.do(self.process_all_repositories)
        
        #Run immediately on start
        self.process_all_repositories()
        
        #Main loop
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  #Check every minute
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.running = False
            self._update_status("error", {"error": str(e)})
    
    def stop(self):
        """Stop the PR metrics server."""
        self.running = False
        logger.info("Server stopping...")
        self._update_status("stopped")

def create_default_config(config_file: str = "pr_config.json"):
    """Create a default configuration file if it doesn't exist."""
    if not os.path.exists(config_file):
        default_config = {
            "access_token": "",
            "repositories": [],
            "interval_hours": 6,
            "output_dir": "pr_metrics_output",
            "pr_state": "open",
            "use_days_lookback": False,
            "days_lookback": 30,
            "save_online": False
        }
        
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Created default configuration file: {config_file}")
        print(f"Please edit {config_file} to configure your GitHub access token and repositories.")


def main():
    """Main function to start the PR metrics server."""
    parser = argparse.ArgumentParser(description="GitHub Pull Request Metrics Server")
    parser.add_argument("--config", default="pr_config.json", help="Path to configuration file")
    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    parser.add_argument("--add-repo", help="Add a repository to the configuration")
    parser.add_argument("--remove-repo", help="Remove a repository from the configuration")
    parser.add_argument("--reset-processed", help="Reset processed PRs for a repository (or 'all' for all repos)")
    
    args = parser.parse_args()
    
    #Create default config if it doesn't exist
    create_default_config(args.config)
    
    #Create server instance
    server = PRMetricsServer(args.config)
    
    #Handle command line operations
    if args.add_repo:
        server.add_repository(args.add_repo)
        
    if args.remove_repo:
        server.remove_repository(args.remove_repo)
        
    if args.reset_processed:
        if args.reset_processed.lower() == "all":
            server.reset_processed_prs()
        else:
            server.reset_processed_prs(args.reset_processed)
        
    if args.run_once:
        server.process_all_repositories()
    else:
        #Start the server
        server.start()


if __name__ == "__main__":
    main()