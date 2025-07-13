"""Module to create pull requests via GitHub API."""
import requests

class PRCreator:
    def __init__(self, token, repo):
        self.token = token
        self.repo = repo

    def create_pr(self, branch_name, title, body):
        url = f'https://api.github.com/repos/{self.repo}/pulls'
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        payload = {
            'title': title,
            'head': branch_name,
            'base': 'main',
            'body': body
        }
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json().get('html_url')
