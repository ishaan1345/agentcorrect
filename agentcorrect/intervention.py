"""
Runtime Intervention Proxy for AgentCorrect
Intercepts agent actions before execution and applies learned corrections
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from urllib.parse import urlparse
import hashlib
import uuid

from .detectors import AgentCorrectV4
from .trace_capture import TraceCapture, AgentAction
from .diff_detection import DiffDetector
from .correlation import CorrelationEngine, CorrelationPattern

@dataclass
class InterventionResult:
    """Result of an intervention attempt"""
    intervened: bool
    original_action: Dict
    corrected_action: Optional[Dict]
    corrections_applied: List[str]
    explanation: str
    confidence: float
    prevented_cost: float = 0.0  # Estimated cost prevented

class InterventionProxy:
    """
    The core component that makes agents work correctly
    Intercepts actions before execution and applies learned corrections
    """
    
    def __init__(self, 
                 confidence_threshold: float = 0.7,
                 auto_correct: bool = True):
        self.detector = AgentCorrectV4()
        self.trace_capture = TraceCapture()
        self.diff_detector = DiffDetector()
        self.correlation_engine = CorrelationEngine()
        
        self.confidence_threshold = confidence_threshold
        self.auto_correct = auto_correct
        
        # Statistics
        self.stats = {
            "total_actions": 0,
            "interventions": 0,
            "failures_prevented": 0,
            "cost_saved": 0.0
        }
    
    async def intercept(self, 
                       action: Dict,
                       execute_fn: Callable = None) -> Dict:
        """
        Main intervention point - intercepts and corrects agent actions
        
        Args:
            action: The agent action to intercept
            execute_fn: Function to execute the action (if not provided, returns corrected action)
            
        Returns:
            Result of the action execution or the corrected action
        """
        self.stats["total_actions"] += 1
        
        # Capture the action
        action_id = self.trace_capture.capture_action(
            action_type=action.get("type", "unknown"),
            target=action.get("url", action.get("target", "")),
            method=action.get("method"),
            payload=action.get("body", action.get("payload")),
            headers=action.get("headers"),
            context=action.get("context", {}),
            agent_framework=action.get("framework", "unknown")
        )
        
        # Track for correlation
        self.correlation_engine.track_action(action_id, action)
        
        # Check if this action will fail
        intervention = await self._check_intervention_needed(action)
        
        if intervention.intervened:
            self.stats["interventions"] += 1
            print(f"🔧 AgentCorrect: {intervention.explanation}")
            
            # Use corrected action
            action_to_execute = intervention.corrected_action
            
            # Log the correction
            self._log_intervention(intervention)
        else:
            action_to_execute = action
        
        # Execute the action (if function provided)
        if execute_fn:
            try:
                result = await execute_fn(action_to_execute)
                
                # Capture successful outcome
                self.trace_capture.capture_outcome(
                    action_id=action_id,
                    success=True,
                    response=result
                )
                
                return result
                
            except Exception as e:
                # Capture failure
                self.trace_capture.capture_outcome(
                    action_id=action_id,
                    success=False,
                    error=str(e)
                )
                
                # Track failure for learning
                self.correlation_engine.track_failure(action_id, {
                    "error": str(e),
                    "timestamp": time.time()
                })
                
                # Check if human corrects this
                self._monitor_for_correction(action_id)
                
                raise
        else:
            # Just return the corrected action
            return action_to_execute
    
    async def _check_intervention_needed(self, action: Dict) -> InterventionResult:
        """
        Check if intervention is needed and apply corrections
        """
        corrections_applied = []
        explanation_parts = []
        corrected_action = action.copy()
        confidence = 1.0
        prevented_cost = 0.0
        
        # 1. Check for known failures using detector
        trace_event = self._action_to_trace_event(action)
        detections = self.detector.detect(trace_event)
        
        if detections:
            for detection in detections:
                if detection["severity"] == "SEV0":
                    # Critical issue - must intervene
                    correction = self._get_correction_for_detection(detection, action)
                    if correction:
                        corrected_action = self._apply_correction(corrected_action, correction)
                        corrections_applied.append(detection["type"])
                        explanation_parts.append(detection["description"])
                        prevented_cost += self._estimate_prevented_cost(detection["type"])
        
        # 2. Check for learned patterns
        pattern = self.correlation_engine.find_matching_pattern(action)
        if pattern and pattern.confidence >= self.confidence_threshold:
            # Apply learned correction
            corrected_action = self._apply_pattern(corrected_action, pattern)
            corrections_applied.append(f"pattern_{pattern.pattern_id}")
            explanation_parts.append(f"Applied learned pattern (confidence: {pattern.confidence:.0%})")
            confidence *= pattern.confidence
        
        # 3. Check for missing required fields
        missing_fields = self._check_missing_fields(action)
        if missing_fields:
            for field, value in missing_fields.items():
                corrected_action = self._add_field(corrected_action, field, value)
                corrections_applied.append(f"added_{field}")
                explanation_parts.append(f"Added missing {field}")
        
        # Determine if we intervened
        intervened = len(corrections_applied) > 0
        
        if intervened:
            self.stats["failures_prevented"] += 1
            self.stats["cost_saved"] += prevented_cost
        
        return InterventionResult(
            intervened=intervened,
            original_action=action,
            corrected_action=corrected_action if intervened else None,
            corrections_applied=corrections_applied,
            explanation=" | ".join(explanation_parts) if explanation_parts else "No intervention needed",
            confidence=confidence,
            prevented_cost=prevented_cost
        )
    
    def _action_to_trace_event(self, action: Dict) -> Dict:
        """Convert action to trace event format for detector"""
        event = {
            "trace_id": f"trace_{uuid.uuid4().hex[:8]}",
            "role": action.get("type", "http"),
            "meta": {}
        }
        
        if action.get("type") == "http" or "url" in action:
            event["meta"]["http"] = {
                "url": action.get("url", ""),
                "method": action.get("method", "GET"),
                "headers": action.get("headers", {}),
                "body": action.get("body", {})
            }
        elif action.get("type") == "sql" or "query" in action:
            event["meta"]["sql"] = {
                "query": action.get("query", "")
            }
        elif action.get("type") == "redis" or "command" in action:
            event["meta"]["redis"] = {
                "command": action.get("command", "")
            }
        
        return event
    
    def _get_correction_for_detection(self, detection: Dict, action: Dict) -> Optional[Dict]:
        """Get correction for a specific detection"""
        correction = {}
        
        if detection["type"] == "payment_no_idempotency":
            # Add idempotency key
            provider = detection.get("provider", "").lower()
            if provider == "stripe":
                correction["add_header"] = {
                    "Idempotency-Key": self._generate_idempotency_key()
                }
            elif provider == "paypal":
                correction["add_header"] = {
                    "PayPal-Request-Id": self._generate_idempotency_key()
                }
            elif provider == "square":
                correction["add_body_field"] = {
                    "idempotency_key": self._generate_idempotency_key()
                }
        
        elif detection["type"] == "sql_no_where":
            # Add WHERE clause
            correction["modify_query"] = self._add_safe_where_clause(action.get("query", ""))
        
        elif detection["type"] == "redis_flush":
            # Block dangerous Redis commands
            correction["block"] = True
            correction["reason"] = "Dangerous Redis command blocked"
        
        return correction if correction else None
    
    def _apply_correction(self, action: Dict, correction: Dict) -> Dict:
        """Apply a correction to an action"""
        corrected = action.copy()
        
        if "add_header" in correction:
            if "headers" not in corrected:
                corrected["headers"] = {}
            corrected["headers"].update(correction["add_header"])
        
        if "add_body_field" in correction:
            if "body" not in corrected:
                corrected["body"] = {}
            corrected["body"].update(correction["add_body_field"])
        
        if "modify_query" in correction:
            corrected["query"] = correction["modify_query"]
        
        if correction.get("block"):
            # This action should be blocked entirely
            raise ValueError(f"Action blocked: {correction.get('reason', 'Safety violation')}")
        
        return corrected
    
    def _apply_pattern(self, action: Dict, pattern: CorrelationPattern) -> Dict:
        """Apply a learned pattern to an action"""
        corrected = action.copy()
        template = pattern.correction_template
        
        # Apply additions
        for path, value in template.get("additions", {}).items():
            corrected = self._add_field(corrected, path, value)
        
        # Apply modifications
        for path, change in template.get("modifications", {}).items():
            corrected = self._modify_field(corrected, path, change["to"])
        
        # Apply removals
        for path in template.get("removals", []):
            corrected = self._remove_field(corrected, path)
        
        return corrected
    
    def _check_missing_fields(self, action: Dict) -> Dict:
        """Check for commonly missing required fields"""
        missing = {}
        
        # Check for payment providers
        if "url" in action:
            url = action["url"].lower()
            headers = {k.lower(): v for k, v in action.get("headers", {}).items()}
            
            if "stripe.com" in url and action.get("method") == "POST":
                if "idempotency-key" not in headers:
                    missing["headers.Idempotency-Key"] = self._generate_idempotency_key()
            
            elif "paypal.com" in url and action.get("method") == "POST":
                if "paypal-request-id" not in headers:
                    missing["headers.PayPal-Request-Id"] = self._generate_idempotency_key()
        
        return missing
    
    def _add_field(self, obj: Dict, path: str, value: Any) -> Dict:
        """Add a field to an object using dot notation path"""
        parts = path.split(".")
        current = obj
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
        return obj
    
    def _modify_field(self, obj: Dict, path: str, value: Any) -> Dict:
        """Modify a field in an object using dot notation path"""
        return self._add_field(obj, path, value)
    
    def _remove_field(self, obj: Dict, path: str) -> Dict:
        """Remove a field from an object using dot notation path"""
        parts = path.split(".")
        current = obj
        
        for part in parts[:-1]:
            if part not in current:
                return obj
            current = current[part]
        
        if parts[-1] in current:
            del current[parts[-1]]
        
        return obj
    
    def _generate_idempotency_key(self) -> str:
        """Generate a unique idempotency key"""
        return f"agentcorrect_{uuid.uuid4()}"
    
    def _add_safe_where_clause(self, query: str) -> str:
        """Add a safe WHERE clause to a SQL query"""
        query_upper = query.upper()
        
        if "DELETE" in query_upper and "WHERE" not in query_upper:
            # Add WHERE 1=0 to make it safe (won't delete anything)
            return query + " WHERE 1=0 /* AgentCorrect: Added safety clause - review required */"
        
        if "UPDATE" in query_upper and "WHERE" not in query_upper:
            # Add WHERE 1=0 to make it safe
            return query + " WHERE 1=0 /* AgentCorrect: Added safety clause - review required */"
        
        return query
    
    def _estimate_prevented_cost(self, failure_type: str) -> float:
        """Estimate the cost prevented by stopping this failure"""
        cost_map = {
            "payment_no_idempotency": 5000.0,  # Average duplicate charge
            "payment_invalid_idempotency": 5000.0,
            "sql_destructive": 50000.0,  # Data loss cost
            "sql_no_where": 10000.0,  # Accidental mass update
            "sql_tautology": 10000.0,
            "redis_flush": 5000.0,  # Cache rebuild cost
            "mongo_drop": 50000.0,
            "s3_delete_bucket": 10000.0
        }
        
        return cost_map.get(failure_type, 1000.0)  # Default prevention value
    
    def _monitor_for_correction(self, action_id: str):
        """Monitor for human correction after a failure"""
        # This would run in background to detect corrections
        async def monitor():
            await asyncio.sleep(1)  # Give human time to correct
            
            # Check for corrections in the trace
            corrections = self.trace_capture.detect_correction_pattern(window_seconds=60)
            
            for correction in corrections:
                # Correlate the correction
                chain = self.correlation_engine.correlate_correction(
                    correction_data={
                        "action": correction.corrected_action,
                        "correction_type": correction.correction_type
                    }
                )
                
                if chain:
                    print(f"✅ Learned from correction: {chain.correction_type}")
        
        # Run in background
        asyncio.create_task(monitor())
    
    def _log_intervention(self, intervention: InterventionResult):
        """Log intervention for analysis"""
        log_entry = {
            "timestamp": time.time(),
            "corrections": intervention.corrections_applied,
            "explanation": intervention.explanation,
            "confidence": intervention.confidence,
            "prevented_cost": intervention.prevented_cost
        }
        
        # Would write to intervention log
        print(f"📊 Intervention logged: {json.dumps(log_entry, indent=2)}")
    
    def get_statistics(self) -> Dict:
        """Get intervention statistics"""
        return {
            **self.stats,
            "intervention_rate": self.stats["interventions"] / self.stats["total_actions"] 
                                if self.stats["total_actions"] > 0 else 0,
            "average_cost_saved": self.stats["cost_saved"] / self.stats["failures_prevented"]
                                 if self.stats["failures_prevented"] > 0 else 0
        }


# Convenience function for easy integration
def make_correct(agent_fn):
    """
    Decorator to make any agent function automatically correct
    
    Usage:
        @make_correct
        async def my_agent_action(params):
            return {"url": "...", "method": "POST", ...}
    """
    proxy = InterventionProxy()
    
    async def wrapper(*args, **kwargs):
        action = await agent_fn(*args, **kwargs)
        return await proxy.intercept(action)
    
    return wrapper