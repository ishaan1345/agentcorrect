"""
Trace Capture System for AgentCorrect
Records all agent actions, API calls, and outcomes for learning
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import deque
import threading

@dataclass
class AgentAction:
    """Represents a single agent action"""
    action_id: str
    timestamp: float
    action_type: str  # http, sql, redis, mongo, s3
    method: Optional[str]  # GET, POST, DELETE, etc
    target: str  # URL, query, command
    payload: Dict[str, Any]
    headers: Optional[Dict[str, str]]
    context: Dict[str, Any]  # LLM prompt, previous actions, etc
    agent_framework: str  # langchain, autogen, custom, etc
    session_id: str
    
    def to_hash(self) -> str:
        """Generate deterministic hash of action"""
        # Create stable representation
        stable_dict = {
            "type": self.action_type,
            "method": self.method,
            "target": self.target,
            "payload": json.dumps(self.payload, sort_keys=True)
        }
        return hashlib.sha256(
            json.dumps(stable_dict, sort_keys=True).encode()
        ).hexdigest()[:16]

@dataclass
class ActionOutcome:
    """Represents the outcome of an agent action"""
    action_id: str
    success: bool
    response: Optional[Dict[str, Any]]
    error: Optional[str]
    duration_ms: float
    status_code: Optional[int]
    
@dataclass 
class HumanCorrection:
    """Represents a human correction to an agent action"""
    original_action_id: str
    correction_time: float
    corrected_action: AgentAction
    correction_type: str  # manual_retry, parameter_fix, complete_replacement
    confidence: float = 1.0  # Human corrections start with high confidence

class TraceCapture:
    """
    Captures all agent actions and their outcomes
    Detects when humans correct agent mistakes
    """
    
    def __init__(self, storage_path: str = ".agentcorrect/traces"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory buffers for recent actions
        self.recent_actions: deque = deque(maxlen=1000)
        self.recent_outcomes: deque = deque(maxlen=1000)
        self.action_index: Dict[str, AgentAction] = {}
        
        # Thread-safe writing
        self.write_lock = threading.Lock()
        
        # Session tracking
        self.current_session = self._generate_session_id()
        
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return f"session_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        
    def _generate_action_id(self) -> str:
        """Generate unique action ID"""
        return f"action_{time.time()}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    def capture_action(self, 
                      action_type: str,
                      target: str,
                      method: Optional[str] = None,
                      payload: Optional[Dict] = None,
                      headers: Optional[Dict] = None,
                      context: Optional[Dict] = None,
                      agent_framework: str = "unknown") -> str:
        """
        Capture an agent action before execution
        Returns action_id for correlation
        """
        action = AgentAction(
            action_id=self._generate_action_id(),
            timestamp=time.time(),
            action_type=action_type,
            method=method,
            target=target,
            payload=payload or {},
            headers=headers,
            context=context or {},
            agent_framework=agent_framework,
            session_id=self.current_session
        )
        
        # Store in memory
        self.recent_actions.append(action)
        self.action_index[action.action_id] = action
        
        # Persist to disk
        self._write_action(action)
        
        return action.action_id
    
    def capture_outcome(self,
                       action_id: str,
                       success: bool,
                       response: Optional[Dict] = None,
                       error: Optional[str] = None,
                       status_code: Optional[int] = None,
                       duration_ms: Optional[float] = None) -> None:
        """Capture the outcome of an agent action"""
        outcome = ActionOutcome(
            action_id=action_id,
            success=success,
            response=response,
            error=error,
            duration_ms=duration_ms or 0,
            status_code=status_code
        )
        
        # Store in memory
        self.recent_outcomes.append(outcome)
        
        # Persist to disk
        self._write_outcome(outcome)
        
        # Check for patterns of failure
        if not success:
            self._analyze_failure_pattern(action_id, outcome)
    
    def capture_correction(self,
                          original_action_id: str,
                          corrected_action: Dict,
                          correction_type: str = "manual_retry") -> HumanCorrection:
        """
        Capture when a human corrects an agent mistake
        This is the KEY learning signal
        """
        # Find original action
        original = self.action_index.get(original_action_id)
        if not original:
            raise ValueError(f"Original action {original_action_id} not found")
        
        # Create corrected action object
        corrected = AgentAction(
            action_id=self._generate_action_id(),
            timestamp=time.time(),
            action_type=corrected_action.get("action_type", original.action_type),
            method=corrected_action.get("method", original.method),
            target=corrected_action.get("target", original.target),
            payload=corrected_action.get("payload", original.payload),
            headers=corrected_action.get("headers", original.headers),
            context=corrected_action.get("context", original.context),
            agent_framework=original.agent_framework,
            session_id=self.current_session
        )
        
        correction = HumanCorrection(
            original_action_id=original_action_id,
            correction_time=time.time(),
            corrected_action=corrected,
            correction_type=correction_type
        )
        
        # This is the learning moment!
        self._write_correction(correction)
        
        return correction
    
    def detect_correction_pattern(self, 
                                 window_seconds: float = 30) -> List[HumanCorrection]:
        """
        Detect when a human fixes an agent mistake
        Looks for:
        1. Failed agent action
        2. Similar successful action within time window
        3. Same target/purpose but different parameters
        """
        corrections = []
        current_time = time.time()
        
        # Find recent failures
        failed_actions = [
            (action, outcome) 
            for action in self.recent_actions 
            for outcome in self.recent_outcomes
            if outcome.action_id == action.action_id 
            and not outcome.success
            and current_time - action.timestamp < window_seconds
        ]
        
        # Look for successful retries
        for failed_action, failed_outcome in failed_actions:
            for action in self.recent_actions:
                if (action.timestamp > failed_action.timestamp and
                    action.timestamp - failed_action.timestamp < window_seconds and
                    action.target == failed_action.target and
                    action.action_type == failed_action.action_type and
                    action.action_id != failed_action.action_id):
                    
                    # Check if this succeeded
                    for outcome in self.recent_outcomes:
                        if outcome.action_id == action.action_id and outcome.success:
                            # Found a correction!
                            correction = HumanCorrection(
                                original_action_id=failed_action.action_id,
                                correction_time=action.timestamp,
                                corrected_action=action,
                                correction_type="detected_retry"
                            )
                            corrections.append(correction)
                            self._write_correction(correction)
                            break
        
        return corrections
    
    def _analyze_failure_pattern(self, action_id: str, outcome: ActionOutcome):
        """Analyze failure patterns for learning"""
        action = self.action_index.get(action_id)
        if not action:
            return
        
        # Count similar failures
        similar_failures = 0
        for past_action in self.recent_actions:
            if past_action.to_hash() == action.to_hash():
                for past_outcome in self.recent_outcomes:
                    if past_outcome.action_id == past_action.action_id and not past_outcome.success:
                        similar_failures += 1
        
        if similar_failures > 2:
            print(f"⚠️ Pattern detected: Action type {action.action_type} to {action.target} has failed {similar_failures} times")
    
    def _write_action(self, action: AgentAction):
        """Write action to trace file"""
        trace_file = self.storage_path / f"{self.current_session}.jsonl"
        with self.write_lock:
            with open(trace_file, "a") as f:
                f.write(json.dumps({
                    "type": "action",
                    "data": asdict(action)
                }) + "\n")
    
    def _write_outcome(self, outcome: ActionOutcome):
        """Write outcome to trace file"""
        trace_file = self.storage_path / f"{self.current_session}.jsonl"
        with self.write_lock:
            with open(trace_file, "a") as f:
                f.write(json.dumps({
                    "type": "outcome",
                    "data": asdict(outcome)
                }) + "\n")
    
    def _write_correction(self, correction: HumanCorrection):
        """Write correction to trace file - this is the gold!"""
        trace_file = self.storage_path / f"{self.current_session}.jsonl"
        with self.write_lock:
            with open(trace_file, "a") as f:
                data = {
                    "type": "correction",
                    "data": {
                        "original_action_id": correction.original_action_id,
                        "correction_time": correction.correction_time,
                        "corrected_action": asdict(correction.corrected_action),
                        "correction_type": correction.correction_type,
                        "confidence": correction.confidence
                    }
                }
                f.write(json.dumps(data) + "\n")
                
        print(f"✅ Learned correction: {correction.correction_type} for action {correction.original_action_id}")
    
    def get_trace_statistics(self) -> Dict:
        """Get statistics about captured traces"""
        total_actions = len(self.recent_actions)
        failed_actions = sum(
            1 for outcome in self.recent_outcomes 
            if not outcome.success
        )
        
        corrections_file = self.storage_path / f"{self.current_session}.jsonl"
        total_corrections = 0
        if corrections_file.exists():
            with open(corrections_file) as f:
                for line in f:
                    data = json.loads(line)
                    if data["type"] == "correction":
                        total_corrections += 1
        
        return {
            "session_id": self.current_session,
            "total_actions": total_actions,
            "failed_actions": failed_actions,
            "failure_rate": failed_actions / total_actions if total_actions > 0 else 0,
            "corrections_learned": total_corrections
        }


# Global instance for easy access
trace_capture = TraceCapture()