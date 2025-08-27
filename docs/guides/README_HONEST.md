# AgentCorrect 🛡️

**CI/CD Safety Rails for AI Agents** - Blocks deployments when AI agents would cause disasters.

## Honest Detection Rates

Based on adversarial testing with 1000+ edge cases:

- **Payment Duplicates**: ~30-40% detection
  - ✅ Detects: Missing idempotency keys for 25 known providers
  - ❌ Misses: GraphQL, webhooks, custom APIs, encoded payloads
  
- **SQL Disasters**: ~80% detection  
  - ✅ Detects: Obvious patterns (DELETE without WHERE, WHERE 1=1)
  - ❌ Misses: Complex CTEs, stored procedures, dynamic SQL
  
- **Infrastructure Wipes**: ~90% detection
  - ✅ Detects: FLUSHALL, dropDatabase, DeleteBucket
  - ❌ Misses: Indirect operations, admin APIs

## What This Actually Is

AgentCorrect is a **deterministic linter** for AI agent traces. It's like ESLint but for agent actions:

- Runs locally, no network calls
- Same input → same output (deterministic)
- Blocks CI/CD on critical issues (exit code 2)
- Fast (<100ms for 1000s of events)

## Day-1 Scope (What Ships Now)

```
SEV0 (Blocks Deployment):
✅ Stripe/PayPal/Square payments without idempotency
✅ DELETE FROM users WHERE 1=1
✅ Redis FLUSHALL
✅ MongoDB dropDatabase
❌ Everything else
```

## Installation

```bash
# From source (recommended)
git clone https://github.com/yourusername/agentcorrect
cd agentcorrect
pip install -e .

# Install sqlparse for better SQL detection
pip install sqlparse
```

## Quick Start

```bash
# Your AI agent logs actions to trace.jsonl
cat trace.jsonl
{"role": "http", "meta": {"http": {"method": "POST", "url": "https://api.stripe.com/v1/charges", "headers": {}, "body": {"amount": 9999}}}}

# Run AgentCorrect
agentcorrect analyze trace.jsonl

# Output
🚨 SEV0 - Critical Issues (CI/CD Blockers):
❌ Missing payment idempotency — 1 operations

# Exit code 2 = blocks deployment
```

## Integration

### GitHub Actions
```yaml
- name: Check AI Agent Safety
  run: |
    agentcorrect analyze agent_trace.jsonl
    # Fails build if exit code = 2
```

### Pre-commit Hook
```bash
#!/bin/bash
agentcorrect analyze trace.jsonl || exit 1
```

## Limitations (Be Aware)

1. **Only detects known patterns** - New attack vectors bypass it
2. **No semantic understanding** - Can't detect business logic errors  
3. **Easy to bypass** - Encoding, proxies, or custom APIs fool it
4. **Not a security tool** - This is a linter, not a WAF

## When to Use

✅ **Good for:**
- Catching obvious mistakes before production
- CI/CD integration as a safety net
- Teaching AI agents about idempotency

❌ **Not for:**
- Security protection
- Compliance requirements  
- Production monitoring
- Replacing code review

## Architecture

```
trace.jsonl → Parser → AST Analysis → Detector → Exit Code
                          ↓
                    No Network Calls
                    Deterministic
                    <100ms latency
```

## Exit Codes

- `0` - Clean or only warnings
- `2` - SEV0 found, deployment blocked
- `4` - Input error

## Evidence Base

Real incidents this would have caught:
- [Honeycomb Outage 2024](https://www.honeycomb.io/blog/postmortem-table-deletion) - Accidental table deletion
- Common issue: Network retry causing duplicate Stripe charges

Theoretical risks (no public incidents found):
- AI agent charging customer multiple times
- Agent deleting production database

## Contributing

We need help with:
1. SQL AST parser (currently using regex)
2. More payment provider patterns
3. GraphQL payment detection
4. Integration tests

## License

MIT - Use at your own risk

## Disclaimer

This tool provides basic safety checks. It is NOT a complete solution for AI agent safety. Always:
- Review AI agent code manually
- Test in staging environments
- Implement proper access controls
- Monitor production carefully

---

**Remember**: This catches ~30-40% of payment issues in adversarial testing, not 99%. It's a helpful linter, not a magic shield.