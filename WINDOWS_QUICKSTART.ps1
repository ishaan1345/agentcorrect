# PowerShell Quickstart for AgentCorrect
# Run this in PowerShell (not Command Prompt)

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host "     AgentCorrect PowerShell Quick Start" -ForegroundColor Cyan
Write-Host "===============================================`n" -ForegroundColor Cyan

# Check Python
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found! Install from python.org" -ForegroundColor Red
    exit 1
}

# Create test trace
Write-Host "[2/5] Creating test trace file..." -ForegroundColor Yellow
@'
{"trace_id": "1", "role": "http", "meta": {"http": {"method": "POST", "url": "https://api.stripe.com/v1/charges", "headers": {}, "body": {"amount": 9999}}}}
{"trace_id": "2", "role": "sql", "meta": {"sql": {"query": "DELETE FROM users WHERE 1=1"}}}
{"trace_id": "3", "role": "redis", "meta": {"redis": {"command": "FLUSHALL"}}}
'@ | Out-File -Encoding UTF8 test_trace.jsonl
Write-Host "✓ Created: test_trace.jsonl" -ForegroundColor Green

# Install AgentCorrect
Write-Host "[3/5] Installing AgentCorrect..." -ForegroundColor Yellow
python -m pip install -e . 2>&1 | Out-Null
Write-Host "✓ AgentCorrect installed" -ForegroundColor Green

# Run analysis
Write-Host "[4/5] Running AgentCorrect analysis...`n" -ForegroundColor Yellow
python -m agentcorrect analyze test_trace.jsonl
$exitCode = $LASTEXITCODE

# Check result
Write-Host "`n[5/5] Result Analysis:" -ForegroundColor Yellow
if ($exitCode -eq 2) {
    Write-Host "🚨 DISASTERS DETECTED! (Exit code 2)" -ForegroundColor Red
    Write-Host "AgentCorrect would BLOCK this deployment." -ForegroundColor Red
} elseif ($exitCode -eq 0) {
    Write-Host "✅ Clean trace (Exit code 0)" -ForegroundColor Green
    Write-Host "Safe to deploy!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Error occurred (Exit code $exitCode)" -ForegroundColor Yellow
}

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host "To use with your AI agent:" -ForegroundColor White
Write-Host "1. Have agent log to: agent_trace.jsonl" -ForegroundColor White
Write-Host "2. Run: python -m agentcorrect analyze agent_trace.jsonl" -ForegroundColor White
Write-Host "3. Exit code 2 = Block deployment" -ForegroundColor Red
Write-Host "4. Exit code 0 = Safe to deploy" -ForegroundColor Green
Write-Host "===============================================`n" -ForegroundColor Cyan