import subprocess
import tempfile
import os
import shutil
from dotenv import load_dotenv

load_dotenv()

class PatchEngine:
    def __init__(self):
        self.git_token = os.getenv('GIT_TOKEN')
        self.git_repo = os.getenv('GIT_REPO')
        self.git_branch = os.getenv('GIT_BRANCH', 'main')
        self.git_user_email = os.getenv('GIT_USER_EMAIL', 'selfhealing@example.com')
        self.git_user_name = os.getenv('GIT_USER_NAME', 'Self-Healing Agent')
        self.temp_dir = None
        self.original_dir = None
        
    def __enter__(self):
        """Context manager entry - creates temp directory and clones repo"""
        self.temp_dir = tempfile.mkdtemp(prefix='patch_engine_')
        self.original_dir = os.getcwd()
        
        # Clone the repository
        repo_url = f"https://{self.git_token}@github.com/{self.git_repo}.git"
        subprocess.run([
            'git', 'clone', '--depth', '1', '--branch', self.git_branch, 
            repo_url, self.temp_dir
        ], check=True)
        
        # Change to repo directory
        os.chdir(self.temp_dir)
        
        # Configure git user (required for commits)
        # Git requires user.email and user.name to be set before making commits
        # These can be customized via GIT_USER_EMAIL and GIT_USER_NAME environment variables
        subprocess.run(['git', 'config', 'user.email', self.git_user_email], check=True)
        subprocess.run(['git', 'config', 'user.name', self.git_user_name], check=True)
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp directory"""
        if self.original_dir:
            os.chdir(self.original_dir)
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            
    def create_branch(self, branch_name):
        """Create a new branch from the current branch"""
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
    
    def push_branch(self, branch_name):
        """Push the branch to remote repository"""
        repo_url = f"https://{self.git_token}@github.com/{self.git_repo}.git"
        subprocess.run(['git', 'push', repo_url, branch_name], check=True)

    def replace_file_and_commit(self, class_name: str, new_content: str, commit_message: str):
        """
        Replace an entire Apex class file with new content and commit the change.
        """
        file_path = f"force-app/main/default/classes/{class_name}.cls"
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Class file not found: {file_path}")
        
        # Write the new content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Stage and commit the changes
        subprocess.run(['git', 'add', file_path], check=True)
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        print(f"✓ Replaced {file_path} and committed changes")
