import os
import time
import json
import logging
import argparse
import schedule
from pathlib import Path
from datetime import datetime
from github import Github
from typing import Dict, List, Optional

# Import your existing classes
from Branch.BranchMetrics import BranchMetrics
from Branch.BranchMetrics import MainBranchMetrics
from Branch.MetricsDataFrames import MetricsDataFrames
from Branch.MetricsFileManager import MetricsFileManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("metrics_server.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("MetricsServer")

class MetricsServer:
    """
    Server that periodically calculates metrics for specified repositories.
    """
    def __init__(self, config_file: str = "main_branch_metrics_server_config.json"):
        """
        Initialize the metrics server with configuration.
        
        Args:
            config_file: Path to the configuration file.
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.github_client = Github(self.config["access_token"])
        self.running = False
        
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            # Validate required fields
            required_fields = ["access_token", "repositories", "interval_hours"]
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field in config: {field}")
                    
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Provide default configuration
            return {
                "access_token": os.environ.get("GITHUB_ACCESS_TOKEN", ""),
                "repositories": [],
                "interval_hours": 24,
                "output_dir": "metrics_output",
                "branches": ["main"]
            }
    
    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            
    def process_repository(self, repo_name: str):
        """
        Process a single repository.
        
        Args:
            repo_name: Full name of the repository (e.g., "owner/repo").
        """
        logger.info(f"Processing repository: {repo_name}")
        try:
            # Get the repository from GitHub
            repo = self.github_client.get_repo(repo_name)
            
            # Process each branch in the configuration
            branches = self.config.get("branches", ["main"])
            for branch_name in branches:
                logger.info(f"Processing branch: {branch_name} in {repo_name}")
                
                # Create metrics calculator for this branch
                branch_metrics = MainBranchMetrics(
                    repo, 
                    save_online=self.config.get("save_online", False),
                    save=True
                ) if branch_name == "main" else BranchMetrics(
                    repo, 
                    branch_name=branch_name,
                    save_online=self.config.get("save_online", False),
                    save=True
                )
                
                # Calculate metrics
                branch_metrics.calculate_metrics()
                
                # Log completion
                logger.info(f"Completed metrics calculation for {repo_name}:{branch_name}")
                
        except Exception as e:
            logger.error(f"Error processing repository {repo_name}: {e}")
    
    def process_all_repositories(self):
        """Process all repositories in the configuration."""
        logger.info("Starting metrics calculation for all repositories")
        start_time = time.time()
        
        # Record run start in status file
        self._update_status("running")
        
        try:
            # Process each repository
            for repo_name in self.config["repositories"]:
                self.process_repository(repo_name)
                
            # Update the last run time in configuration
            self.config["last_run"] = datetime.now().isoformat()
            self.save_config()
            
            # Record run completion in status file
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
            "interval_hours": self.config["interval_hours"]
        }
        
        if additional_info:
            status_info.update(additional_info)
            
        try:
            with open("server_status.json", 'w') as f:
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
    
    def start(self):
        """Start the metrics server."""
        if self.running:
            logger.warning("Server is already running")
            return
            
        self.running = True
        logger.info(f"Starting metrics server with {self.config['interval_hours']} hour interval")
        
        # Set up the schedule
        schedule.every(self.config["interval_hours"]).hours.do(self.process_all_repositories)
        
        # Run immediately on start
        self.process_all_repositories()
        
        # Main loop
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.running = False
            self._update_status("error", {"error": str(e)})
    
    def stop(self):
        """Stop the metrics server."""
        self.running = False
        logger.info("Server stopping...")
        self._update_status("stopped")


def create_default_config(config_file: str = "config.json"):
    """Create a default configuration file if it doesn't exist."""
    if not os.path.exists(config_file):
        default_config = {
            "access_token": "",
            "repositories": [],
            "interval_hours": 24,
            "output_dir": "metrics_output",
            "branches": ["main"],
            "save_online": False
        }
        
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Created default configuration file: {config_file}")
        print(f"Please edit {config_file} to configure your GitHub access token and repositories.")


def main():
    """Main function to start the metrics server."""
    parser = argparse.ArgumentParser(description="GitHub Repository Metrics Server")
    parser.add_argument("--config", default="main_branch_metrics_server_config.json", help="Path to configuration file")
    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    parser.add_argument("--add-repo", help="Add a repository to the configuration")
    parser.add_argument("--remove-repo", help="Remove a repository from the configuration")
    
    args = parser.parse_args()
    
    # Create default config if it doesn't exist
    create_default_config(args.config)
    
    # Create server instance
    server = MetricsServer(args.config)
    
    # Handle command line operations
    if args.add_repo:
        server.add_repository(args.add_repo)
        
    if args.remove_repo:
        server.remove_repository(args.remove_repo)
        
    if args.run_once:
        server.process_all_repositories()
    else:
        # Start the server
        server.start()


if __name__ == "__main__":
    main()
