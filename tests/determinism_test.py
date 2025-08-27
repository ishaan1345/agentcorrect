#!/usr/bin/env python3
"""
Determinism Test - Verify AgentCorrect produces identical output
Requirement: Deterministic output (no timestamps, sorted keys)
"""

import subprocess
import hashlib
import json
import tempfile
import sys
from pathlib import Path

def run_and_hash(trace_file, output_dir):
    """Run agentcorrect and return SHA256 of output files."""
    subprocess.run(
        ['python3', '-m', 'agentcorrect', 'analyze', trace_file, '--out', output_dir],
        capture_output=True,
        text=True,
        check=False
    )
    
    hashes = {}
    for file in ['findings.json', 'coverage.json']:
        filepath = Path(output_dir) / file
        if filepath.exists():
            with open(filepath, 'rb') as f:
                hashes[file] = hashlib.sha256(f.read()).hexdigest()
    
    return hashes

def main():
    print("Determinism Test - Running same input 3 times")
    print("=" * 60)
    
    # Create test trace
    test_trace = {
        "role": "http",
        "meta": {
            "http": {
                "method": "POST",
                "url": "https://api.stripe.com/v1/charges",
                "headers": {},
                "body": {"amount": 1000}
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        json.dump(test_trace, f)
        trace_file = f.name
    
    # Run 3 times
    all_hashes = []
    for i in range(3):
        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"\nRun {i+1}:")
            hashes = run_and_hash(trace_file, tmpdir)
            all_hashes.append(hashes)
            for file, hash_val in hashes.items():
                print(f"  {file}: {hash_val[:16]}...")
    
    # Verify all identical
    print("\n" + "=" * 60)
    
    if len(all_hashes) < 3:
        print("❌ FAILED: Not all runs completed")
        return 1
    
    # Check if all hashes match
    files_match = True
    for filename in ['findings.json', 'coverage.json']:
        first_hash = all_hashes[0].get(filename, '')
        if all(h.get(filename, '') == first_hash for h in all_hashes):
            print(f"✅ {filename}: All hashes identical (deterministic)")
        else:
            print(f"❌ {filename}: Hashes differ (non-deterministic!)")
            files_match = False
    
    Path(trace_file).unlink()
    
    if files_match:
        print("\n✅ PASS: Output is deterministic (no timestamps/randomness)")
        return 0
    else:
        print("\n❌ FAIL: Output is non-deterministic")
        return 1

if __name__ == "__main__":
    sys.exit(main())