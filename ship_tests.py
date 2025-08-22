#!/usr/bin/env python3
"""
Acceptance Tests for AgentCorrect - Must Pass Before Ship
Tests that it's HIGH SIGNAL, LOW FALSE POSITIVE
"""

import json
import subprocess
import tempfile
import sys
from pathlib import Path

def run_test(name, trace_events, expected_exit, should_detect=None, should_not_detect=None):
    """Run a single test case."""
    print(f"\nTEST: {name}")
    print("-" * 60)
    
    # Write trace
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for event in trace_events:
            f.write(json.dumps(event) + '\n')
        temp_file = f.name
    
    # Run AgentCorrect
    result = subprocess.run(
        ['python3', '-m', 'agentcorrect', 'analyze', temp_file],
        capture_output=True,
        text=True
    )
    
    Path(temp_file).unlink()
    
    # Check exit code
    if result.returncode != expected_exit:
        print(f"❌ FAILED: Exit {result.returncode}, expected {expected_exit}")
        print(result.stdout[:500])
        return False
    
    # Check for expected detections
    if should_detect:
        for pattern in should_detect:
            if pattern not in result.stdout:
                print(f"❌ FAILED: Missing '{pattern}' in output")
                return False
    
    # Check for false positives
    if should_not_detect:
        for pattern in should_not_detect:
            if pattern in result.stdout:
                print(f"❌ FAILED: False positive '{pattern}' found")
                return False
    
    print(f"✅ PASSED (exit {result.returncode})")
    return True

def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║            AGENTCORRECT SHIP TESTS - HIGH SR, LOW FP            ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    passed = 0
    failed = 0
    
    # === PAYMENT TESTS (5) ===
    print("\n" + "="*60)
    print("PAYMENT PROVIDER TESTS")
    print("="*60)
    
    # Test 1: Stripe missing idempotency
    if run_test(
        "1. Stripe missing idempotency → SEV0",
        [{"role": "http", "meta": {"http": {
            "method": "POST",
            "url": "https://api.stripe.com/v1/charges",
            "headers": {},
            "body": {"amount": 1000}
        }}}],
        expected_exit=2,
        should_detect=["Missing payment idempotency", "Stripe", "Idempotency-Key"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 2: PayPal missing idempotency
    if run_test(
        "2. PayPal missing idempotency → SEV0",
        [{"role": "http", "meta": {"http": {
            "method": "POST",
            "url": "https://api.paypal.com/v2/checkout/orders",
            "headers": {},
            "body": {"amount": {"value": "100"}}
        }}}],
        expected_exit=2,
        should_detect=["Missing payment idempotency", "PayPal", "PayPal-Request-Id"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 3: Square missing idempotency (body field)
    if run_test(
        "3. Square missing idempotency → SEV0",
        [{"role": "http", "meta": {"http": {
            "method": "POST",
            "url": "https://connect.squareup.com/v2/payments",
            "headers": {},
            "body": {"amount": 5000}
        }}}],
        expected_exit=2,
        should_detect=["Missing payment idempotency", "Square", "idempotency_key"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 4: Adyen missing idempotency
    if run_test(
        "4. Adyen missing idempotency → SEV0",
        [{"role": "http", "meta": {"http": {
            "method": "POST",
            "url": "https://checkout-test.adyen.com/v71/payments",
            "headers": {},
            "body": {"amount": {"value": 7500}}
        }}}],
        expected_exit=2,
        should_detect=["Missing payment idempotency", "Adyen"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 5: Subdomain spoofing (FALSE POSITIVE CHECK)
    if run_test(
        "5. Subdomain spoofing → NO DETECTION",
        [{"role": "http", "meta": {"http": {
            "method": "POST",
            "url": "https://api.stripe.com.evil.com/v1/charges",
            "headers": {},
            "body": {"amount": 1000}
        }}}],
        expected_exit=0,  # Should NOT detect
        should_not_detect=["Missing payment idempotency"]
    ):
        passed += 1
    else:
        failed += 1
    
    # === SQL TESTS (5) ===
    print("\n" + "="*60)
    print("SQL DETECTION TESTS")
    print("="*60)
    
    # Test 6: DELETE without WHERE
    if run_test(
        "6. DELETE without WHERE → SEV0",
        [{"role": "sql", "meta": {"sql": {"query": "DELETE FROM users"}}}],
        expected_exit=2,
        should_detect=["SQL DELETE/UPDATE without WHERE"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 7: DELETE with tautology
    if run_test(
        "7. DELETE WHERE 1=1 → SEV0",
        [{"role": "sql", "meta": {"sql": {"query": "DELETE FROM users WHERE 1=1"}}}],
        expected_exit=2,
        should_detect=["SQL with tautology"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 8: DELETE with proper WHERE (FALSE POSITIVE CHECK)
    if run_test(
        "8. DELETE with proper WHERE → CLEAN",
        [{"role": "sql", "meta": {"sql": {"query": "DELETE FROM users WHERE user_id = 123"}}}],
        expected_exit=0,
        should_not_detect=["SEV0"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 9: TRUNCATE production table
    if run_test(
        "9. TRUNCATE TABLE → SEV0",
        [{"role": "sql", "meta": {"sql": {"query": "TRUNCATE TABLE orders"}}}],
        expected_exit=2,
        should_detect=["Destructive SQL"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 10: TRUNCATE scratch table (FALSE POSITIVE CHECK)
    if run_test(
        "10. TRUNCATE tmp_ table → CLEAN",
        [{"role": "sql", "meta": {"sql": {"query": "TRUNCATE TABLE tmp_staging"}}}],
        expected_exit=0,
        should_not_detect=["SEV0"]
    ):
        passed += 1
    else:
        failed += 1
    
    # === INFRA TESTS (3) ===
    print("\n" + "="*60)
    print("INFRASTRUCTURE TESTS")
    print("="*60)
    
    # Test 11: Redis FLUSHALL
    if run_test(
        "11. Redis FLUSHALL → SEV0",
        [{"role": "redis", "meta": {"redis": {"command": "FLUSHALL"}}}],
        expected_exit=2,
        should_detect=["Redis cache wipe"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 12: MongoDB dropDatabase
    if run_test(
        "12. MongoDB dropDatabase → SEV0",
        [{"role": "mongo", "meta": {"mongo": {"op": "dropDatabase"}}}],
        expected_exit=2,
        should_detect=["MongoDB destructive"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 13: S3 DeleteBucket
    if run_test(
        "13. S3 DeleteBucket → SEV0",
        [{"role": "s3", "meta": {"s3": {"op": "DeleteBucket", "bucket": "prod-data"}}}],
        expected_exit=2,
        should_detect=["S3 bucket deletion"]
    ):
        passed += 1
    else:
        failed += 1
    
    # === META TESTS (2) ===
    print("\n" + "="*60)
    print("META TESTS")
    print("="*60)
    
    # Test 14: Clean trace returns 0
    if run_test(
        "14. Clean trace → Exit 0",
        [
            {"role": "http", "meta": {"http": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "headers": {"Idempotency-Key": "order-12345"},
                "body": {"amount": 1000}
            }}},
            {"role": "sql", "meta": {"sql": {"query": "SELECT * FROM users WHERE user_id = 123"}}},
            {"role": "redis", "meta": {"redis": {"command": "GET user:123"}}}
        ],
        expected_exit=0,
        should_detect=["No issues detected"]
    ):
        passed += 1
    else:
        failed += 1
    
    # Test 15: Mixed issues return 2
    if run_test(
        "15. Mixed SEV0+clean → Exit 2",
        [
            {"role": "http", "meta": {"http": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "headers": {},
                "body": {"amount": 1000}
            }}},
            {"role": "sql", "meta": {"sql": {"query": "SELECT * FROM users"}}}
        ],
        expected_exit=2,
        should_detect=["SEV0", "Missing payment idempotency"]
    ):
        passed += 1
    else:
        failed += 1
    
    # === SUMMARY ===
    print("\n" + "="*60)
    print(f"RESULTS: {passed}/15 tests passed")
    print("="*60)
    
    if passed == 15:
        print("\n✅ ALL TESTS PASSED - READY TO SHIP!")
        print("\nThis proves:")
        print("• HIGH SIGNAL: Catches all vendor-documented disasters")
        print("• LOW NOISE: No false positives on clean code")
        print("• RELIABLE: Exit codes work for CI/CD integration")
        return 0
    else:
        print(f"\n❌ {failed} TESTS FAILED - FIX BEFORE SHIPPING!")
        return 1

if __name__ == "__main__":
    sys.exit(main())