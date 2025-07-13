import os
import json
import uuid
from dotenv import load_dotenv

from .agentforce_client import AgentforceClient
from .snippet_fetcher   import SnippetFetcher
from .patch_engine      import PatchEngine
from .pr_creator        import PRCreator
from .jira_creator      import JiraCreator
from .sf_updater        import update_exception_record

load_dotenv()

SF_INSTANCE = os.getenv('SF_INSTANCE')
SF_API_ENDPOINT = os.getenv('SF_API_ENDPOINT')
SF_TOKEN    = os.getenv('SF_ACCESS_TOKEN')
MODEL_ID    = os.getenv('MODEL_ID')

GIT_TOKEN = os.getenv('GIT_TOKEN')
GIT_REPO  = os.getenv('GIT_REPO')

agent_client    = AgentforceClient(SF_TOKEN, SF_API_ENDPOINT, MODEL_ID)
snippet_fetcher = SnippetFetcher()
pr_creator      = PRCreator(GIT_TOKEN, GIT_REPO)
jira_creator    = JiraCreator()

def process_exception(exception_id: str, exception_message: str, stack_trace: str) -> str:
    print(f"🔍 Processing exception {exception_id}: {exception_message}")
    print(f"📋 Stack trace: {stack_trace}")
    
    # 1) Parse stack trace to extract all frames properly
    parse_prompt = [
        {"role": "system", "content": 
            "You are a JSON parser. Parse the stack trace and return ONLY valid JSON in this exact format:\n"
            "{\n"
            "  \"fixable\": true,\n"
            "  \"frames\": [\n"
            "    {\"class\": \"ClassName\", \"method\": \"methodName\", \"line\": 25}\n"
            "  ]\n"
            "}\n"
            "\n"
            "CRITICAL RULES:\n"
            "- Return ONLY raw JSON, no markdown, no code blocks, no extra text\n"
            "- Only include Apex CLASSES in frames, not triggers\n"
            "- If you see 'Trigger.SomeTrigger', look for the class it calls\n"
            "- Order frames from top to bottom (call stack order)\n"
            "- Validate your JSON before responding"},
        {"role": "user", "content": f"Exception: {exception_message}\n\nStack trace:\n{stack_trace}"}
    ]
    
    # Try parsing with validation
    max_parse_attempts = 3
    for attempt in range(max_parse_attempts):
        parse_resp = agent_client.get_completion(parse_prompt, max_tokens=512, temperature=0.0).strip()
        print(f"DEBUG: Parse response (attempt {attempt + 1}): {parse_resp}")
        
        try:
            result = json.loads(parse_resp)
            
            # Validate the response structure
            if not isinstance(result, dict):
                raise ValueError("Response is not a JSON object")
            if "fixable" not in result:
                raise ValueError("Missing 'fixable' field")
            if not result.get("fixable"):
                update_exception_record(exception_id, None, 'Human Intervention')
                raise ValueError("Exception not fixable by LLM")
            if "frames" not in result or not isinstance(result["frames"], list):
                raise ValueError("Missing or invalid 'frames' field")
            if not result["frames"]:
                raise ValueError("No frames found in stack trace")
            
            # Validate first frame
            primary_frame = result["frames"][0]
            if not isinstance(primary_frame, dict):
                raise ValueError("Invalid frame structure")
            if "class" not in primary_frame or "line" not in primary_frame:
                raise ValueError("Frame missing required fields")
            
            class_name = primary_frame["class"]
            error_line = primary_frame["line"]
            
            print(f"DEBUG: Primary frame - Class: {class_name}, Line: {error_line}")
            break
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Parse attempt {attempt + 1} failed: {e}")
            if attempt == max_parse_attempts - 1:
                update_exception_record(exception_id, None, 'Human Intervention')
                raise ValueError("Could not parse stack trace after multiple attempts")
            
            # Ask LLM to fix the format
            parse_prompt.append({
                "role": "user",
                "content": f"Invalid JSON format. Error: {e}. Please provide ONLY valid JSON in the exact format specified, no markdown or extra text."
            })
    
    # 2) Start with the primary class and fetch additional classes on demand
    classes_fetched = {}
    
    # Fetch the primary class first
    try:
        primary_class = snippet_fetcher.fetch(class_name)
        classes_fetched[class_name] = primary_class
        print(f"DEBUG: Fetched primary class {class_name}, length: {len(primary_class)}")
    except Exception as e:
        print(f"Failed to fetch primary class {class_name}: {e}")
        update_exception_record(exception_id, None, 'Human Intervention')
        raise ValueError(f"Could not fetch primary class {class_name}")
    
    # 3) Start the conversation with LLM for fixing
    fix_conversation = [
        {"role": "system", "content":
            "You are a Salesforce Apex expert. I will provide you with a class and exception details.\n"
            "If you need additional classes for context, respond with EXACTLY:\n"
            "NEED_MORE: ClassName\n"
            "\n"
            "When you have enough context to fix the issue, respond with ONLY valid JSON in this exact format:\n"
            "{\n"
            "  \"ClassName1\": \"<complete_fixed_class_content>\",\n"
            "  \"ClassName2\": \"<complete_fixed_class_content>\"\n"
            "}\n"
            "\n"
            "CRITICAL RULES FOR ANALYSIS:\n"
            "- The stack trace shows the execution path, but the ROOT CAUSE might be in classes NOT shown in the stack trace\n"
            "- Look for method calls, constructor calls, and dependencies in the provided classes\n"
            "- If you see calls to other classes (e.g., ContactSelector, AccountService, etc.), request them even if not in stack trace\n"
            "- Common patterns to look for:\n"
            "  * Service classes calling Selector classes for SOQL queries\n"
            "  * Util classes being called for data processing\n"
            "  * Helper classes for validation or transformation\n"
            "  * Factory classes for object creation\n"
            "- If the exception is about missing fields, check if the fix requires adding fields to SOQL queries in selector classes\n"
            "- If the exception is about null objects, check if the fix requires changes in classes that create/fetch those objects\n"
            "\n"
            "CRITICAL RULES FOR RESPONSE:\n"
            "- Return ONLY raw JSON, no markdown, no code blocks, no extra text\n"
            "- Return complete fixed classes with proper error handling\n"
            "- Preserve all existing functionality\n"
            "- Add minimal fixes for the specific exception type\n"
            "- Handle different exception types appropriately:\n"
            "  * NullPointerException: Add null checks AND request classes that might return null\n"
            "  * ListException: Add bounds checking AND request classes that populate lists\n"
            "  * DmlException: Add try-catch or validation AND request classes that prepare DML data\n"
            "  * QueryException: Add proper SOQL handling AND request selector classes with SOQL queries\n"
            "  * StringException: Add string validation AND request classes that process strings\n"
            "  * MathException: Add division by zero checks AND request classes that perform calculations\n"
            "- Escape quotes and newlines properly in JSON\n"
            "- Validate your JSON before responding"},
        {"role": "user", "content":
            f"Exception: {exception_message}\n"
            f"Error line: {error_line}\n"
            f"Stack trace:\n{stack_trace}\n\n"
            f"Primary class ({class_name}):\n{primary_class}\n\n"
            f"IMPORTANT: The stack trace shows the execution path, but the actual root cause might be in classes that are called internally but not shown in the stack trace.\n"
            f"For example, if {class_name} calls other service classes, selector classes, or utility classes, you should request them to understand the full context.\n"
            f"Look for method calls, constructor calls, and dependencies in the code above.\n\n"
            f"Please analyze the code and either:\n"
            f"1. Request more classes that might be related to the root cause (even if not in stack trace)\n"
            f"2. Provide the complete fix if you have enough context\n\n"
            f"Common patterns to investigate:\n"
            f"- Service classes often call Selector classes for SOQL queries\n"
            f"- Missing field exceptions often require adding fields to SOQL in selector classes\n"
            f"- Null pointer exceptions might need fixes in classes that create/fetch the null objects\n"
            f"- DML exceptions might need fixes in classes that prepare the DML data"}
    ]
    
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print(f"DEBUG: LLM conversation iteration {iteration}")
        
        llm_response = agent_client.get_completion(fix_conversation, max_tokens=4096, temperature=0.0).strip()
        print(f"DEBUG: LLM response length: {len(llm_response)}")
        
        # Check if LLM is requesting more classes
        if llm_response.startswith("NEED_MORE:"):
            requested_class = llm_response.split(":", 1)[1].strip()
            print(f"DEBUG: LLM requested additional class: {requested_class}")
            
            # Fetch the requested class
            try:
                if requested_class not in classes_fetched:
                    requested_class_content = snippet_fetcher.fetch(requested_class)
                    classes_fetched[requested_class] = requested_class_content
                    print(f"DEBUG: Fetched requested class {requested_class}, length: {len(requested_class_content)}")
                else:
                    requested_class_content = classes_fetched[requested_class]
                    print(f"DEBUG: Using already fetched class {requested_class}")
                
                # Add the requested class to conversation
                fix_conversation.append({
                    "role": "user",
                    "content": f"Here is {requested_class}:\n{requested_class_content}\n\n"
                              f"Now you have {len(classes_fetched)} classes total: {', '.join(classes_fetched.keys())}\n"
                              f"Please analyze all the classes together to understand the full context and dependencies.\n"
                              f"If you still need more classes to understand the root cause, request them.\n"
                              f"Otherwise, provide the complete fix for all classes that need changes."
                })
                
            except Exception as e:
                print(f"Failed to fetch requested class {requested_class}: {e}")
                fix_conversation.append({
                    "role": "user", 
                    "content": f"Could not fetch class {requested_class}. Error: {e}\n\n"
                              f"Available classes: {', '.join(classes_fetched.keys())}\n"
                              f"Please either:\n"
                              f"1. Request a different class name if you suspect the name was incorrect\n"
                              f"2. Proceed with the available classes and provide the best fix possible\n"
                              f"3. Request another class that might be related to the root cause"
                })
            
            continue
        
        # LLM should have provided the fix in JSON format
        try:
            fixed_classes = json.loads(llm_response)
            
            # Validate the response structure
            if not isinstance(fixed_classes, dict):
                raise ValueError("Response is not a JSON object")
            if not fixed_classes:
                raise ValueError("Empty JSON response")
            
            # Validate that we have at least the primary class fixed
            if class_name not in fixed_classes:
                raise ValueError(f"Primary class {class_name} not found in fix response")
            
            # Validate that all fixed classes have content
            for cls_name, cls_content in fixed_classes.items():
                if not isinstance(cls_content, str) or not cls_content.strip():
                    raise ValueError(f"Invalid or empty content for class {cls_name}")
            
            print(f"DEBUG: Received fixes for {len(fixed_classes)} classes")
            break
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM fix response: {e}")
            print(f"Raw response: {llm_response[:200]}...")
            if iteration == max_iterations:
                update_exception_record(exception_id, None, 'Human Intervention')
                raise ValueError("LLM could not provide valid JSON fix after multiple attempts")
            
            # Ask LLM to fix the JSON format
            fix_conversation.append({
                "role": "user",
                "content": f"Invalid JSON format. Error: {e}. Please provide ONLY valid JSON in the exact format specified, no markdown or extra text."
            })
            continue
        except ValueError as e:
            print(f"Invalid fix response structure: {e}")
            if iteration == max_iterations:
                update_exception_record(exception_id, None, 'Human Intervention')
                raise ValueError("LLM could not provide valid fix after multiple attempts")
            
            # Ask LLM to fix the response
            fix_conversation.append({
                "role": "user",
                "content": f"Invalid response structure: {e}. Please provide valid JSON with complete class content in the exact format specified."
            })
            continue
    
    if iteration >= max_iterations:
        update_exception_record(exception_id, None, 'Human Intervention')
        raise ValueError("Maximum iterations reached, LLM could not provide fix")
    
    # 4) Apply the fixes
    branch = f"fix/{class_name}-{uuid.uuid4().hex[:8]}"
    
    try:
        with PatchEngine() as patch_engine:
            patch_engine.create_branch(branch)
            
            # Apply fixes for all classes returned by LLM
            for fixed_class_name, fixed_class_content in fixed_classes.items():
                print(f"DEBUG: Applying fix for class {fixed_class_name}")
                patch_engine.replace_file_and_commit(
                    fixed_class_name, 
                    fixed_class_content, 
                    f"Auto-fix {fixed_class_name}: {exception_message}"
                )
            
            patch_engine.push_branch(branch)
        
        # Create PR
        pr_title = f"Fix {class_name}" + (f" and {len(fixed_classes)-1} other classes" if len(fixed_classes) > 1 else "")
        pr_description = f"Auto-fix for: {exception_message}\n\nFixed classes: {', '.join(fixed_classes.keys())}"
        pr_url = pr_creator.create_pr(branch, pr_title, pr_description)
        
        # Create Jira issue
        jira_summary = f"[{class_name}] Auto-fix PR created"
        jira_description = f"PR: {pr_url}\nException: {exception_message}\nFixed classes: {', '.join(fixed_classes.keys())}\nPlease review and merge."
        jira_url = jira_creator.create_issue(jira_summary, jira_description)
        
        # Update Salesforce record
        update_exception_record(exception_id, pr_url, 'Resolved')
        
        print(f"✅ Successfully created PR: {pr_url}")
        print(f"✅ Fixed {len(fixed_classes)} classes: {', '.join(fixed_classes.keys())}")
        return pr_url
        
    except Exception as e:
        print(f"Failed to create PR: {e}")
        update_exception_record(exception_id, None, 'Human Intervention')
        raise ValueError(f"Failed to create PR: {e}")




