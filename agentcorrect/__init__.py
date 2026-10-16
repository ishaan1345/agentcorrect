"""
AgentCorrect - provider-agnostic tool execution guard and trace analyzer

Use agentcorrect.runtime for the execution gate; legacy trace checks remain available.
"""

__version__ = "0.2.0a1"
__author__ = "AgentCorrect Team"
__email__ = "support@agentcorrect.com"
__license__ = "MIT"

from .detectors_v4_fixed import AgentCorrectV4

__all__ = ["AgentCorrectV4", "__version__"]