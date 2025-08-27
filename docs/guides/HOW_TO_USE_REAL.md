# 🚀 HOW TO USE AGENTCORRECT IN YOUR REAL PROJECT

## The Setup (5 minutes)

### Step 1: Your AI Agent Must Log Its Actions

Your AI agent (ChatGPT, Claude, etc.) needs to save what it's doing to a file called `agent_trace.jsonl`:

```python
# In your AI agent code, add logging:
import json

def log_action(action_data):
    with open("agent_trace.jsonl", "a") as f:
        f.write(json.dumps(action_data) + "\n")

# When agent makes a payment:
log_action({
    "trace_id": "payment-001",
    "role": "http",
    "meta": {
        "http": {
            "method": "POST",
            "url": "https://api.stripe.com/v1/charges",
            "headers": headers,
            "body": payment_data
        }
    }
})

# When agent runs SQL:
log_action({
    "trace_id": "sql-001", 
    "role": "sql",
    "meta": {
        "sql": {
            "query": "DELETE FROM users WHERE user_id = 123"
        }
    }
})
```

### Step 2: Install AgentCorrect

```bash
cd C:\AI\VISIBILITYAGENT
python -m pip install -e .
```

## Real World Example

### Scenario: E-commerce AI Assistant

You have an AI agent that handles:
- Processing customer payments
- Managing inventory database
- Updating order status

### Your Workflow:

```powershell
# 1. AI agent runs and creates log file
python your_ai_agent.py
# This creates: agent_trace.jsonl

# 2. Before deploying, check for disasters
python -m agentcorrect analyze agent_trace.jsonl

# 3. Read the output
# If you see "SEV0 Issues" - STOP! Fix them first
# If you see "No issues detected" - Safe to deploy
```

## Integration Examples

### Example 1: Python Script Integration

```python
# check_before_deploy.py
import subprocess
import sys

def check_agent_safety():
    """Run AgentCorrect before deployment"""
    
    print("🔍 Checking AI agent for disasters...")
    
    result = subprocess.run(
        ["python", "-m", "agentcorrect", "analyze", "agent_trace.jsonl"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    if result.returncode == 2:
        print("❌ DISASTERS FOUND! Do not deploy!")
        print("Fix the issues above first.")
        sys.exit(1)
    else:
        print("✅ Safe to deploy!")
        return True

# Run check
check_before_deploy()
```

### Example 2: CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/check-agent.yml
name: Check AI Agent Safety

on: [push, pull_request]

jobs:
  safety-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Install AgentCorrect
        run: pip install -e .
      
      - name: Check for disasters
        run: |
          python -m agentcorrect analyze agent_trace.jsonl
          if [ $? -eq 2 ]; then
            echo "Disasters detected! Blocking deployment."
            exit 1
          fi
```

### Example 3: Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Checking AI agent for disasters..."
python -m agentcorrect analyze agent_trace.jsonl

if [ $? -eq 2 ]; then
    echo "❌ Commit blocked: AI agent has disasters!"
    exit 1
fi

echo "✅ Safe to commit"
```

## What to Log (Your Agent's Actions)

### Payment Actions
```json
{
  "role": "http",
  "meta": {
    "http": {
      "method": "POST",
      "url": "https://api.stripe.com/v1/charges",
      "headers": {
        "Authorization": "Bearer sk_test_...",
        "Idempotency-Key": "order-12345"  // This prevents duplicates!
      },
      "body": {
        "amount": 2000,
        "currency": "usd"
      }
    }
  }
}
```

### Database Actions
```json
{
  "role": "sql",
  "meta": {
    "sql": {
      "query": "UPDATE orders SET status = 'shipped' WHERE order_id = 456"
    }
  }
}
```

### Cache Actions
```json
{
  "role": "redis",
  "meta": {
    "redis": {
      "command": "DEL user:123:cart"
    }
  }
}
```

## Daily Usage Pattern

### Morning: Development
```bash
# AI agent develops new features
python ai_agent_dev.py

# Check what it did
python -m agentcorrect analyze agent_trace.jsonl
# Fix any issues found
```

### Afternoon: Testing
```bash
# AI agent runs test scenarios
python ai_agent_test.py

# Verify safety
python -m agentcorrect analyze test_trace.jsonl
```

### Evening: Before Production
```bash
# Final safety check
python -m agentcorrect analyze agent_trace.jsonl

# Only deploy if exit code is 0
if [ $? -eq 0 ]; then
    ./deploy.sh
fi
```

## Reading the Output

### ❌ BAD (Don't Deploy):
```
🚨 SEV0 - Critical Issues (CI/CD Blockers):
--------------------------------------------------
❌ Missing payment idempotency — 3 operations
❌ SQL DELETE without WHERE — 1 query
```
**Action:** Fix these issues before deploying!

### ✅ GOOD (Safe to Deploy):
```
✅ No issues detected - trace is clean!
```
**Action:** Safe to deploy to production!

## Quick Test Right Now

```powershell
# Create a test trace
@"
{"role": "http", "meta": {"http": {"method": "POST", "url": "https://api.stripe.com/v1/charges", "headers": {}, "body": {"amount": 1000}}}}
{"role": "sql", "meta": {"sql": {"query": "DELETE FROM users WHERE 1=1"}}}
"@ | Out-File -Encoding UTF8 test.jsonl

# Run AgentCorrect
python -m agentcorrect analyze test.jsonl

# You should see disasters detected!
```

## The Key Points

1. **Log what your AI agent does** → `trace.jsonl`
2. **Run AgentCorrect before deploying** → `agentcorrect analyze trace.jsonl`
3. **Exit code 2 = STOP** (disasters found)
4. **Exit code 0 = GO** (safe to deploy)

That's it! It's like spell-check but for AI disasters.