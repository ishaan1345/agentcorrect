"""Output formatting and artifact generation for AgentCorrect."""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


def print_human_summary(findings: List[Dict], coverage: Dict[str, Any], total_events: int, output_dir: Path = None):
    """Print human-readable summary to stdout."""
    print("=" * 60)
    print(f"AgentCorrect Analysis - {total_events} events scanned")
    print("=" * 60)
    
    # Group findings by severity
    sev0_findings = [f for f in findings if f.get("severity") == "SEV0"]
    sev1_findings = [f for f in findings if f.get("severity") == "SEV1"]
    
    if sev0_findings:
        print("\nSEV0 - Critical Issues (CI/CD Blockers):")
        print("-" * 50)
        
        # Group by type
        by_type = {}
        for f in sev0_findings:
            ftype = f.get("type", "unknown")
            by_type[ftype] = by_type.get(ftype, 0) + 1
        
        for ftype, count in by_type.items():
            if ftype == "payment_no_idempotency":
                print(f"Missing payment idempotency - {count} operations")
                print("   Fix: Add idempotency keys to payment POST requests")
            elif ftype == "sql_unbounded_write":
                print(f"SQL unbounded writes - {count} queries")
                print("   Fix: Add WHERE clauses to DELETE/UPDATE queries")
            else:
                print(f"{ftype} - {count} issues")
    
    if sev1_findings:
        print("\nSEV1 - Advisory Issues (Non-blocking):")
        print("-" * 50)
        
        by_type = {}
        for f in sev1_findings:
            ftype = f.get("type", "unknown")
            by_type[ftype] = by_type.get(ftype, 0) + 1
        
        for ftype, count in by_type.items():
            print(f"{ftype} - {count} issues")
    
    if not findings:
        print("\nNo issues detected - trace is clean!")
    
    # Coverage summary
    coverage_pct = coverage.get("coverage_percentage", 0)
    eligible = coverage.get("eligible_events", 0)
    checked = coverage.get("checked_events", 0)
    
    if eligible > 0:
        print(f"\nCoverage: checked {coverage_pct:.0f}% of eligible ops ({checked}/{eligible})")
    
    if output_dir:
        print(f"\nDetails: {output_dir}/report.html")


def write_artifacts(output_dir: Path, findings: List[Dict], coverage: Dict[str, Any], 
                   timings: Dict[str, Any], redactor: Any):
    """Write all output artifacts to directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write findings.json
    with open(output_dir / "findings.json", "w") as f:
        json.dump(findings, f, indent=2)
    
    # Write coverage.json
    with open(output_dir / "coverage.json", "w") as f:
        json.dump(coverage, f, indent=2)
    
    # Write timings.json
    with open(output_dir / "timings.json", "w") as f:
        json.dump(timings, f, indent=2)
    
    # Write HTML report
    html_content = generate_html_report(findings, coverage, timings)
    with open(output_dir / "report.html", "w") as f:
        f.write(html_content)
    
    # Write SHA256SUMS
    write_checksums(output_dir)


def generate_html_report(findings: List[Dict], coverage: Dict[str, Any], 
                         timings: Dict[str, Any]) -> str:
    """Generate HTML report."""
    timestamp = datetime.now().isoformat()
    
    sev0_count = sum(1 for f in findings if f.get("severity") == "SEV0")
    sev1_count = sum(1 for f in findings if f.get("severity") == "SEV1")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>AgentCorrect Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 20px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
        .sev0 {{ color: #d32f2f; font-weight: bold; }}
        .sev1 {{ color: #f57c00; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .finding {{ margin: 10px 0; padding: 10px; border-left: 3px solid #ccc; }}
        .finding.sev0 {{ border-color: #d32f2f; background: #ffebee; }}
        .finding.sev1 {{ border-color: #f57c00; background: #fff3e0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AgentCorrect Analysis Report</h1>
        <p>Generated: {timestamp}</p>
        <div>
            <span class="metric">Total Events: {coverage.get('total_events', 0)}</span>
            <span class="metric sev0">SEV0 Issues: {sev0_count}</span>
            <span class="metric sev1">SEV1 Issues: {sev1_count}</span>
            <span class="metric">Coverage: {coverage.get('coverage_percentage', 0):.1f}%</span>
        </div>
    </div>
    
    <h2>Findings</h2>
"""
    
    if not findings:
        html += "<p>✅ No issues detected - trace is clean!</p>"
    else:
        for finding in findings:
            sev_class = "sev0" if finding.get("severity") == "SEV0" else "sev1"
            html += f"""
    <div class="finding {sev_class}">
        <strong>{finding.get('type', 'unknown')}</strong> - {finding.get('description', '')}
        <br>Confidence: {finding.get('confidence', 0):.1%}
    </div>
"""
    
    html += """
</body>
</html>
"""
    return html


def write_checksums(output_dir: Path):
    """Write SHA256 checksums for all files."""
    checksums = []
    
    for file_path in output_dir.glob("*"):
        if file_path.name == "SHA256SUMS":
            continue
        if file_path.is_file():
            with open(file_path, "rb") as f:
                hash_obj = hashlib.sha256()
                hash_obj.update(f.read())
                checksums.append(f"{hash_obj.hexdigest()}  {file_path.name}")
    
    with open(output_dir / "SHA256SUMS", "w") as f:
        f.write("\n".join(checksums) + "\n")