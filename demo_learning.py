#!/usr/bin/env python3
"""
Demo of AgentCorrect Learning System

Shows how AgentCorrect learns from corrections and auto-fixes future failures.
"""

import json
import subprocess
import os
from pathlib import Path

def create_failing_trace():
    """Create a trace with Stripe payment missing idempotency key."""
    trace = [
        {
            "role": "http",
            "meta": {
                "http": {
                    "method": "POST",
                    "url": "https://api.stripe.com/v1/charges",
                    "headers": {},  # Missing Idempotency-Key!
                    "body": {
                        "amount": 5000,
                        "currency": "usd",
                        "customer": "cus_123"
                    }
                }
            }
        }
    ]
    
    with open("failing_trace.jsonl", "w") as f:
        for event in trace:
            f.write(json.dumps(event) + "\n")
    
    return "failing_trace.jsonl"

def create_corrected_trace():
    """Create the corrected version with idempotency key."""
    trace = [
        {
            "role": "http",
            "meta": {
                "http": {
                    "method": "POST",
                    "url": "https://api.stripe.com/v1/charges",
                    "headers": {
                        "Idempotency-Key": "order-12345"  # Fixed!
                    },
                    "body": {
                        "amount": 5000,
                        "currency": "usd",
                        "customer": "cus_123"
                    }
                }
            }
        }
    ]
    
    with open("corrected_trace.jsonl", "w") as f:
        for event in trace:
            f.write(json.dumps(event) + "\n")
    
    return "corrected_trace.jsonl"

def create_new_failing_trace():
    """Create a new trace that should be auto-corrected."""
    trace = [
        {
            "role": "http",
            "meta": {
                "http": {
                    "method": "POST",
                    "url": "https://api.stripe.com/v1/charges",
                    "headers": {},  # Missing again!
                    "body": {
                        "amount": 9999,  # Different amount
                        "currency": "usd",
                        "customer": "cus_456"  # Different customer
                    }
                }
            }
        }
    ]
    
    with open("new_failing_trace.jsonl", "w") as f:
        for event in trace:
            f.write(json.dumps(event) + "\n")
    
    return "new_failing_trace.jsonl"

def run_command(cmd):
    """Run a command and print output."""
    print(f"\n$ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

def main():
    print("=" * 60)
    print("AGENTCORRECT LEARNING DEMO")
    print("=" * 60)
    
    # Step 1: Create a failing trace
    print("\n1️⃣ Creating a trace with missing Stripe idempotency key...")
    failing_trace = create_failing_trace()
    
    # Step 2: Analyze it (should fail)
    print("\n2️⃣ Analyzing the failing trace...")
    run_command(f"python3 -m agentcorrect analyze {failing_trace}")
    
    # Step 3: Create corrected version
    print("\n3️⃣ Creating corrected version with idempotency key...")
    corrected_trace = create_corrected_trace()
    
    # Step 4: Teach AgentCorrect the correction
    print("\n4️⃣ Teaching AgentCorrect the correction...")
    run_command(f"python3 -m agentcorrect learn {failing_trace} {corrected_trace} --failure-type missing_idempotency_key")
    
    # Step 5: Create a new failing trace
    print("\n5️⃣ Creating a NEW failing trace (different customer/amount)...")
    new_failing = create_new_failing_trace()
    
    # Step 6: Auto-correct it!
    print("\n6️⃣ Auto-correcting the new trace...")
    run_command(f"python3 -m agentcorrect autocorrect {new_failing}")
    
    # Step 7: Verify the corrected trace
    print("\n7️⃣ Analyzing the auto-corrected trace...")
    run_command(f"python3 -m agentcorrect analyze new_failing_trace_corrected.jsonl")
    
    # Step 8: Show stats
    print("\n8️⃣ Showing learning statistics...")
    run_command("python3 -m agentcorrect stats")
    
    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETE!")
    print("\nKey takeaways:")
    print("1. AgentCorrect detected the missing idempotency key")
    print("2. We taught it the correction with one example")
    print("3. It automatically fixed a NEW payment with different details")
    print("4. The pattern was learned, not just the specific instance")
    print("=" * 60)
    
    # Cleanup
    for f in ["failing_trace.jsonl", "corrected_trace.jsonl", 
              "new_failing_trace.jsonl", "new_failing_trace_corrected.jsonl"]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    main()