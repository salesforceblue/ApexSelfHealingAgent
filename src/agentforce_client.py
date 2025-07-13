"""Client to interact with Salesforce Agentforce Models API."""
import requests
import json

class AgentforceClient:
    def __init__(self, token, instance, model_id):
        self.token = token
        self.instance = instance  
        self.model_id = model_id

    def get_completion(self, messages, max_tokens=256, temperature=0.0):
        """Get completion from the model with improved prompt handling"""
        url = f'{self.instance}/einstein/platform/v1/models/{self.model_id}/generations'
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'x-sfdc-app-context': 'EinsteinGPT',
            'x-client-feature-id': 'ai-platform-models-connected-app'
        }
        
        # Convert messages to a more structured prompt
        prompt = ""
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                prompt += f"SYSTEM: {content}\n\n"
            elif role == 'user':
                prompt += f"USER: {content}\n\n"
            elif role == 'assistant':
                prompt += f"ASSISTANT: {content}\n\n"
        
        # Add explicit instruction for structured output
        if any('JSON' in msg.get('content', '') for msg in messages):
            prompt += "IMPORTANT: Respond with valid JSON only, no additional text.\n\n"
        
        payload = {
            'prompt': prompt.strip(),
            'maxTokens': max_tokens,
            'temperature': temperature
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            return result['generation']['generatedText']
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            raise
        except KeyError as e:
            print(f"Unexpected response format: {e}")
            print(f"Full response: {resp.json()}")
            raise
