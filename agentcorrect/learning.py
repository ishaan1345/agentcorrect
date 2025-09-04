"""
AgentCorrect Learning System - Learn from human corrections

This module watches for human corrections to detected failures and learns
patterns to auto-correct next time.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class Correction:
    """A learned correction pattern."""
    id: str
    failure_type: str  # e.g. "missing_idempotency_key"
    original_action: Dict[str, Any]
    corrected_action: Dict[str, Any]
    learned_at: str
    applied_count: int = 0
    success_count: int = 0
    confidence: float = 0.0
    
    def calculate_confidence(self):
        """Calculate confidence based on successful applications."""
        if self.applied_count == 0:
            return 0.0
        return self.success_count / self.applied_count

class CorrectionLearner:
    """Learns from human corrections to agent failures."""
    
    def __init__(self, corrections_dir: str = ".agentcorrect"):
        self.corrections_dir = Path(corrections_dir)
        self.corrections_dir.mkdir(exist_ok=True)
        self.corrections_file = self.corrections_dir / "corrections.jsonl"
        self.corrections = self.load_corrections()
        
    def load_corrections(self) -> Dict[str, Correction]:
        """Load existing corrections from disk."""
        corrections = {}
        if self.corrections_file.exists():
            with open(self.corrections_file, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    corr = Correction(**data)
                    corrections[corr.id] = corr
        return corrections
    
    def save_correction(self, correction: Correction):
        """Persist a correction to disk."""
        with open(self.corrections_file, 'a') as f:
            f.write(json.dumps(asdict(correction)) + '\n')
    
    def learn_from_trace_diff(self, 
                              original_trace: str, 
                              corrected_trace: str,
                              failure_type: str):
        """
        Learn from the difference between original failed trace and corrected trace.
        
        Args:
            original_trace: JSONL trace that failed
            corrected_trace: JSONL trace after human correction
            failure_type: Type of failure detected (e.g. "missing_idempotency_key")
        """
        # Parse traces
        original_actions = [json.loads(line) for line in original_trace.strip().split('\n')]
        corrected_actions = [json.loads(line) for line in corrected_trace.strip().split('\n')]
        
        # Find the correction
        for orig, corr in zip(original_actions, corrected_actions):
            if orig != corr:
                # Found a difference - this is the correction
                correction_id = hashlib.md5(
                    f"{failure_type}_{json.dumps(orig)}".encode()
                ).hexdigest()[:8]
                
                correction = Correction(
                    id=correction_id,
                    failure_type=failure_type,
                    original_action=orig,
                    corrected_action=corr,
                    learned_at=datetime.now().isoformat()
                )
                
                self.corrections[correction_id] = correction
                self.save_correction(correction)
                
                print(f"✅ LEARNED CORRECTION: {failure_type}")
                print(f"   Original: {json.dumps(orig)[:100]}...")
                print(f"   Corrected: {json.dumps(corr)[:100]}...")
                
                return correction
        
        return None
    
    def find_applicable_correction(self, action: Dict[str, Any], failure_type: str) -> Optional[Correction]:
        """
        Find a correction that applies to this action.
        
        Args:
            action: The action that might need correction
            failure_type: The type of failure detected
            
        Returns:
            Applicable correction if found, None otherwise
        """
        for correction in self.corrections.values():
            if correction.failure_type != failure_type:
                continue
                
            # Check if this correction matches the action pattern
            if self._matches_pattern(action, correction.original_action):
                return correction
        
        return None
    
    def _matches_pattern(self, action: Dict[str, Any], pattern: Dict[str, Any]) -> bool:
        """
        Check if an action matches a correction pattern.
        
        This is where the magic happens - pattern matching to determine
        if a learned correction applies to a new action.
        """
        # For HTTP requests
        if action.get('role') == 'http' and pattern.get('role') == 'http':
            action_meta = action.get('meta', {}).get('http', {})
            pattern_meta = pattern.get('meta', {}).get('http', {})
            
            # Match by URL and method
            if (action_meta.get('url') == pattern_meta.get('url') and
                action_meta.get('method') == pattern_meta.get('method')):
                
                # Check if it's missing the same thing (e.g., idempotency key)
                action_headers = action_meta.get('headers', {})
                pattern_headers = pattern_meta.get('headers', {})
                
                # If pattern was missing idempotency key and current action is too
                if 'Idempotency-Key' not in pattern_headers and 'Idempotency-Key' not in action_headers:
                    return True
        
        # For SQL queries
        elif action.get('role') == 'sql' and pattern.get('role') == 'sql':
            action_query = action.get('meta', {}).get('sql', {}).get('query', '')
            pattern_query = pattern.get('meta', {}).get('sql', {}).get('query', '')
            
            # Similar structure check (both DELETE without WHERE, etc.)
            if self._similar_sql_structure(action_query, pattern_query):
                return True
        
        return False
    
    def _similar_sql_structure(self, query1: str, query2: str) -> bool:
        """Check if two SQL queries have similar problematic structure."""
        # Simple check - both missing WHERE
        q1_upper = query1.upper()
        q2_upper = query2.upper()
        
        if 'DELETE' in q1_upper and 'DELETE' in q2_upper:
            if 'WHERE' not in q1_upper and 'WHERE' not in q2_upper:
                return True
        
        return False
    
    def apply_correction(self, action: Dict[str, Any], correction: Correction) -> Dict[str, Any]:
        """
        Apply a learned correction to an action.
        
        Args:
            action: The action to correct
            correction: The correction to apply
            
        Returns:
            Corrected action
        """
        # Deep copy the action
        import copy
        corrected = copy.deepcopy(action)
        
        # Apply the correction based on what changed
        if action.get('role') == 'http':
            # For HTTP, typically adding headers
            orig_headers = correction.original_action.get('meta', {}).get('http', {}).get('headers', {})
            corr_headers = correction.corrected_action.get('meta', {}).get('http', {}).get('headers', {})
            
            # Find what was added
            for key, value in corr_headers.items():
                if key not in orig_headers:
                    # This header was added in the correction
                    if 'meta' not in corrected:
                        corrected['meta'] = {}
                    if 'http' not in corrected['meta']:
                        corrected['meta']['http'] = {}
                    if 'headers' not in corrected['meta']['http']:
                        corrected['meta']['http']['headers'] = {}
                    
                    # Generate appropriate value (e.g., unique ID for idempotency)
                    if key == 'Idempotency-Key':
                        import uuid
                        corrected['meta']['http']['headers'][key] = str(uuid.uuid4())
                    else:
                        corrected['meta']['http']['headers'][key] = value
        
        # Update stats
        correction.applied_count += 1
        self.save_correction(correction)
        
        return corrected


class AutoCorrector:
    """
    Auto-correct agent actions based on learned patterns.
    
    This integrates with the existing AgentCorrect detector to
    automatically fix problems we've seen before.
    """
    
    def __init__(self, learner: CorrectionLearner):
        self.learner = learner
        self.stats = {
            'intercepted': 0,
            'corrected': 0,
            'failures_prevented': 0
        }
    
    def process_trace(self, trace_path: str) -> str:
        """
        Process a trace file and auto-correct known failures.
        
        Args:
            trace_path: Path to JSONL trace file
            
        Returns:
            Path to corrected trace file
        """
        try:
            from .detectors import AgentCorrectV4
        except ImportError:
            from detectors import AgentCorrectV4
        
        detector = AgentCorrectV4()
        corrected_trace_lines = []
        corrections_applied = []
        
        with open(trace_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                action = json.loads(line)
                self.stats['intercepted'] += 1
                
                # Check if this action would trigger a failure
                findings = detector.check_single_action(action)
                
                if findings:
                    # This action has problems
                    failure_type = findings[0]['type']  # e.g., 'missing_idempotency'
                    
                    # Do we have a correction for this?
                    correction = self.learner.find_applicable_correction(action, failure_type)
                    
                    if correction:
                        # Apply the correction
                        corrected_action = self.learner.apply_correction(action, correction)
                        corrected_trace_lines.append(json.dumps(corrected_action))
                        
                        self.stats['corrected'] += 1
                        self.stats['failures_prevented'] += 1
                        
                        corrections_applied.append({
                            'line': line_num,
                            'failure_type': failure_type,
                            'correction_id': correction.id
                        })
                        
                        print(f"🔧 AUTO-CORRECTED (line {line_num}): {failure_type}")
                    else:
                        # No correction available yet
                        corrected_trace_lines.append(line.strip())
                        print(f"⚠️  NO CORRECTION AVAILABLE (line {line_num}): {failure_type}")
                else:
                    # This action is fine
                    corrected_trace_lines.append(line.strip())
        
        # Write corrected trace
        corrected_path = trace_path.replace('.jsonl', '_corrected.jsonl')
        with open(corrected_path, 'w') as f:
            for line in corrected_trace_lines:
                f.write(line + '\n')
        
        # Print summary
        print("\n📊 AUTO-CORRECTION SUMMARY")
        print(f"   Actions processed: {self.stats['intercepted']}")
        print(f"   Corrections applied: {self.stats['corrected']}")
        print(f"   Failures prevented: {self.stats['failures_prevented']}")
        
        if corrections_applied:
            print("\n   Corrections applied:")
            for corr in corrections_applied:
                print(f"     Line {corr['line']}: {corr['failure_type']} (correction {corr['correction_id']})")
        
        return corrected_path


# CLI Integration
def add_learning_commands(subparsers):
    """Add learning commands to AgentCorrect CLI."""
    
    # learn command
    learn_parser = subparsers.add_parser('learn', help='Learn from corrected trace')
    learn_parser.add_argument('original', help='Original trace that failed')
    learn_parser.add_argument('corrected', help='Corrected trace after human fix')
    learn_parser.add_argument('--failure-type', required=True, help='Type of failure that was corrected')
    
    # autocorrect command
    auto_parser = subparsers.add_parser('autocorrect', help='Auto-correct trace using learned patterns')
    auto_parser.add_argument('input', help='Input trace to auto-correct')
    auto_parser.add_argument('--output', help='Output path for corrected trace')
    
    # stats command
    stats_parser = subparsers.add_parser('stats', help='Show learning statistics')


if __name__ == '__main__':
    # Test the learning system
    learner = CorrectionLearner()
    
    # Example: Learn from a Stripe correction
    original = '{"role":"http","meta":{"http":{"method":"POST","url":"https://api.stripe.com/v1/charges","headers":{},"body":{"amount":1000}}}}'
    corrected = '{"role":"http","meta":{"http":{"method":"POST","url":"https://api.stripe.com/v1/charges","headers":{"Idempotency-Key":"order-123"},"body":{"amount":1000}}}}'
    
    learner.learn_from_trace_diff(original, corrected, "missing_idempotency_key")
    
    # Now test auto-correction
    auto_corrector = AutoCorrector(learner)
    
    # This should get auto-corrected
    new_action = json.loads('{"role":"http","meta":{"http":{"method":"POST","url":"https://api.stripe.com/v1/charges","headers":{},"body":{"amount":2000}}}}')
    
    correction = learner.find_applicable_correction(new_action, "missing_idempotency_key")
    if correction:
        corrected_action = learner.apply_correction(new_action, correction)
        print(f"\n✅ Successfully auto-corrected: {json.dumps(corrected_action)}")