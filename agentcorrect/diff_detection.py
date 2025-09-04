"""
Diff Detection Engine for AgentCorrect
Identifies when humans manually fix agent mistakes
"""

import json
import difflib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import ast

# Simple DeepDiff replacement for demo
class DeepDiff:
    def __init__(self, obj1, obj2, ignore_order=True, view='tree'):
        self.obj1 = obj1
        self.obj2 = obj2
        self.diffs = self._compute_diffs(obj1, obj2)
    
    def _compute_diffs(self, obj1, obj2):
        diffs = {}
        if isinstance(obj1, dict) and isinstance(obj2, dict):
            # Find added keys
            added = set(obj2.keys()) - set(obj1.keys())
            if added:
                diffs['dictionary_item_added'] = [MockItem(None, obj2[k], k) for k in added]
            
            # Find removed keys  
            removed = set(obj1.keys()) - set(obj2.keys())
            if removed:
                diffs['dictionary_item_removed'] = [MockItem(obj1[k], None, k) for k in removed]
            
            # Find changed values
            changed = []
            for k in set(obj1.keys()) & set(obj2.keys()):
                if obj1[k] != obj2[k]:
                    changed.append(MockItem(obj1[k], obj2[k], k))
            if changed:
                diffs['values_changed'] = changed
        
        return diffs
    
    def __contains__(self, key):
        return key in self.diffs
    
    def __getitem__(self, key):
        return self.diffs.get(key, [])

class MockItem:
    def __init__(self, t1, t2, path):
        self.t1 = t1
        self.t2 = t2
        self.path = path
    
    def __str__(self):
        return f"['{self.path}']"

@dataclass
class DiffResult:
    """Represents a detected difference between agent and human action"""
    diff_type: str  # added_field, removed_field, changed_value, changed_structure
    path: str  # JSON path to the difference
    original_value: Any
    corrected_value: Any
    importance: float  # 0-1 score of how important this diff is

class DiffDetector:
    """
    Detects differences between failed agent actions and human corrections
    This is how we learn what needs to be fixed
    """
    
    CRITICAL_FIELDS = {
        # Payment related
        "idempotency_key", "idempotencykey", "idempotency-key",
        "x-idempotency-key", "stripe-idempotency-key",
        
        # SQL safety
        "where", "where_clause", "limit", "conditions",
        
        # Auth headers
        "authorization", "api-key", "x-api-key", "bearer",
        
        # Safety fields
        "dry_run", "test_mode", "sandbox", "confirm",
    }
    
    def detect_diff(self, 
                   failed_action: Dict,
                   corrected_action: Dict) -> List[DiffResult]:
        """
        Detect all differences between failed and corrected action
        Returns list of diffs ranked by importance
        """
        diffs = []
        
        # Deep diff analysis
        deep_diff = DeepDiff(
            failed_action, 
            corrected_action,
            ignore_order=True,
            view='tree'
        )
        
        # Added fields (human added something agent missed)
        if 'dictionary_item_added' in deep_diff:
            for item in deep_diff['dictionary_item_added']:
                path = self._extract_path(str(item))
                value = item.t2
                
                diff = DiffResult(
                    diff_type="added_field",
                    path=path,
                    original_value=None,
                    corrected_value=value,
                    importance=self._calculate_importance(path, value)
                )
                diffs.append(diff)
        
        # Removed fields (human removed something agent added)
        if 'dictionary_item_removed' in deep_diff:
            for item in deep_diff['dictionary_item_removed']:
                path = self._extract_path(str(item))
                value = item.t1
                
                diff = DiffResult(
                    diff_type="removed_field",
                    path=path,
                    original_value=value,
                    corrected_value=None,
                    importance=self._calculate_importance(path, value) * 0.5  # Removals less critical
                )
                diffs.append(diff)
        
        # Changed values
        if 'values_changed' in deep_diff:
            for item in deep_diff['values_changed']:
                path = self._extract_path(str(item))
                
                diff = DiffResult(
                    diff_type="changed_value",
                    path=path,
                    original_value=item.t1,
                    corrected_value=item.t2,
                    importance=self._calculate_importance(path, item.t2)
                )
                diffs.append(diff)
        
        # Type changes (e.g., string to int)
        if 'type_changes' in deep_diff:
            for item in deep_diff['type_changes']:
                path = self._extract_path(str(item))
                
                diff = DiffResult(
                    diff_type="type_change",
                    path=path,
                    original_value=item.t1,
                    corrected_value=item.t2,
                    importance=0.7  # Type changes are usually important
                )
                diffs.append(diff)
        
        # Sort by importance
        diffs.sort(key=lambda x: x.importance, reverse=True)
        
        return diffs
    
    def detect_sql_diff(self, 
                       failed_query: str,
                       corrected_query: str) -> List[DiffResult]:
        """
        Special handling for SQL query differences
        """
        diffs = []
        
        failed_upper = failed_query.upper()
        corrected_upper = corrected_query.upper()
        
        # Check for WHERE clause addition
        if "WHERE" not in failed_upper and "WHERE" in corrected_upper:
            where_start = corrected_upper.index("WHERE")
            where_clause = corrected_query[where_start:]
            
            diffs.append(DiffResult(
                diff_type="added_where_clause",
                path="sql.where",
                original_value=None,
                corrected_value=where_clause,
                importance=1.0  # Critical for safety
            ))
        
        # Check for LIMIT addition
        if "LIMIT" not in failed_upper and "LIMIT" in corrected_upper:
            limit_start = corrected_upper.index("LIMIT")
            limit_clause = corrected_query[limit_start:].split()[1]
            
            diffs.append(DiffResult(
                diff_type="added_limit",
                path="sql.limit",
                original_value=None,
                corrected_value=limit_clause,
                importance=0.8
            ))
        
        # Check for dangerous operation replacement
        dangerous_ops = ["TRUNCATE", "DROP", "DELETE FROM"]
        for op in dangerous_ops:
            if op in failed_upper and op not in corrected_upper:
                diffs.append(DiffResult(
                    diff_type="removed_dangerous_op",
                    path="sql.operation",
                    original_value=op,
                    corrected_value=self._extract_operation(corrected_query),
                    importance=1.0
                ))
        
        return diffs
    
    def detect_api_diff(self,
                       failed_request: Dict,
                       corrected_request: Dict) -> List[DiffResult]:
        """
        Special handling for API request differences
        Focus on headers, auth, and idempotency
        """
        diffs = []
        
        # Check headers
        failed_headers = failed_request.get("headers", {})
        corrected_headers = corrected_request.get("headers", {})
        
        # Case-insensitive header comparison
        failed_headers_lower = {k.lower(): v for k, v in failed_headers.items()}
        corrected_headers_lower = {k.lower(): v for k, v in corrected_headers.items()}
        
        # Check for added headers
        for header, value in corrected_headers_lower.items():
            if header not in failed_headers_lower:
                # This is a critical addition
                importance = 1.0 if any(
                    key in header for key in ["idempotency", "auth", "api-key"]
                ) else 0.6
                
                diffs.append(DiffResult(
                    diff_type="added_header",
                    path=f"headers.{header}",
                    original_value=None,
                    corrected_value=value,
                    importance=importance
                ))
        
        # Check body differences
        failed_body = failed_request.get("body", {})
        corrected_body = corrected_request.get("body", {})
        
        if isinstance(failed_body, dict) and isinstance(corrected_body, dict):
            body_diffs = self.detect_diff(failed_body, corrected_body)
            diffs.extend(body_diffs)
        
        return diffs
    
    def extract_correction_pattern(self, diffs: List[DiffResult]) -> Dict:
        """
        Extract a reusable pattern from the differences
        This pattern can be applied to future similar failures
        """
        pattern = {
            "must_add": [],
            "must_remove": [],
            "must_change": [],
            "conditions": {}
        }
        
        for diff in diffs:
            if diff.importance < 0.5:
                continue  # Skip low-importance diffs
            
            if diff.diff_type == "added_field":
                pattern["must_add"].append({
                    "path": diff.path,
                    "value": diff.corrected_value,
                    "importance": diff.importance
                })
            
            elif diff.diff_type == "removed_field":
                pattern["must_remove"].append({
                    "path": diff.path,
                    "importance": diff.importance
                })
            
            elif diff.diff_type in ["changed_value", "type_change"]:
                pattern["must_change"].append({
                    "path": diff.path,
                    "from": diff.original_value,
                    "to": diff.corrected_value,
                    "importance": diff.importance
                })
        
        return pattern
    
    def _calculate_importance(self, path: str, value: Any) -> float:
        """
        Calculate importance score for a diff
        Higher score = more critical to correct
        """
        path_lower = path.lower()
        
        # Critical fields get highest importance
        for critical in self.CRITICAL_FIELDS:
            if critical in path_lower:
                return 1.0
        
        # Payment/money related
        if any(word in path_lower for word in ["payment", "amount", "price", "charge"]):
            return 0.9
        
        # Security related
        if any(word in path_lower for word in ["auth", "token", "key", "secret"]):
            return 0.9
        
        # Safety related
        if any(word in path_lower for word in ["confirm", "dry_run", "test", "sandbox"]):
            return 0.8
        
        # Data mutation
        if any(word in path_lower for word in ["delete", "update", "modify", "remove"]):
            return 0.8
        
        # Check value characteristics
        if isinstance(value, str):
            # UUIDs and keys
            if len(value) > 20 and "-" in value:
                return 0.7
            # Likely test values
            if value.lower() in ["test", "demo", "null", "undefined"]:
                return 0.3
        
        # Default importance
        return 0.5
    
    def _extract_path(self, diff_str: str) -> str:
        """Extract JSON path from DeepDiff string representation"""
        # Parse path from DeepDiff output
        if "[" in diff_str and "]" in diff_str:
            start = diff_str.index("[")
            end = diff_str.rindex("]")
            path = diff_str[start+1:end]
            return path.replace("'", "").replace("][", ".")
        return diff_str
    
    def _extract_operation(self, query: str) -> str:
        """Extract the main operation from a SQL query"""
        query_upper = query.upper().strip()
        operations = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "TRUNCATE"]
        
        for op in operations:
            if query_upper.startswith(op):
                return op
        
        return "UNKNOWN"
    
    def generate_correction_rule(self, 
                                 pattern: Dict,
                                 context: Dict) -> Dict:
        """
        Generate a correction rule that can be applied automatically
        """
        rule = {
            "id": f"rule_{hash(json.dumps(pattern, sort_keys=True))}",
            "pattern": pattern,
            "context_requirements": self._extract_context_requirements(context),
            "confidence": 0.5,  # Start with medium confidence
            "applications": 0,
            "successes": 0
        }
        
        return rule
    
    def _extract_context_requirements(self, context: Dict) -> Dict:
        """
        Extract the context conditions when this correction should apply
        """
        requirements = {}
        
        # Extract relevant context
        if "url" in context:
            # Extract domain for API-specific rules
            from urllib.parse import urlparse
            parsed = urlparse(context["url"])
            requirements["domain"] = parsed.netloc
        
        if "action_type" in context:
            requirements["action_type"] = context["action_type"]
        
        if "method" in context:
            requirements["method"] = context["method"]
        
        if "agent_framework" in context:
            requirements["agent_framework"] = context["agent_framework"]
        
        return requirements


# Example usage showing how corrections are detected
def example_payment_correction():
    detector = DiffDetector()
    
    # Agent forgot idempotency key
    failed_action = {
        "url": "https://api.stripe.com/v1/charges",
        "method": "POST",
        "headers": {
            "Authorization": "Bearer sk_test_123"
        },
        "body": {
            "amount": 5000,
            "currency": "usd"
        }
    }
    
    # Human added idempotency key
    corrected_action = {
        "url": "https://api.stripe.com/v1/charges",
        "method": "POST",
        "headers": {
            "Authorization": "Bearer sk_test_123",
            "Idempotency-Key": "unique-key-12345"
        },
        "body": {
            "amount": 5000,
            "currency": "usd"
        }
    }
    
    # Detect the difference
    diffs = detector.detect_api_diff(failed_action, corrected_action)
    
    # Extract pattern
    pattern = detector.extract_correction_pattern(diffs)
    
    print("Detected corrections:")
    for diff in diffs:
        print(f"  - {diff.diff_type}: {diff.path}")
        print(f"    Importance: {diff.importance:.0%}")
        print(f"    Correction: {diff.original_value} → {diff.corrected_value}")
    
    print("\nExtracted pattern:")
    print(json.dumps(pattern, indent=2))
    
    return pattern