#!/usr/bin/env python3
"""
SIMPLE EXAMPLE: How to use AgentCorrect in your code
"""

import json
import subprocess

# ==============================================================================
# PART 1: Your AI Agent (this is YOUR code that needs protection)
# ==============================================================================

class YourAIAgent:
    """This represents YOUR AI agent that does stuff"""
    
    def __init__(self):
        self.trace_file = "agent_actions.jsonl"
    
    def log_action(self, action_data):
        """Log every action to a file for checking"""
        with open(self.trace_file, "a") as f:
            f.write(json.dumps(action_data) + "\n")
    
    def charge_customer(self, customer_id, amount):
        """AI agent tries to charge a customer"""
        
        # LOG THE ACTION (this is what AgentCorrect will check)
        self.log_action({
            "trace_id": f"payment-{customer_id}",
            "role": "http",
            "meta": {
                "http": {
                    "method": "POST",
                    "url": "https://api.stripe.com/v1/charges",
                    "headers": {
                        # OOPS! AI FORGOT THE IDEMPOTENCY KEY!
                        "Authorization": "Bearer sk_test_xxx"
                    },
                    "body": {
                        "amount": amount,
                        "customer": customer_id
                    }
                }
            }
        })
        
        print(f"AI Agent: Charging customer {customer_id} for ${amount/100}")
    
    def delete_old_users(self):
        """AI agent tries to clean up database"""
        
        # LOG THE ACTION
        self.log_action({
            "trace_id": "cleanup-001",
            "role": "sql",
            "meta": {
                "sql": {
                    # DISASTER! This would delete EVERYONE!
                    "query": "DELETE FROM users WHERE 1=1"
                }
            }
        })
        
        print("AI Agent: Cleaning up old users...")
    
    def clear_cache(self):
        """AI agent tries to clear cache"""
        
        # LOG THE ACTION
        self.log_action({
            "trace_id": "cache-001",
            "role": "redis",
            "meta": {
                "redis": {
                    # DISASTER! This wipes EVERYTHING!
                    "command": "FLUSHALL"
                }
            }
        })
        
        print("AI Agent: Clearing cache...")

# ==============================================================================
# PART 2: How to check for disasters BEFORE production
# ==============================================================================

def check_for_disasters(trace_file="agent_actions.jsonl"):
    """Run AgentCorrect to check for disasters"""
    
    print("\n" + "="*60)
    print("🔍 CHECKING AI AGENT FOR DISASTERS...")
    print("="*60 + "\n")
    
    # Run AgentCorrect
    result = subprocess.run(
        ["python", "-m", "agentcorrect", "analyze", trace_file],
        capture_output=True,
        text=True
    )
    
    # Show the output
    print(result.stdout)
    
    # Check the exit code
    if result.returncode == 2:
        print("\n" + "❌"*30)
        print("DANGER! DISASTERS DETECTED!")
        print("DO NOT DEPLOY THIS AI AGENT!")
        print("❌"*30 + "\n")
        return False
    else:
        print("\n" + "✅"*30)
        print("SAFE! No disasters detected.")
        print("OK to deploy this AI agent.")
        print("✅"*30 + "\n")
        return True

# ==============================================================================
# PART 3: Complete workflow
# ==============================================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                   HOW TO USE AGENTCORRECT                           ║
║                    Real Working Example                             ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Step 1: Your AI agent does its work
    print("STEP 1: AI Agent performs actions")
    print("-" * 40)
    
    agent = YourAIAgent()
    
    # Clear previous log
    open("agent_actions.jsonl", "w").close()
    
    # AI agent does stuff (with disasters!)
    agent.charge_customer("cus_123", 9999)  # Missing idempotency key!
    agent.delete_old_users()                # Would delete ALL users!
    agent.clear_cache()                      # Would wipe entire cache!
    
    print("\n✓ Actions logged to: agent_actions.jsonl")
    
    # Step 2: Check for disasters before deploying
    print("\nSTEP 2: Check for disasters before production")
    print("-" * 40)
    
    is_safe = check_for_disasters()
    
    # Step 3: Decision
    print("\nSTEP 3: Deployment decision")
    print("-" * 40)
    
    if is_safe:
        print("→ Proceed with deployment")
    else:
        print("→ Fix the issues first!")
        print("\nHOW TO FIX:")
        print("1. Payment: Add 'Idempotency-Key' header")
        print("2. SQL: Use specific WHERE clause (not 1=1)")
        print("3. Redis: Don't use FLUSHALL")
    
    print("\n" + "="*60)
    print("This is how you use AgentCorrect in real projects!")
    print("="*60)

if __name__ == "__main__":
    main()