"""
AgentCorrect - CI/CD guardrails for AI agents

Stop payment duplicates, data deletions, and infrastructure wipes before production.
"""

__version__ = "0.1.0"
__author__ = "AgentCorrect Team"
__email__ = "support@agentcorrect.com"
__license__ = "MIT"

from .detectors_v4_fixed import AgentCorrectV4

__all__ = ["AgentCorrectV4", "__version__"]