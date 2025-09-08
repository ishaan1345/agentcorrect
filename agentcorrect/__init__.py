"""
AgentCorrect - Autocorrect for AI Agents
Simple, automatic fixes for common AI agent mistakes
"""

from .core import AgentCorrect, autocorrect, Correction
from .integrations import (
    protect_agent,
    LangChainCorrector, 
    OpenAIFunctionCorrector,
    autocorrect_action
)

__version__ = "1.0.0"
__all__ = [
    "AgentCorrect",
    "autocorrect", 
    "protect_agent",
    "LangChainCorrector",
    "OpenAIFunctionCorrector", 
    "autocorrect_action",
    "Correction"
]

# Quick start
def fix(action):
    """
    Quick fix for any AI agent action
    
    Example:
        import agentcorrect
        
        # Automatically adds auth headers, idempotency keys, etc.
        fixed = agentcorrect.fix({
            "url": "https://api.stripe.com/v1/charges",
            "method": "POST",
            "body": {"amount": 5000}
        })
    """
    return autocorrect(action)