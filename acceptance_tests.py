#!/usr/bin/env python3
"""
Acceptance Tests for AgentCorrect v4
Must pass ALL tests before shipping to users
Based on requirements from user's positioning document
"""

import json
import subprocess
import tempfile
import sys
from pathlib import Path

# Add agentcorrect to path
sys.path.insert(0, 'agentcorrect')

def run_test(name, trace_data, expected_exit_code, expected_output_contains=None):
    """Run a single acceptance test."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    
    # Write trace to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for event in trace_data:
            f.write(json.dumps(event) + '\n')
        temp_file = f.name
    
    try:
        # Run agentcorrect
        result = subprocess.run(
            ['python', '-m', 'agentcorrect', 'analyze', temp_file],
            capture_output=True,
            text=True
        )
        
        print(f"Exit code: {result.returncode} (expected: {expected_exit_code})")
        print(f"Output:\n{result.stdout}")
        
        # Check exit code
        if result.returncode != expected_exit_code:
            print(f"❌ FAILED: Wrong exit code")
            return False
        
        # Check output contains expected strings
        if expected_output_contains:
            for expected in expected_output_contains:
                if expected not in result.stdout:
                    print(f"❌ FAILED: Output missing '{expected}'")
                    return False
        
        # Check for required gap/scope lines
        if "Gap in coverage:" not in result.stdout:
            print(f"❌ FAILED: Missing 'Gap in coverage' line")
            return False
        
        if "Scope:" not in result.stdout:
            print(f"❌ FAILED: Missing 'Scope' line")
            return False
        
        print(f"✅ PASSED")
        return True
        
    finally:
        Path(temp_file).unlink()

def test_stripe_missing_idempotency():
    """Test 1: Stripe payment without idempotency key → SEV0."""
    trace = [{
        "trace_id": "1",
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "headers": {"Authorization": "Bearer sk_test_xxx"},
                "body": {"amount": 9999}
            }
        }
    }]
    
    return run_test(
        "Stripe Missing Idempotency",
        trace,
        expected_exit_code=2,  # SEV0 blocks
        expected_output_contains=["SEV0", "Missing payment idempotency"]
    )

def test_stripe_with_idempotency():
    """Test 2: Stripe payment WITH idempotency key → Clean."""
    trace = [{
        "trace_id": "2",
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "headers": {
                    "Authorization": "Bearer sk_test_xxx",
                    "Idempotency-Key": "order-12345-unique"
                },
                "body": {"amount": 9999}
            }
        }
    }]
    
    return run_test(
        "Stripe With Idempotency",
        trace,
        expected_exit_code=0,  # Clean
        expected_output_contains=["No issues detected"]
    )

def test_case_insensitive_headers():
    """Test 3: Headers should be case-insensitive."""
    trace = [{
        "trace_id": "3",
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "headers": {
                    "authorization": "Bearer sk_test_xxx",
                    "idempotency-key": "order-12345"  # lowercase
                },
                "body": {"amount": 9999}
            }
        }
    }]
    
    return run_test(
        "Case Insensitive Headers",
        trace,
        expected_exit_code=0,  # Should find the key
        expected_output_contains=["No issues detected"]
    )

def test_sql_delete_without_where():
    """Test 4: SQL DELETE without WHERE → SEV0."""
    trace = [{
        "trace_id": "4",
        "role": "sql",
        "meta": {
            "sql": {
                "query": "DELETE FROM users"
            }
        }
    }]
    
    return run_test(
        "SQL DELETE without WHERE",
        trace,
        expected_exit_code=2,  # SEV0 blocks
        expected_output_contains=["SEV0", "DELETE", "WHERE"]
    )

def test_sql_delete_with_tautology():
    """Test 5: SQL DELETE with tautology → SEV0."""
    trace = [{
        "trace_id": "5",
        "role": "sql",
        "meta": {
            "sql": {
                "query": "DELETE FROM users WHERE 1=1"
            }
        }
    }]
    
    return run_test(
        "SQL DELETE with Tautology",
        trace,
        expected_exit_code=2,  # SEV0 blocks
        expected_output_contains=["SEV0"]
    )

def test_sql_delete_with_condition():
    """Test 6: SQL DELETE with real condition → Clean."""
    trace = [{
        "trace_id": "6",
        "role": "sql",
        "meta": {
            "sql": {
                "query": "DELETE FROM users WHERE user_id = 123"
            }
        }
    }]
    
    return run_test(
        "SQL DELETE with Condition",
        trace,
        expected_exit_code=0,  # Clean
        expected_output_contains=["No issues detected"]
    )

def test_redis_flushall():
    """Test 7: Redis FLUSHALL → SEV0."""
    trace = [{
        "trace_id": "7",
        "role": "redis",
        "meta": {
            "redis": {
                "command": "FLUSHALL"
            }
        }
    }]
    
    return run_test(
        "Redis FLUSHALL",
        trace,
        expected_exit_code=2,  # SEV0 blocks
        expected_output_contains=["SEV0", "Redis", "FLUSHALL"]
    )

def test_subdomain_spoofing():
    """Test 8: Subdomain spoofing should be caught."""
    trace = [{
        "trace_id": "8",
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://api.stripe.com.evil.com/v1/charges",
                "headers": {},
                "body": {"amount": 9999}
            }
        }
    }]
    
    return run_test(
        "Subdomain Spoofing Protection",
        trace,
        expected_exit_code=0,  # Not a real Stripe domain
        expected_output_contains=["No issues detected"]
    )

def test_paypal_missing_idempotency():
    """Test 9: PayPal without Request ID → SEV0."""
    trace = [{
        "trace_id": "9",
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://api.paypal.com/v2/checkout/orders",
                "headers": {},
                "body": {"amount": {"value": "100.00"}}
            }
        }
    }]
    
    return run_test(
        "PayPal Missing Request ID",
        trace,
        expected_exit_code=2,  # SEV0 blocks
        expected_output_contains=["SEV0", "PayPal", "idempotency"]
    )

def test_square_body_idempotency():
    """Test 10: Square uses body field for idempotency."""
    trace = [{
        "trace_id": "10",
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://connect.squareup.com/v2/payments",
                "headers": {},
                "body": {
                    "amount": 5000,
                    "idempotency_key": "unique-payment-123"
                }
            }
        }
    }]
    
    return run_test(
        "Square Body Idempotency",
        trace,
        expected_exit_code=0,  # Has idempotency in body
        expected_output_contains=["No issues detected"]
    )

def test_invalid_idempotency_key():
    """Test 11: Invalid idempotency keys should be caught."""
    trace = [{
        "trace_id": "11",
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "headers": {
                    "Idempotency-Key": "test"  # Too short and test value
                },
                "body": {"amount": 9999}
            }
        }
    }]
    
    return run_test(
        "Invalid Idempotency Key",
        trace,
        expected_exit_code=2,  # SEV0 for invalid key
        expected_output_contains=["SEV0", "Invalid idempotency"]
    )

def test_mongodb_drop():
    """Test 12: MongoDB dropDatabase → SEV0."""
    trace = [{
        "trace_id": "12",
        "role": "mongo",
        "meta": {
            "mongo": {
                "op": "dropDatabase"
            }
        }
    }]
    
    return run_test(
        "MongoDB Drop Database",
        trace,
        expected_exit_code=2,  # SEV0 blocks
        expected_output_contains=["SEV0", "MongoDB", "drop"]
    )

def test_s3_delete_bucket():
    """Test 13: S3 DeleteBucket → SEV0."""
    trace = [{
        "trace_id": "13",
        "role": "s3",
        "meta": {
            "s3": {
                "op": "DeleteBucket",
                "bucket": "production-data"
            }
        }
    }]
    
    return run_test(
        "S3 Delete Bucket",
        trace,
        expected_exit_code=2,  # SEV0 blocks
        expected_output_contains=["SEV0", "S3", "DeleteBucket"]
    )

def test_deterministic_output():
    """Test 14: Output should be deterministic (no timestamps)."""
    trace = [{
        "trace_id": "14",
        "role": "http",
        "meta": {
            "http": {
                "method": "GET",
                "url": "https://example.com/api"
            }
        }
    }]
    
    # Run twice and compare
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        json.dump(trace[0], f)
        f.write('\n')
        temp_file = f.name
    
    with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
        # First run
        result1 = subprocess.run(
            ['python', '-m', 'agentcorrect', 'analyze', temp_file, '--out', tmpdir1],
            capture_output=True,
            text=True
        )
        
        # Second run
        result2 = subprocess.run(
            ['python', '-m', 'agentcorrect', 'analyze', temp_file, '--out', tmpdir2],
            capture_output=True,
            text=True
        )
        
        # Compare outputs (should be identical)
        if result1.stdout != result2.stdout:
            print("❌ FAILED: Output not deterministic")
            return False
        
        # Check artifacts don't contain timestamps
        for artifact in ['findings.json', 'coverage.json']:
            path1 = Path(tmpdir1) / artifact
            path2 = Path(tmpdir2) / artifact
            if path1.exists() and path2.exists():
                content1 = path1.read_text()
                content2 = path2.read_text()
                if content1 != content2:
                    print(f"❌ FAILED: {artifact} not deterministic")
                    return False
    
    Path(temp_file).unlink()
    print("✅ PASSED: Deterministic output")
    return True

def test_windows_quickstart():
    """Test 15: Windows quickstart commands should work."""
    print("\n" + "="*60)
    print("TEST: Windows Quickstart Commands")
    print("="*60)
    
    # Test that python (not python3) works
    result = subprocess.run(
        ['python', '--version'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ FAILED: 'python' command not found")
        return False
    
    print(f"Python version: {result.stdout.strip()}")
    
    # Test module execution
    result = subprocess.run(
        ['python', '-m', 'agentcorrect', '--version'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ FAILED: Module execution failed")
        return False
    
    print("✅ PASSED: Windows commands work")
    return True

def main():
    """Run all acceptance tests."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                  AGENTCORRECT ACCEPTANCE TESTS                  ║
║                     Must Pass Before Shipping                   ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    tests = [
        test_stripe_missing_idempotency,
        test_stripe_with_idempotency,
        test_case_insensitive_headers,
        test_sql_delete_without_where,
        test_sql_delete_with_tautology,
        test_sql_delete_with_condition,
        test_redis_flushall,
        test_subdomain_spoofing,
        test_paypal_missing_idempotency,
        test_square_body_idempotency,
        test_invalid_idempotency_key,
        test_mongodb_drop,
        test_s3_delete_bucket,
        test_deterministic_output,
        test_windows_quickstart,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - READY TO SHIP!")
        return 0
    else:
        print(f"\n❌ {failed} TESTS FAILED - FIX BEFORE SHIPPING!")
        return 1

if __name__ == "__main__":
    sys.exit(main())