#!/usr/bin/env python3
"""
AgentCorrect Integrations - Easy integration with AI frameworks
"""

from typing import Dict, Any, Callable
from .core import AgentCorrect
import json


class LangChainCorrector:
    """
    LangChain integration for AgentCorrect
    
    Usage:
        from agentcorrect_integrations import LangChainCorrector
        from langchain.agents import initialize_agent
        
        agent = initialize_agent(tools, llm, ...)
        safe_agent = LangChainCorrector(agent)
        
        # Now all agent actions are auto-corrected
        result = safe_agent.run("Process refund for order 123")
    """
    
    def __init__(self, agent, auto_fix: bool = True):
        self.agent = agent
        self.corrector = AgentCorrect(auto_fix=auto_fix)
        self._wrap_agent()
    
    def _wrap_agent(self):
        """Wrap agent methods to add autocorrect"""
        # Store original methods
        self._original_run = self.agent.run if hasattr(self.agent, 'run') else None
        self._original_invoke = self.agent.invoke if hasattr(self.agent, 'invoke') else None
        
        # Replace with wrapped versions
        if self._original_run:
            self.agent.run = self._wrapped_run
        if self._original_invoke:
            self.agent.invoke = self._wrapped_invoke
    
    def _wrapped_run(self, *args, **kwargs):
        """Wrapped run method with autocorrect"""
        # Get the action the agent wants to take
        result = self._original_run(*args, **kwargs)
        
        # If result looks like an action, fix it
        if isinstance(result, dict):
            result = self.corrector.fix(result)
            
            # Log corrections
            corrections = self.corrector.get_corrections()
            if corrections:
                print(f"🔧 AgentCorrect fixed {len(corrections)} issues:")
                for c in corrections:
                    print(f"  • {c.issue} → {c.fix}")
        
        return result
    
    def _wrapped_invoke(self, *args, **kwargs):
        """Wrapped invoke method with autocorrect"""
        result = self._original_invoke(*args, **kwargs)
        
        if isinstance(result, dict):
            result = self.corrector.fix(result)
            
            corrections = self.corrector.get_corrections()
            if corrections:
                print(f"🔧 AgentCorrect fixed {len(corrections)} issues")
        
        return result
    
    def run(self, *args, **kwargs):
        """Proxy run method"""
        return self.agent.run(*args, **kwargs)
    
    def invoke(self, *args, **kwargs):
        """Proxy invoke method"""
        return self.agent.invoke(*args, **kwargs)


class OpenAIFunctionCorrector:
    """
    OpenAI Function Calling integration
    
    Usage:
        from agentcorrect_integrations import OpenAIFunctionCorrector
        import openai
        
        corrector = OpenAIFunctionCorrector()
        
        # Get function call from OpenAI
        response = openai.ChatCompletion.create(...)
        function_call = response.choices[0].message.function_call
        
        # Fix any issues before executing
        fixed_call = corrector.fix_function_call(function_call)
    """
    
    def __init__(self):
        self.corrector = AgentCorrect()
    
    def fix_function_call(self, function_call: Dict) -> Dict:
        """Fix OpenAI function call before execution"""
        
        # Parse arguments if they're a string
        if isinstance(function_call.get("arguments"), str):
            try:
                args = json.loads(function_call["arguments"])
            except json.JSONDecodeError:
                args = {}
        else:
            args = function_call.get("arguments", {})
        
        # Convert to action format
        action = {
            "type": "function_call",
            "function": function_call.get("name"),
            **args
        }
        
        # Fix common issues
        fixed_action = self.corrector.fix(action)
        
        # Convert back to function call format
        fixed_call = function_call.copy()
        if isinstance(fixed_call.get("arguments"), str):
            # Remove type field and convert back to JSON string
            fixed_args = {k: v for k, v in fixed_action.items() 
                         if k not in ["type", "function", "blocked", "error", "warning"]}
            fixed_call["arguments"] = json.dumps(fixed_args)
        else:
            fixed_call["arguments"] = {k: v for k, v in fixed_action.items() 
                                      if k not in ["type", "function", "blocked", "error", "warning"]}
        
        # Handle blocked actions
        if fixed_action.get("blocked"):
            raise ValueError(f"Function call blocked: {fixed_action.get('error')}")
        
        return fixed_call


def protect_agent(agent: Any) -> Any:
    """
    Universal agent protector - works with any agent
    
    Usage:
        from agentcorrect_integrations import protect_agent
        
        agent = create_your_agent()
        safe_agent = protect_agent(agent)
    """
    
    # Detect agent type and wrap appropriately
    if hasattr(agent, '__module__'):
        module = agent.__module__
        
        if 'langchain' in module:
            return LangChainCorrector(agent)
        elif 'openai' in module:
            return OpenAIFunctionCorrector()
    
    # Generic wrapper for unknown agents
    class GenericCorrector:
        def __init__(self, agent):
            self.agent = agent
            self.corrector = AgentCorrect()
        
        def __getattr__(self, name):
            """Proxy all attributes to original agent"""
            attr = getattr(self.agent, name)
            
            if callable(attr):
                def wrapper(*args, **kwargs):
                    result = attr(*args, **kwargs)
                    if isinstance(result, dict):
                        result = self.corrector.fix(result)
                    return result
                return wrapper
            
            return attr
    
    return GenericCorrector(agent)


# Decorator for functions that generate agent actions
def autocorrect_action(func: Callable) -> Callable:
    """
    Decorator to autocorrect agent actions
    
    Usage:
        @autocorrect_action
        def generate_api_call(endpoint: str) -> dict:
            return {
                "url": endpoint,
                "method": "POST"
            }
        
        # Missing auth header will be added automatically
        action = generate_api_call("https://api.stripe.com/v1/charges")
    """
    corrector = AgentCorrect()
    
    def wrapper(*args, **kwargs):
        action = func(*args, **kwargs)
        if isinstance(action, dict):
            action = corrector.fix(action)
            
            corrections = corrector.get_corrections()
            if corrections:
                print(f"🔧 Autocorrected: {', '.join(c.issue for c in corrections)}")
        
        return action
    
    return wrapper