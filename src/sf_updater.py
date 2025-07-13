"""Module to update Exception__c records in Salesforce."""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SF_INSTANCE = os.getenv('SF_INSTANCE')
SF_TOKEN    = os.getenv('SF_ACCESS_TOKEN')

def update_exception_record(exception_id, pr_url, status):
    url = f"{SF_INSTANCE}/services/data/v60.0/sobjects/ExceptionLogger__c/{exception_id}"
    headers = {
        "Authorization": f"Bearer {SF_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "Status__c": status,
        "Pull_Request__c": pr_url
    }
    
    try:
        resp = requests.patch(url, json=body, headers=headers)
        resp.raise_for_status()
        print(f"✓ Successfully updated Salesforce record {exception_id}")
    except Exception as e:
        print(f"✗ Failed to update Salesforce record {exception_id}: {e}")
        raise
