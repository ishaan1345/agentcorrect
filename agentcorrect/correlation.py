"""
Correlation System for AgentCorrect
Links agent actions → failures → human corrections
"""

import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import hashlib

@dataclass
class CorrelationChain:
    """
    Represents the full chain from action to correction
    This is the complete learning signal
    """
    chain_id: str
    agent_action: Dict
    failure_outcome: Dict
    human_correction: Dict
    time_to_failure: float  # seconds from action to failure
    time_to_correction: float  # seconds from failure to correction
    correlation_confidence: float  # How confident we are these are related
    failure_type: str  # Classification of what went wrong
    correction_type: str  # Classification of how it was fixed
    context: Dict = field(default_factory=dict)

@dataclass
class CorrelationPattern:
    """A pattern learned from multiple correlation chains"""
    pattern_id: str
    failure_signature: str  # Hash identifying this type of failure
    correction_template: Dict  # The fix to apply
    context_requirements: Dict  # When to apply this fix
    confidence: float
    application_count: int = 0
    success_count: int = 0
    example_chains: List[str] = field(default_factory=list)  # Chain IDs

class CorrelationEngine:
    """
    Correlates agent actions with failures and human corrections
    This is how we understand what went wrong and how to fix it
    """
    
    def __init__(self, storage_path: str = ".agentcorrect/correlations"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Active tracking
        self.pending_actions: Dict[str, Dict] = {}  # action_id → action data
        self.failed_actions: Dict[str, Dict] = {}  # action_id → failure data
        self.correlation_chains: List[CorrelationChain] = []
        self.patterns: Dict[str, CorrelationPattern] = {}
        
        # Load existing patterns
        self._load_patterns()
    
    def track_action(self, action_id: str, action_data: Dict):
        """Track an agent action for potential correlation"""
        self.pending_actions[action_id] = {
            "data": action_data,
            "timestamp": time.time()
        }
        
        # Clean up old pending actions (>5 minutes)
        self._cleanup_old_pending()
    
    def track_failure(self, action_id: str, failure_data: Dict):
        """Track a failure outcome for correlation"""
        if action_id in self.pending_actions:
            self.failed_actions[action_id] = {
                "action": self.pending_actions[action_id],
                "failure": failure_data,
                "failure_time": time.time()
            }
            # Move from pending to failed
            del self.pending_actions[action_id]
    
    def correlate_correction(self, 
                           correction_data: Dict,
                           time_window: float = 60.0) -> Optional[CorrelationChain]:
        """
        Correlate a human correction with a recent failure
        This is the key moment where we learn
        """
        correction_time = time.time()
        best_match = None
        best_score = 0.0
        
        # Find the most likely failure this correction is fixing
        for action_id, failed in self.failed_actions.items():
            # Time proximity check
            time_since_failure = correction_time - failed["failure_time"]
            if time_since_failure > time_window:
                continue
            
            # Calculate correlation score
            score = self._calculate_correlation_score(
                failed["action"]["data"],
                failed["failure"],
                correction_data,
                time_since_failure
            )
            
            if score > best_score:
                best_score = score
                best_match = (action_id, failed)
        
        if best_match and best_score > 0.7:  # Confidence threshold
            action_id, failed = best_match
            
            # Create correlation chain
            chain = CorrelationChain(
                chain_id=self._generate_chain_id(),
                agent_action=failed["action"]["data"],
                failure_outcome=failed["failure"],
                human_correction=correction_data,
                time_to_failure=failed["failure_time"] - failed["action"]["timestamp"],
                time_to_correction=correction_time - failed["failure_time"],
                correlation_confidence=best_score,
                failure_type=self._classify_failure(failed["failure"]),
                correction_type=self._classify_correction(failed["action"]["data"], correction_data),
                context=self._extract_context(failed["action"]["data"])
            )
            
            # Store the chain
            self.correlation_chains.append(chain)
            self._save_chain(chain)
            
            # Learn pattern from this chain
            self._learn_pattern(chain)
            
            # Clean up
            del self.failed_actions[action_id]
            
            print(f"✅ Correlated: {chain.failure_type} → {chain.correction_type} (confidence: {best_score:.0%})")
            
            return chain
        
        return None
    
    def find_matching_pattern(self, action: Dict) -> Optional[CorrelationPattern]:
        """
        Find a pattern that matches the current action
        This is used to prevent failures before they happen
        """
        action_signature = self._generate_action_signature(action)
        
        for pattern in self.patterns.values():
            if self._pattern_matches(action, action_signature, pattern):
                return pattern
        
        return None
    
    def _calculate_correlation_score(self,
                                    action: Dict,
                                    failure: Dict, 
                                    correction: Dict,
                                    time_delta: float) -> float:
        """
        Calculate how likely a correction is related to a failure
        """
        score = 1.0
        
        # Time proximity (exponential decay)
        time_score = max(0.0, 1.0 - (time_delta / 60.0))  # Decay over 1 minute
        score *= (0.3 + 0.7 * time_score)
        
        # Target similarity
        if "url" in action and "url" in correction:
            if action["url"] == correction["url"]:
                score *= 1.2  # Boost for same endpoint
            elif self._same_domain(action["url"], correction["url"]):
                score *= 1.1  # Smaller boost for same domain
        
        # Method similarity
        if "method" in action and "method" in correction:
            if action["method"] == correction["method"]:
                score *= 1.1
        
        # Structural similarity
        if "body" in action and "body" in correction:
            similarity = self._structural_similarity(action["body"], correction["body"])
            score *= (0.5 + 0.5 * similarity)
        
        # Known failure patterns
        if self._is_known_failure_pattern(failure):
            score *= 1.2
        
        return min(1.0, score)  # Cap at 1.0
    
    def _classify_failure(self, failure: Dict) -> str:
        """Classify the type of failure"""
        if "error" in failure:
            error = failure["error"].lower()
            
            if "idempotency" in error or "duplicate" in error:
                return "duplicate_request"
            elif "auth" in error or "unauthorized" in error:
                return "auth_failure"
            elif "rate limit" in error:
                return "rate_limit"
            elif "timeout" in error:
                return "timeout"
            elif "not found" in error or "404" in error:
                return "not_found"
            elif "validation" in error or "invalid" in error:
                return "validation_error"
        
        if "status_code" in failure:
            code = failure["status_code"]
            if code == 401:
                return "auth_failure"
            elif code == 429:
                return "rate_limit"
            elif code == 404:
                return "not_found"
            elif code >= 500:
                return "server_error"
            elif code >= 400:
                return "client_error"
        
        return "unknown_failure"
    
    def _classify_correction(self, original: Dict, corrected: Dict) -> str:
        """Classify the type of correction applied"""
        # Check what was added
        if "headers" in corrected:
            corrected_headers = set(k.lower() for k in corrected.get("headers", {}))
            original_headers = set(k.lower() for k in original.get("headers", {}))
            
            added = corrected_headers - original_headers
            if any("idempotency" in h for h in added):
                return "added_idempotency"
            if any("auth" in h or "key" in h for h in added):
                return "fixed_auth"
        
        # Check body changes
        if "body" in corrected and "body" in original:
            if isinstance(corrected["body"], dict) and isinstance(original["body"], dict):
                added_keys = set(corrected["body"].keys()) - set(original["body"].keys())
                if added_keys:
                    return "added_fields"
                
                # Check for value changes
                for key in original["body"]:
                    if key in corrected["body"] and original["body"][key] != corrected["body"][key]:
                        return "changed_values"
        
        # SQL specific
        if "query" in original and "query" in corrected:
            if "WHERE" not in original["query"].upper() and "WHERE" in corrected["query"].upper():
                return "added_where_clause"
            if "LIMIT" not in original["query"].upper() and "LIMIT" in corrected["query"].upper():
                return "added_limit"
        
        return "general_correction"
    
    def _learn_pattern(self, chain: CorrelationChain):
        """
        Learn a reusable pattern from a correlation chain
        """
        # Generate signature for this failure type
        failure_sig = self._generate_failure_signature(chain)
        
        if failure_sig in self.patterns:
            # Update existing pattern
            pattern = self.patterns[failure_sig]
            pattern.example_chains.append(chain.chain_id)
            
            # Update confidence based on consistency
            if self._is_consistent_correction(pattern, chain):
                pattern.confidence = min(1.0, pattern.confidence * 1.1)
            else:
                pattern.confidence *= 0.9
        else:
            # Create new pattern
            pattern = CorrelationPattern(
                pattern_id=self._generate_pattern_id(),
                failure_signature=failure_sig,
                correction_template=self._extract_correction_template(chain),
                context_requirements=chain.context,
                confidence=0.7,  # Start with moderate confidence
                example_chains=[chain.chain_id]
            )
            self.patterns[failure_sig] = pattern
        
        self._save_pattern(pattern)
    
    def _generate_action_signature(self, action: Dict) -> str:
        """Generate a signature for an action"""
        sig_parts = []
        
        if "action_type" in action:
            sig_parts.append(action["action_type"])
        if "method" in action:
            sig_parts.append(action["method"])
        if "url" in action:
            from urllib.parse import urlparse
            parsed = urlparse(action["url"])
            sig_parts.append(parsed.netloc)
            sig_parts.append(parsed.path)
        
        return ":".join(sig_parts)
    
    def _generate_failure_signature(self, chain: CorrelationChain) -> str:
        """Generate a signature for a failure pattern"""
        sig_parts = [
            chain.failure_type,
            self._generate_action_signature(chain.agent_action),
        ]
        return hashlib.md5(":".join(sig_parts).encode()).hexdigest()[:16]
    
    def _extract_correction_template(self, chain: CorrelationChain) -> Dict:
        """Extract a reusable correction template from a chain"""
        from .diff_detection import DiffDetector
        
        detector = DiffDetector()
        diffs = detector.detect_diff(chain.agent_action, chain.human_correction)
        
        template = {
            "additions": {},
            "modifications": {},
            "removals": []
        }
        
        for diff in diffs:
            if diff.importance < 0.5:
                continue
                
            if diff.diff_type == "added_field":
                template["additions"][diff.path] = diff.corrected_value
            elif diff.diff_type in ["changed_value", "type_change"]:
                template["modifications"][diff.path] = {
                    "from": diff.original_value,
                    "to": diff.corrected_value
                }
            elif diff.diff_type == "removed_field":
                template["removals"].append(diff.path)
        
        return template
    
    def _pattern_matches(self, action: Dict, signature: str, pattern: CorrelationPattern) -> bool:
        """Check if an action matches a pattern"""
        # Check context requirements
        for key, value in pattern.context_requirements.items():
            if key not in action or action[key] != value:
                return False
        
        # Check structural match
        # This is simplified - in production would be more sophisticated
        return True
    
    def _same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs have the same domain"""
        from urllib.parse import urlparse
        return urlparse(url1).netloc == urlparse(url2).netloc
    
    def _structural_similarity(self, obj1: Any, obj2: Any) -> float:
        """Calculate structural similarity between two objects"""
        if type(obj1) != type(obj2):
            return 0.0
        
        if isinstance(obj1, dict) and isinstance(obj2, dict):
            keys1 = set(obj1.keys())
            keys2 = set(obj2.keys())
            if not keys1 and not keys2:
                return 1.0
            intersection = len(keys1 & keys2)
            union = len(keys1 | keys2)
            return intersection / union if union > 0 else 0.0
        
        return 1.0 if obj1 == obj2 else 0.0
    
    def _is_known_failure_pattern(self, failure: Dict) -> bool:
        """Check if this matches a known failure pattern"""
        # Check against common patterns
        if "error" in failure:
            error = failure["error"].lower()
            known_patterns = [
                "idempotency", "duplicate", "already exists",
                "missing required", "invalid", "unauthorized"
            ]
            return any(pattern in error for pattern in known_patterns)
        return False
    
    def _is_consistent_correction(self, pattern: CorrelationPattern, chain: CorrelationChain) -> bool:
        """Check if a new correction is consistent with the pattern"""
        new_template = self._extract_correction_template(chain)
        
        # Check if corrections are similar
        # Simplified - in production would be more sophisticated
        return new_template.get("additions") == pattern.correction_template.get("additions")
    
    def _cleanup_old_pending(self):
        """Remove old pending actions that likely won't correlate"""
        current_time = time.time()
        cutoff_time = 300  # 5 minutes
        
        to_remove = [
            action_id for action_id, data in self.pending_actions.items()
            if current_time - data["timestamp"] > cutoff_time
        ]
        
        for action_id in to_remove:
            del self.pending_actions[action_id]
    
    def _generate_chain_id(self) -> str:
        """Generate unique chain ID"""
        return f"chain_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    def _generate_pattern_id(self) -> str:
        """Generate unique pattern ID"""
        return f"pattern_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    def _extract_context(self, action: Dict) -> Dict:
        """Extract relevant context from an action"""
        context = {}
        
        if "url" in action:
            from urllib.parse import urlparse
            parsed = urlparse(action["url"])
            context["domain"] = parsed.netloc
            context["path"] = parsed.path
        
        for key in ["action_type", "method", "agent_framework"]:
            if key in action:
                context[key] = action[key]
        
        return context
    
    def _save_chain(self, chain: CorrelationChain):
        """Save correlation chain to disk"""
        chain_file = self.storage_path / "chains.jsonl"
        with open(chain_file, "a") as f:
            f.write(json.dumps({
                "chain_id": chain.chain_id,
                "agent_action": chain.agent_action,
                "failure_outcome": chain.failure_outcome,
                "human_correction": chain.human_correction,
                "time_to_failure": chain.time_to_failure,
                "time_to_correction": chain.time_to_correction,
                "correlation_confidence": chain.correlation_confidence,
                "failure_type": chain.failure_type,
                "correction_type": chain.correction_type,
                "context": chain.context
            }) + "\n")
    
    def _save_pattern(self, pattern: CorrelationPattern):
        """Save pattern to disk"""
        patterns_file = self.storage_path / "patterns.json"
        
        # Load existing patterns
        patterns_dict = {}
        if patterns_file.exists():
            with open(patterns_file) as f:
                patterns_dict = json.load(f)
        
        # Update with new pattern
        patterns_dict[pattern.pattern_id] = {
            "pattern_id": pattern.pattern_id,
            "failure_signature": pattern.failure_signature,
            "correction_template": pattern.correction_template,
            "context_requirements": pattern.context_requirements,
            "confidence": pattern.confidence,
            "application_count": pattern.application_count,
            "success_count": pattern.success_count,
            "example_chains": pattern.example_chains
        }
        
        # Save back
        with open(patterns_file, "w") as f:
            json.dump(patterns_dict, f, indent=2)
    
    def _load_patterns(self):
        """Load patterns from disk"""
        patterns_file = self.storage_path / "patterns.json"
        if patterns_file.exists():
            with open(patterns_file) as f:
                patterns_dict = json.load(f)
                
            for pattern_data in patterns_dict.values():
                pattern = CorrelationPattern(**pattern_data)
                self.patterns[pattern.failure_signature] = pattern

# Global instance
correlation_engine = CorrelationEngine()