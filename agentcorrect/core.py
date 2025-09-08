#!/usr/bin/env python3
"""
AgentCorrect - Autocorrect for AI Agents
Automatically fixes common AI agent mistakes before they cause problems
"""

import json
import uuid
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class Correction:
    """A correction that was applied"""
    issue: str
    fix: str
    confidence: float = 1.0


class AgentCorrect:
    """
    Autocorrect for AI agents - fixes common mistakes automatically
    
    Usage:
        corrector = AgentCorrect()
        fixed_action = corrector.fix(agent_action)
    """
    
    def __init__(self, auto_fix: bool = True):
        self.auto_fix = auto_fix
        self.corrections_made = []
        
    def fix(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix common AI agent mistakes
        
        Args:
            action: The AI agent's intended action
            
        Returns:
            Fixed action with corrections applied
        """
        fixed = action.copy()
        self.corrections_made = []
        
        # Detect action type
        action_type = self._detect_action_type(fixed)
        
        # Apply fixes based on type
        # Always apply API fixes first for HTTP calls
        if "url" in fixed or "endpoint" in fixed:
            fixed = self._fix_api_call(fixed)
        
        if action_type == "sql_query":
            fixed = self._fix_sql_query(fixed)
        elif action_type == "payment":
            fixed = self._fix_payment(fixed)
        elif action_type == "email":
            fixed = self._fix_email(fixed)
        elif action_type == "customer_message":
            fixed = self._fix_customer_message(fixed)
            
        return fixed
    
    def _detect_action_type(self, action: Dict) -> str:
        """Detect what type of action this is"""
        
        # Check explicit type
        if "type" in action:
            return action["type"]
        
        # Detect from content
        if "url" in action or "endpoint" in action:
            url = action.get("url", action.get("endpoint", ""))
            if any(p in url for p in ["stripe.com", "paypal.com", "square"]):
                return "payment"
            return "api_call"
        
        if "query" in action or "sql" in action:
            return "sql_query"
        
        if "to" in action and "@" in str(action.get("to", "")):
            return "email"
        
        if "message" in action or "response" in action:
            return "customer_message"
        
        return "unknown"
    
    def _fix_api_call(self, action: Dict) -> Dict:
        """Fix common API call mistakes"""
        
        # Add missing auth headers
        if "headers" not in action:
            action["headers"] = {}
        
        headers = action["headers"]
        url = action.get("url", "")
        
        # Add auth if missing
        auth_headers = [h.lower() for h in headers.keys()]
        if not any(h in auth_headers for h in ["authorization", "x-api-key", "api-key"]):
            if "stripe.com" in url:
                headers["Authorization"] = "Bearer ${STRIPE_KEY}"
                self.corrections_made.append(Correction(
                    "Missing Stripe auth",
                    "Added Authorization header"
                ))
            elif "api." in url:
                headers["Authorization"] = "Bearer ${API_KEY}"
                self.corrections_made.append(Correction(
                    "Missing API auth",
                    "Added Authorization header"
                ))
        
        # Add idempotency key for mutations
        method = action.get("method", "GET").upper()
        if method in ["POST", "PUT", "PATCH"]:
            if "stripe.com" in url and "Idempotency-Key" not in headers:
                headers["Idempotency-Key"] = str(uuid.uuid4())
                self.corrections_made.append(Correction(
                    "Missing idempotency key",
                    "Added Idempotency-Key for payment"
                ))
        
        # Add content-type if missing
        if method in ["POST", "PUT", "PATCH"] and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
            self.corrections_made.append(Correction(
                "Missing Content-Type",
                "Added Content-Type header"
            ))
        
        return action
    
    def _fix_sql_query(self, action: Dict) -> Dict:
        """Fix dangerous SQL queries"""
        
        query = action.get("query", action.get("sql", ""))
        original_query = query
        
        # Block destructive queries without WHERE
        query_upper = query.upper()
        
        # DELETE without WHERE
        if "DELETE" in query_upper and "WHERE" not in query_upper:
            action["blocked"] = True
            action["error"] = "DELETE without WHERE clause is dangerous"
            self.corrections_made.append(Correction(
                "DELETE without WHERE",
                "Blocked dangerous query",
                confidence=1.0
            ))
            return action
        
        # TRUNCATE or DROP
        if any(danger in query_upper for danger in ["TRUNCATE", "DROP TABLE", "DROP DATABASE"]):
            action["blocked"] = True
            action["error"] = "Destructive operation blocked"
            self.corrections_made.append(Correction(
                "Destructive SQL operation",
                "Blocked dangerous query",
                confidence=1.0
            ))
            return action
        
        # UPDATE without WHERE
        if "UPDATE" in query_upper and "WHERE" not in query_upper:
            action["blocked"] = True
            action["error"] = "UPDATE without WHERE clause is dangerous"
            self.corrections_made.append(Correction(
                "UPDATE without WHERE",
                "Blocked dangerous query",
                confidence=1.0
            ))
            return action
        
        # Add LIMIT to SELECT if missing
        if "SELECT" in query_upper and "LIMIT" not in query_upper:
            query = query.rstrip(";") + " LIMIT 1000;"
            action["query"] = query
            self.corrections_made.append(Correction(
                "SELECT without LIMIT",
                "Added LIMIT 1000",
                confidence=0.9
            ))
        
        return action
    
    def _fix_payment(self, action: Dict) -> Dict:
        """Fix payment-related actions"""
        
        # Always add idempotency key
        headers = action.get("headers", {})
        
        if "Idempotency-Key" not in headers and "idempotency_key" not in action.get("body", {}):
            if "headers" not in action:
                action["headers"] = {}
            action["headers"]["Idempotency-Key"] = str(uuid.uuid4())
            self.corrections_made.append(Correction(
                "Payment without idempotency",
                "Added idempotency key",
                confidence=1.0
            ))
        
        # Validate amount
        amount = action.get("amount", action.get("body", {}).get("amount", 0))
        if amount <= 0:
            action["blocked"] = True
            action["error"] = "Invalid payment amount"
            self.corrections_made.append(Correction(
                "Invalid payment amount",
                "Blocked payment",
                confidence=1.0
            ))
        
        # Check for customer ID
        if not any(k in action.get("body", {}) for k in ["customer", "customer_id", "source"]):
            action["warning"] = "Missing customer identifier"
            self.corrections_made.append(Correction(
                "Missing customer ID",
                "Flagged for review",
                confidence=0.8
            ))
        
        return action
    
    def _fix_email(self, action: Dict) -> Dict:
        """Fix email-related actions"""
        
        # Check for unsubscribe link in marketing emails
        body = action.get("body", action.get("html", ""))
        to = action.get("to", "")
        
        # If sending to multiple recipients, ensure unsubscribe
        if isinstance(to, list) and len(to) > 1:
            if "unsubscribe" not in body.lower():
                action["body"] = body + "\n\n<a href='${UNSUBSCRIBE_URL}'>Unsubscribe</a>"
                self.corrections_made.append(Correction(
                    "Mass email without unsubscribe",
                    "Added unsubscribe link",
                    confidence=0.9
                ))
        
        # Validate email addresses
        if isinstance(to, str) and "@" not in to:
            action["blocked"] = True
            action["error"] = "Invalid email address"
            self.corrections_made.append(Correction(
                "Invalid email address",
                "Blocked email",
                confidence=1.0
            ))
        
        return action
    
    def _fix_customer_message(self, action: Dict) -> Dict:
        """Fix customer-facing messages"""
        
        message = action.get("message", action.get("response", ""))
        original = message
        
        # Fix common tone issues
        replacements = {
            "I understand your frustration": "I can help you with this",
            "Unfortunately, I cannot": "Let me find a solution",
            "That's not possible": "Let me explore alternatives",
            "You're wrong": "I see there may be some confusion",
            "As I already said": "To clarify",
            "Obviously": "To help explain",
        }
        
        for bad, good in replacements.items():
            if bad.lower() in message.lower():
                # Case-insensitive replacement
                pattern = re.compile(re.escape(bad), re.IGNORECASE)
                message = pattern.sub(good, message)
                self.corrections_made.append(Correction(
                    f"Poor tone: '{bad}'",
                    f"Replaced with: '{good}'",
                    confidence=0.8
                ))
        
        if message != original:
            action["message"] = message
        
        return action
    
    def get_corrections(self) -> List[Correction]:
        """Get list of corrections that were made"""
        return self.corrections_made


# Convenience function
def autocorrect(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Quick autocorrect function
    
    Example:
        from agentcorrect import autocorrect
        
        fixed_action = autocorrect({
            "url": "https://api.stripe.com/v1/charges",
            "method": "POST",
            "body": {"amount": 5000}
        })
        # Automatically adds auth header and idempotency key
    """
    corrector = AgentCorrect()
    return corrector.fix(action)