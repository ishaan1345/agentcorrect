#!/usr/bin/env python3
"""
Example: Convert LangChain/AutoGen/CrewAI traces to AgentCorrect format
"""

import json
import sys
from typing import Dict, List, Any

def convert_langchain_trace(langchain_events: List[Dict]) -> List[Dict]:
    """Convert LangChain trace to AgentCorrect format."""
    agentcorrect_trace = []
    
    for event in langchain_events:
        if event.get("type") == "tool_call":
            tool_name = event.get("tool", "")
            tool_input = event.get("input", {})
            
            # Convert SQL tools
            if tool_name in ["sql_database", "query_database"]:
                agentcorrect_trace.append({
                    "role": "sql",
                    "meta": {
                        "sql": {
                            "query": tool_input.get("query", "")
                        }
                    },
                    "trace_id": event.get("run_id", "unknown")
                })
            
            # Convert HTTP tools
            elif tool_name in ["requests", "http_request"]:
                agentcorrect_trace.append({
                    "role": "http",
                    "meta": {
                        "http": {
                            "method": tool_input.get("method", "GET"),
                            "url": tool_input.get("url", ""),
                            "headers": tool_input.get("headers", {}),
                            "body": tool_input.get("body", {})
                        }
                    },
                    "trace_id": event.get("run_id", "unknown")
                })
    
    return agentcorrect_trace

def convert_autogen_trace(autogen_logs: List[str]) -> List[Dict]:
    """Convert AutoGen logs to AgentCorrect format."""
    agentcorrect_trace = []
    
    for line in autogen_logs:
        # Parse AutoGen function calls
        if "function_call" in line:
            try:
                data = json.loads(line)
                func_name = data.get("function", "")
                args = data.get("arguments", {})
                
                if func_name == "execute_sql":
                    agentcorrect_trace.append({
                        "role": "sql",
                        "meta": {
                            "sql": {
                                "query": args.get("query", "")
                            }
                        }
                    })
                elif func_name == "make_payment":
                    agentcorrect_trace.append({
                        "role": "http",
                        "meta": {
                            "http": {
                                "method": "POST",
                                "url": args.get("url", ""),
                                "headers": args.get("headers", {}),
                                "body": args.get("payload", {})
                            }
                        }
                    })
            except json.JSONDecodeError:
                continue
    
    return agentcorrect_trace

def convert_openai_function_calls(messages: List[Dict]) -> List[Dict]:
    """Convert OpenAI function calling format to AgentCorrect."""
    agentcorrect_trace = []
    
    for msg in messages:
        if msg.get("role") == "assistant" and "function_call" in msg:
            func = msg["function_call"]
            func_name = func.get("name", "")
            args = json.loads(func.get("arguments", "{}"))
            
            if "sql" in func_name.lower() or "query" in func_name.lower():
                agentcorrect_trace.append({
                    "role": "sql",
                    "meta": {
                        "sql": {
                            "query": args.get("query", args.get("sql", ""))
                        }
                    }
                })
            elif "payment" in func_name.lower() or "charge" in func_name.lower():
                agentcorrect_trace.append({
                    "role": "http",
                    "meta": {
                        "http": {
                            "method": "POST",
                            "url": args.get("url", f"https://api.stripe.com/v1/charges"),
                            "headers": args.get("headers", {}),
                            "body": args.get("body", args)
                        }
                    }
                })
            elif "redis" in func_name.lower():
                agentcorrect_trace.append({
                    "role": "redis",
                    "meta": {
                        "redis": {
                            "command": args.get("command", "")
                        }
                    }
                })
    
    return agentcorrect_trace

def main():
    """Example usage."""
    
    # Example 1: LangChain trace
    langchain_trace = [
        {
            "type": "tool_call",
            "tool": "sql_database",
            "input": {"query": "DELETE FROM users WHERE age > 30"},
            "run_id": "abc123"
        },
        {
            "type": "tool_call", 
            "tool": "http_request",
            "input": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "body": {"amount": 5000}
            },
            "run_id": "def456"
        }
    ]
    
    # Convert and save
    converted = convert_langchain_trace(langchain_trace)
    with open("trace.jsonl", "w") as f:
        for event in converted:
            f.write(json.dumps(event) + "\n")
    
    print(f"Converted {len(converted)} events to AgentCorrect format")
    print("Run: agentcorrect analyze trace.jsonl")

if __name__ == "__main__":
    main()