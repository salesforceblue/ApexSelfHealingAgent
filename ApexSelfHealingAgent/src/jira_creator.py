# src/jira_creator.py
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

class JiraCreator:
    def __init__(self):
        load_dotenv()  # Ensure environment variables are loaded
        self.base_url   = os.getenv('JIRA_BASE_URL')
        self.email      = os.getenv('JIRA_EMAIL')
        self.api_token  = os.getenv('JIRA_API_TOKEN')
        self.project    = os.getenv('JIRA_PROJECT_KEY')
        self.issue_type = os.getenv('JIRA_ISSUE_TYPE', 'Task')
        self.auth       = HTTPBasicAuth(self.email, self.api_token)
        self.headers    = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def create_issue(self, summary: str, description: str) -> str:
        url = f"{self.base_url}/rest/api/3/issue"
        
        # Convert plain text description to Atlassian Document Format (ADF)
        adf_description = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": description
                        }
                    ]
                }
            ]
        }
        
        payload = {
            "fields": {
                "project":     {"key": self.project},
                "summary":     summary,
                "description": adf_description,
                "issuetype":   {"name": self.issue_type}
            }
        }
        resp = requests.post(url, json=payload, headers=self.headers, auth=self.auth)
        resp.raise_for_status()
        data = resp.json()
        return f"{self.base_url}/browse/{data['key']}"
