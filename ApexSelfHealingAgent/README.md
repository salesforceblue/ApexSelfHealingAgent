# SelfHealingAgent Build

This project implements the full initial build of the SelfHealingAgent orchestrator,
including a FastAPI endpoint for Apex to invoke.

Read all about this project at https://salesforceblue.com/apex-self-healing-agent/ 

## Prerequisites

- Python 3.8+ installed
- Install dependencies: `pip install -r requirements.txt`
- Configure `.env` file and update with your Salesforce, GitHub, and JIRA tokens

## Quick Start

1. **Start the server:**
   ```bash
   python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
   ```

2. **Test the API:**
   ```bash
   curl -X POST http://localhost:8000/solve \
     -H "Content-Type: application/json" \
     -d '{
       "exception_id": "test-123",
       "exception_message": "Attempt to de-reference a null object",
       "stack_trace": "Class.AccountTriggerHandler.handleAfterUpdate: line 14, column 1\nTrigger.AccountTrigger: line 3, column 1"
     }'
   ```

Server runs on `http://localhost:8000` - API docs available at `/docs`
