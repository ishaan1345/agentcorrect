"""
LangChain Integration for AgentCorrect
Makes LangChain agents work correctly by intercepting and correcting their actions
"""

from typing import Dict, List, Any, Optional
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish
import json
import asyncio

from ..intervention import InterventionProxy

class AgentCorrectCallback(BaseCallbackHandler):
    """
    LangChain callback that intercepts and corrects agent actions
    
    Usage:
        from agentcorrect.integrations.langchain import AgentCorrectCallback
        
        callback = AgentCorrectCallback()
        agent = initialize_agent(
            tools,
            llm,
            callbacks=[callback],
            ...
        )
    """
    
    def __init__(self, 
                 auto_correct: bool = True,
                 confidence_threshold: float = 0.7):
        self.proxy = InterventionProxy(
            confidence_threshold=confidence_threshold,
            auto_correct=auto_correct
        )
        self.current_action = None
        self.corrected_actions = {}
    
    def on_agent_action(self, action: AgentAction, **kwargs) -> Any:
        """
        Called when agent decides on an action
        This is where we intercept and potentially correct
        """
        # Convert LangChain action to our format
        agent_action = self._langchain_to_agentcorrect(action)
        
        # Run intervention check synchronously
        loop = asyncio.new_event_loop()
        intervention = loop.run_until_complete(
            self.proxy._check_intervention_needed(agent_action)
        )
        loop.close()
        
        if intervention.intervened:
            # Store the correction
            self.corrected_actions[action.tool] = intervention
            
            # Modify the action in place (if possible)
            if intervention.corrected_action:
                corrected_lc_action = self._agentcorrect_to_langchain(
                    intervention.corrected_action,
                    action
                )
                
                # Update the action
                action.tool = corrected_lc_action.tool
                action.tool_input = corrected_lc_action.tool_input
                action.log = f"[AgentCorrect: {intervention.explanation}]\n{action.log}"
                
                print(f"🔧 AgentCorrect intervened: {intervention.explanation}")
        
        self.current_action = action
        return action
    
    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """
        Called when a tool fails
        This is a learning opportunity
        """
        if self.current_action:
            # Track the failure
            action_data = self._langchain_to_agentcorrect(self.current_action)
            
            # This failed - track it for learning
            action_id = self.proxy.trace_capture.capture_action(
                action_type="tool",
                target=self.current_action.tool,
                payload={"input": self.current_action.tool_input},
                context={"error": str(error)}
            )
            
            self.proxy.trace_capture.capture_outcome(
                action_id=action_id,
                success=False,
                error=str(error)
            )
            
            self.proxy.correlation_engine.track_failure(action_id, {
                "error": str(error),
                "tool": self.current_action.tool
            })
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """
        Called when a tool completes successfully
        Track success for confidence scoring
        """
        if self.current_action and self.current_action.tool in self.corrected_actions:
            # A corrected action succeeded!
            intervention = self.corrected_actions[self.current_action.tool]
            
            # Update pattern confidence
            # This proves the correction worked
            print(f"✅ AgentCorrect correction succeeded for {self.current_action.tool}")
    
    def _langchain_to_agentcorrect(self, action: AgentAction) -> Dict:
        """Convert LangChain action to AgentCorrect format"""
        # Parse tool input based on common patterns
        tool_input = action.tool_input
        
        # Handle different tool types
        if action.tool == "requests_post" or "post" in action.tool.lower():
            # HTTP POST tool
            if isinstance(tool_input, dict):
                return {
                    "type": "http",
                    "method": "POST",
                    "url": tool_input.get("url", ""),
                    "headers": tool_input.get("headers", {}),
                    "body": tool_input.get("data", tool_input.get("json", {})),
                    "framework": "langchain"
                }
        
        elif action.tool == "sql_query" or "sql" in action.tool.lower():
            # SQL tool
            return {
                "type": "sql",
                "query": tool_input if isinstance(tool_input, str) else str(tool_input),
                "framework": "langchain"
            }
        
        # Generic tool
        return {
            "type": "tool",
            "tool": action.tool,
            "input": tool_input,
            "framework": "langchain"
        }
    
    def _agentcorrect_to_langchain(self, 
                                   corrected: Dict,
                                   original: AgentAction) -> AgentAction:
        """Convert corrected action back to LangChain format"""
        # Create new action with corrections
        tool_input = original.tool_input
        
        if corrected["type"] == "http":
            # Update HTTP parameters
            if isinstance(tool_input, dict):
                tool_input["headers"] = corrected.get("headers", tool_input.get("headers", {}))
                tool_input["data"] = corrected.get("body", tool_input.get("data", {}))
                if "url" in corrected:
                    tool_input["url"] = corrected["url"]
        
        elif corrected["type"] == "sql":
            # Update SQL query
            tool_input = corrected.get("query", tool_input)
        
        # Create new action with corrected input
        return AgentAction(
            tool=original.tool,
            tool_input=tool_input,
            log=original.log
        )


class AgentCorrectToolWrapper:
    """
    Wrapper for LangChain tools that adds AgentCorrect protection
    
    Usage:
        from langchain.tools import Tool
        from agentcorrect.integrations.langchain import AgentCorrectToolWrapper
        
        original_tool = Tool(name="api_call", func=make_api_call)
        protected_tool = AgentCorrectToolWrapper(original_tool)
    """
    
    def __init__(self, tool, proxy: Optional[InterventionProxy] = None):
        self.tool = tool
        self.proxy = proxy or InterventionProxy()
        
        # Copy tool attributes
        self.name = tool.name
        self.description = tool.description
    
    async def arun(self, *args, **kwargs):
        """Async run with protection"""
        # Create action representation
        action = {
            "type": "tool",
            "tool": self.name,
            "args": args,
            "kwargs": kwargs,
            "framework": "langchain"
        }
        
        # Intercept and potentially correct
        corrected = await self.proxy.intercept(action)
        
        # Run with corrected parameters
        if hasattr(self.tool, 'arun'):
            return await self.tool.arun(
                *corrected.get("args", args),
                **corrected.get("kwargs", kwargs)
            )
        else:
            return self.tool.run(
                *corrected.get("args", args),
                **corrected.get("kwargs", kwargs)
            )
    
    def run(self, *args, **kwargs):
        """Sync run with protection"""
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.arun(*args, **kwargs))
        loop.close()
        return result


def make_agent_correct(agent_or_chain):
    """
    Make any LangChain agent or chain automatically correct
    
    Usage:
        from agentcorrect.integrations.langchain import make_agent_correct
        
        agent = initialize_agent(tools, llm, ...)
        safe_agent = make_agent_correct(agent)
    """
    callback = AgentCorrectCallback()
    
    # Add callback to the agent/chain
    if hasattr(agent_or_chain, 'callbacks'):
        if agent_or_chain.callbacks:
            agent_or_chain.callbacks.append(callback)
        else:
            agent_or_chain.callbacks = [callback]
    elif hasattr(agent_or_chain, 'callback_manager'):
        agent_or_chain.callback_manager.add_handler(callback)
    
    return agent_or_chain


# Example: Protecting common failure points
class SafeStripeChargeTool:
    """
    Example of a protected Stripe charge tool that never forgets idempotency
    """
    
    def __init__(self, stripe_key: str):
        self.stripe_key = stripe_key
        self.proxy = InterventionProxy()
        self.name = "stripe_charge"
        self.description = "Create a Stripe charge"
    
    async def arun(self, amount: int, currency: str = "usd", **kwargs):
        """Create a Stripe charge with automatic correction"""
        action = {
            "type": "http",
            "method": "POST",
            "url": "https://api.stripe.com/v1/charges",
            "headers": {
                "Authorization": f"Bearer {self.stripe_key}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            "body": {
                "amount": amount,
                "currency": currency,
                **kwargs
            }
        }
        
        # AgentCorrect will add idempotency key if missing
        corrected = await self.proxy.intercept(action)
        
        # Now execute with corrections
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                corrected["url"],
                headers=corrected["headers"],
                data=corrected["body"]
            ) as response:
                return await response.json()
    
    def run(self, *args, **kwargs):
        """Sync version"""
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.arun(*args, **kwargs))
        loop.close()
        return result