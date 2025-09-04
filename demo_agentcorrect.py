#!/usr/bin/env python3
"""
AgentCorrect Demo - Make Your AI Agents Work Correctly

This demo shows how AgentCorrect:
1. Detects when agents are about to fail
2. Learns from human corrections  
3. Automatically applies corrections to prevent repeated failures
"""

import asyncio
import json
from agentcorrect.intervention import InterventionProxy

async def demo_payment_correction():
    """
    Demo: Agent forgets idempotency key, human corrects, agent never forgets again
    """
    print("\n" + "="*60)
    print("DEMO: Preventing Duplicate Stripe Charges")
    print("="*60)
    
    proxy = InterventionProxy()
    
    # Simulate agent making a Stripe charge WITHOUT idempotency key
    agent_action = {
        "type": "http",
        "method": "POST",
        "url": "https://api.stripe.com/v1/charges",
        "headers": {
            "Authorization": "Bearer sk_test_123"
        },
        "body": {
            "amount": 5000,
            "currency": "usd",
            "customer": "cus_123"
        }
    }
    
    print("\n1️⃣ Agent attempts Stripe charge WITHOUT idempotency key:")
    print(json.dumps(agent_action, indent=2))
    
    # AgentCorrect intercepts and corrects
    corrected_action = await proxy.intercept(agent_action)
    
    print("\n2️⃣ AgentCorrect automatically adds idempotency key:")
    print(json.dumps(corrected_action, indent=2))
    
    print("\n✅ Result: Duplicate charge prevented!")
    print(f"   Statistics: {proxy.get_statistics()}")

async def demo_sql_safety():
    """
    Demo: Agent tries dangerous SQL, AgentCorrect makes it safe
    """
    print("\n" + "="*60)
    print("DEMO: Preventing SQL Disasters")
    print("="*60)
    
    proxy = InterventionProxy()
    
    # Simulate agent trying to DELETE without WHERE clause
    dangerous_action = {
        "type": "sql",
        "query": "DELETE FROM users"
    }
    
    print("\n1️⃣ Agent attempts DELETE without WHERE clause:")
    print(f"   Query: {dangerous_action['query']}")
    
    # AgentCorrect intercepts and corrects
    safe_action = await proxy.intercept(dangerous_action)
    
    print("\n2️⃣ AgentCorrect adds safety WHERE clause:")
    print(f"   Query: {safe_action['query']}")
    
    print("\n✅ Result: Data loss prevented!")

async def demo_learning_from_correction():
    """
    Demo: AgentCorrect learns from human corrections
    """
    print("\n" + "="*60)
    print("DEMO: Learning From Human Corrections")
    print("="*60)
    
    from agentcorrect.trace_capture import TraceCapture
    from agentcorrect.correlation import CorrelationEngine
    from agentcorrect.diff_detection import DiffDetector
    
    trace = TraceCapture()
    correlation = CorrelationEngine()
    diff_detector = DiffDetector()
    
    # Step 1: Agent fails
    print("\n1️⃣ Agent makes API call and fails:")
    failed_action = {
        "url": "https://api.example.com/process",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": {"data": "test"}
    }
    
    action_id = trace.capture_action(
        action_type="http",
        target=failed_action["url"],
        method="POST",
        payload=failed_action["body"],
        headers=failed_action["headers"]
    )
    
    trace.capture_outcome(
        action_id=action_id,
        success=False,
        error="Missing required field: api_key"
    )
    
    correlation.track_action(action_id, failed_action)
    correlation.track_failure(action_id, {"error": "Missing api_key"})
    
    print(f"   Action: {json.dumps(failed_action, indent=2)}")
    print("   ❌ Failed: Missing api_key")
    
    # Step 2: Human corrects
    print("\n2️⃣ Human fixes by adding api_key:")
    corrected_action = {
        "url": "https://api.example.com/process",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "X-API-Key": "secret_key_123"
        },
        "body": {"data": "test"}
    }
    print(f"   Corrected: {json.dumps(corrected_action, indent=2)}")
    
    # Step 3: AgentCorrect learns
    print("\n3️⃣ AgentCorrect learns the pattern:")
    
    # Detect differences
    diffs = diff_detector.detect_api_diff(failed_action, corrected_action)
    pattern = diff_detector.extract_correction_pattern(diffs)
    
    print("   Learned corrections:")
    for diff in diffs:
        print(f"   - {diff.diff_type}: {diff.path} = {diff.corrected_value}")
    
    # Correlate the correction
    chain = correlation.correlate_correction(corrected_action, time_window=60)
    
    # Step 4: Next time, agent won't fail
    print("\n4️⃣ Next time agent attempts same action:")
    print("   AgentCorrect will automatically add X-API-Key header")
    print("   ✅ Agent works correctly!")

async def demo_cost_savings():
    """
    Demo: Show cost savings from prevented failures
    """
    print("\n" + "="*60)
    print("DEMO: Cost Savings Dashboard")
    print("="*60)
    
    proxy = InterventionProxy()
    
    # Simulate preventing multiple expensive failures
    failures_to_prevent = [
        {
            "type": "http",
            "method": "POST",
            "url": "https://api.stripe.com/v1/charges",
            "headers": {"Authorization": "Bearer sk_test"},
            "body": {"amount": 50000, "currency": "usd"}
        },
        {
            "type": "sql",
            "query": "DELETE FROM orders"
        },
        {
            "type": "sql", 
            "query": "UPDATE users SET premium = true"
        }
    ]
    
    print("\n🛡️ Preventing failures in real-time:")
    
    for action in failures_to_prevent:
        await proxy.intercept(action)
        await asyncio.sleep(0.5)  # Simulate time passing
    
    stats = proxy.get_statistics()
    
    print("\n📊 AgentCorrect Statistics:")
    print(f"   Total actions processed: {stats['total_actions']}")
    print(f"   Interventions made: {stats['interventions']}")
    print(f"   Failures prevented: {stats['failures_prevented']}")
    print(f"   💰 Cost saved: ${stats['cost_saved']:,.2f}")
    print(f"   Average savings per intervention: ${stats['average_cost_saved']:,.2f}")

async def main():
    """Run all demos"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║              AgentCorrect - Make Agents Work             ║
    ║                                                           ║
    ║     Your agent will never make the same mistake twice    ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    await demo_payment_correction()
    await asyncio.sleep(1)
    
    await demo_sql_safety()
    await asyncio.sleep(1)
    
    await demo_learning_from_correction()
    await asyncio.sleep(1)
    
    await demo_cost_savings()
    
    print("\n" + "="*60)
    print("SUMMARY: AgentCorrect Makes Your Agents Work Correctly")
    print("="*60)
    print("""
    ✅ Prevents duplicate payments by adding idempotency keys
    ✅ Stops SQL disasters by adding safety clauses
    ✅ Learns from every human correction
    ✅ Applies corrections automatically
    ✅ Saves thousands of dollars per week
    
    The result: Agents that work correctly, every time.
    
    Learn more: https://agentcorrect.ai
    """)

if __name__ == "__main__":
    asyncio.run(main())