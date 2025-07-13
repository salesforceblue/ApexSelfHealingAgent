import os
import requests

class SnippetFetcher:
    """Fetch Apex class contents from remote Git repository, on demand, with simple per-class caching.
    Only handles Apex classes (.cls files) - triggers and other components are handled by the LLM logic."""
    def __init__(self):
        self.git_token = os.getenv('GIT_TOKEN')
        self.git_repo  = os.getenv('GIT_REPO')  # format: owner/repo
        self.branch    = os.getenv('GIT_BRANCH', 'main')
        self.base_url  = f"https://api.github.com/repos/{self.git_repo}/contents"
        self._cache    = {}

    def fetch(self, class_name):
        """
        Return the entire Apex class source for `class_name.cls` from the configured Git branch.
        Fetches directly from remote GitHub repository. Caches the result after the first fetch.
        Only handles Apex classes - the LLM should only provide class names, not triggers.
        """
        if class_name in self._cache:
            return self._cache[class_name]

        # GitHub API URL for the specific Apex class file
        file_path = f"force-app/main/default/classes/{class_name}.cls"
        url = f"{self.base_url}/{file_path}"
        
        headers = {
            'Authorization': f'token {self.git_token}',
            'Accept': 'application/vnd.github.v3.raw'  # Get raw content directly
        }
        
        params = {'ref': self.branch}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            content = response.text
        except requests.exceptions.RequestException as e:
            # Add more detailed error information
            error_details = f"Failed to fetch {class_name}.cls from remote repository: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_details += f" (Status: {e.response.status_code})"
                if e.response.status_code == 401:
                    error_details += " - GitHub token may be expired or invalid"
                elif e.response.status_code == 404:
                    error_details += f" - File not found at path: {file_path}"
            raise Exception(error_details)

        self._cache[class_name] = content
        return content
