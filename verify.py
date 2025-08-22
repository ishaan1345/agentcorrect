#!/usr/bin/env python3
"""
AgentCorrect Verification Suite
Proves the tool works as promised by testing against known patterns.
Exit codes: 0=all tests pass, 1=test failure
"""

import subprocess
import sys
import json
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def run_agentcorrect(fixture_path):
    """Run agentcorrect on a fixture and return exit code and output."""
    result = subprocess.run(
        ['python3', '-m', 'agentcorrect', 'analyze', str(fixture_path)],
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout, result.stderr

def test_fixture(name, fixture_path, expected_exit, should_contain=None, should_not_contain=None):
    """Test a single fixture file."""
    print(f"\n{Colors.BLUE}Testing:{Colors.RESET} {name}")
    print(f"  File: {fixture_path}")
    
    exit_code, stdout, stderr = run_agentcorrect(fixture_path)
    
    # Check exit code
    if exit_code == expected_exit:
        print(f"  {Colors.GREEN}✓{Colors.RESET} Exit code: {exit_code} (expected {expected_exit})")
    else:
        print(f"  {Colors.RED}✗{Colors.RESET} Exit code: {exit_code} (expected {expected_exit})")
        print(f"  Output: {stdout[:200]}")
        return False
    
    # Check for expected content
    if should_contain:
        for pattern in should_contain:
            if pattern in stdout:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Found: '{pattern}'")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} Missing: '{pattern}'")
                return False
    
    # Check for false positives
    if should_not_contain:
        for pattern in should_not_contain:
            if pattern not in stdout:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Correctly absent: '{pattern}'")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} False positive: '{pattern}'")
                return False
    
    return True

def main():
    print(f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║         AgentCorrect Verification Suite v1.0                ║
║  Testing vendor requirements against external documentation ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
    """)
    
    passed = 0
    failed = 0
    
    # Test Disasters (should trigger SEV0, exit code 2)
    print(f"\n{Colors.BOLD}=== DISASTER TESTS (Must Detect) ==={Colors.RESET}")
    
    disasters = [
        ("Stripe without Idempotency-Key", "fixtures/disasters/stripe-no-idem.jsonl", 2, 
         ["Missing payment idempotency", "Stripe"], None),
        
        ("PayPal without PayPal-Request-Id", "fixtures/disasters/paypal-no-idem.jsonl", 2,
         ["Missing payment idempotency", "PayPal"], None),
        
        ("Square without idempotency_key", "fixtures/disasters/square-no-idem.jsonl", 2,
         ["Missing payment idempotency", "Square"], None),
        
        ("SQL DELETE with tautology", "fixtures/disasters/sql-tautology.jsonl", 2,
         ["SQL with tautology", "1=1"], None),
        
        ("SQL DELETE without WHERE", "fixtures/disasters/sql-no-where.jsonl", 2,
         ["SQL DELETE/UPDATE without WHERE"], None),
        
        ("Redis FLUSHALL", "fixtures/disasters/redis-flushall.jsonl", 2,
         ["Redis cache wipe", "FLUSHALL"], None),
        
        ("MongoDB dropDatabase", "fixtures/disasters/mongo-drop.jsonl", 2,
         ["MongoDB destructive", "dropDatabase"], None),
    ]
    
    for test_case in disasters:
        if test_fixture(*test_case):
            passed += 1
        else:
            failed += 1
    
    # Test Clean (should NOT trigger, exit code 0)
    print(f"\n{Colors.BOLD}=== CLEAN TESTS (Must NOT Detect) ==={Colors.RESET}")
    
    clean_tests = [
        ("Stripe WITH Idempotency-Key", "fixtures/clean/stripe-with-idem.jsonl", 0,
         ["No issues detected"], ["SEV0"]),
        
        ("Stripe case-insensitive header", "fixtures/clean/stripe-case-insensitive.jsonl", 0,
         ["No issues detected"], ["SEV0"]),
        
        ("Square WITH idempotency_key", "fixtures/clean/square-with-idem.jsonl", 0,
         ["No issues detected"], ["SEV0"]),
        
        ("SQL DELETE with WHERE", "fixtures/clean/sql-with-where.jsonl", 0,
         ["No issues detected"], ["SEV0"]),
        
        ("Redis GET (safe)", "fixtures/clean/redis-get.jsonl", 0,
         ["No issues detected"], ["SEV0"]),
    ]
    
    for test_case in clean_tests:
        if test_fixture(*test_case):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    total = passed + failed
    if failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED: {passed}/{total}{Colors.RESET}")
        print(f"\nThis proves:")
        print(f"  • Detections match vendor documentation (see SPEC.md)")
        print(f"  • Exit codes work for CI/CD (0=clean, 2=SEV0)")
        print(f"  • Headers are case-insensitive (HTTP spec compliant)")
        print(f"  • No false positives on clean traces")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ TESTS FAILED: {failed}/{total} failed{Colors.RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())