#!/usr/bin/env python3
"""
AgentCorrect CLI - Command-line interface for testing and using AgentCorrect
"""

import sys
import json
import argparse
from .core import AgentCorrect


def main():
    parser = argparse.ArgumentParser(
        description="AgentCorrect - Autocorrect for AI Agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fix an API call
  echo '{"url": "https://api.stripe.com/v1/charges", "method": "POST"}' | agentcorrect
  
  # Fix a SQL query
  agentcorrect --action '{"query": "DELETE FROM users"}'
  
  # Check what corrections would be made
  agentcorrect --action '{"message": "I understand your frustration"}' --dry-run
        """
    )
    
    parser.add_argument(
        "--action",
        type=str,
        help="JSON action to fix (or pipe via stdin)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without applying"
    )
    
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo showing common fixes"
    )
    
    args = parser.parse_args()
    
    if args.demo:
        run_demo()
        return
    
    # Get action from args or stdin
    if args.action:
        try:
            action = json.loads(args.action)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON - {e}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        try:
            action = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON from stdin - {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    # Fix the action
    corrector = AgentCorrect()
    fixed = corrector.fix(action)
    corrections = corrector.get_corrections()
    
    # Show results
    if args.dry_run:
        print("Original action:")
        print(json.dumps(action, indent=2))
        print("\nCorrections that would be made:")
        if corrections:
            for c in corrections:
                print(f"  • {c.issue} → {c.fix} (confidence: {c.confidence:.0%})")
        else:
            print("  No corrections needed")
        print("\nFixed action:")
        print(json.dumps(fixed, indent=2))
    else:
        # Output fixed action as JSON
        print(json.dumps(fixed, indent=2))
        
        # Show corrections to stderr
        if corrections:
            print(f"\n✅ Fixed {len(corrections)} issues:", file=sys.stderr)
            for c in corrections:
                print(f"  • {c.issue} → {c.fix}", file=sys.stderr)


def run_demo():
    """Run demo showing common fixes"""
    print("🔧 AgentCorrect Demo - Common AI Agent Fixes\n")
    print("=" * 60)
    
    demos = [
        {
            "name": "Stripe API call without auth",
            "action": {
                "url": "https://api.stripe.com/v1/charges",
                "method": "POST",
                "body": {"amount": 5000, "currency": "usd"}
            }
        },
        {
            "name": "SQL DELETE without WHERE",
            "action": {
                "query": "DELETE FROM users"
            }
        },
        {
            "name": "Payment without idempotency",
            "action": {
                "type": "payment",
                "url": "https://api.stripe.com/v1/payment_intents",
                "method": "POST",
                "amount": 10000,
                "headers": {"Authorization": "Bearer sk_test_123"}
            }
        },
        {
            "name": "Customer message with poor tone",
            "action": {
                "type": "customer_message",
                "message": "I understand your frustration, but unfortunately, I cannot help with this issue."
            }
        },
        {
            "name": "SELECT without LIMIT",
            "action": {
                "type": "sql_query",
                "query": "SELECT * FROM orders WHERE status = 'pending'"
            }
        }
    ]
    
    corrector = AgentCorrect()
    
    for demo in demos:
        print(f"\n📝 {demo['name']}")
        print("-" * 40)
        
        print("Before:")
        print(json.dumps(demo['action'], indent=2))
        
        fixed = corrector.fix(demo['action'])
        corrections = corrector.get_corrections()
        
        if corrections:
            print("\nCorrections:")
            for c in corrections:
                print(f"  ✅ {c.issue} → {c.fix}")
        else:
            print("\nNo corrections needed")
        
        if demo['action'] != fixed:
            print("\nAfter:")
            print(json.dumps(fixed, indent=2))
    
    print("\n" + "=" * 60)
    print("✨ AgentCorrect - Keeping your AI agents safe and correct!")


if __name__ == "__main__":
    main()