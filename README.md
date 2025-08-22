# AgentCorrect

Stop your AI agents from destroying production.

## What This Does

AgentCorrect scans AI agent traces and blocks deployments when it finds:
- Payment API calls missing idempotency keys (duplicate charges)
- SQL queries that would delete/modify all records
- Infrastructure commands that would wipe caches or databases

Exit code 2 fails your CI/CD pipeline. That's it.

## Who Needs This

You need this if:
- Your AI agents call payment APIs (Stripe, PayPal, Square, etc.)
- Your AI agents execute SQL queries  
- Your AI agents touch Redis, MongoDB, or cloud infrastructure
- You've ever had an agent accidentally charge a customer twice
- You've ever had an agent delete production data

You don't need this if:
- Your agents are read-only
- Your agents don't touch money or data
- You manually review every agent action

## Installation

```bash
pip install agentcorrect
```

## Usage

```bash
# Analyze agent trace
agentcorrect analyze trace.jsonl

# In CI/CD pipeline
agentcorrect analyze trace.jsonl || exit 1
```

## What It Catches

### Payment Disasters
- Stripe: Missing Idempotency-Key header → Prevents duplicate charges
- PayPal: Missing PayPal-Request-Id → Prevents duplicate charges  
- Square: Missing idempotency_key in body → Prevents duplicate charges
- 25+ payment providers with their exact requirements

### SQL Disasters  
- `DELETE FROM users WHERE 1=1` → Blocked (tautology)
- `DELETE FROM users` → Blocked (no WHERE clause)
- `TRUNCATE TABLE orders` → Blocked (data loss)
- `DROP TABLE customers` → Blocked (irreversible)

### Infrastructure Disasters
- Redis: `FLUSHALL` → Blocked (cache wipe)
- MongoDB: `dropDatabase` → Blocked (database deletion)
- S3: `DeleteBucket` → Blocked (storage deletion)

## Real Example

Your agent does this:
```python
# Agent tries to charge customer
response = stripe.charges.create(amount=5000, currency="usd")
# Network timeout, agent retries
response = stripe.charges.create(amount=5000, currency="usd") 
# Customer charged twice - $100 lost
```

AgentCorrect catches this:
```
Missing payment idempotency
Provider: Stripe  
Fix: Add header 'Idempotency-Key: <unique-order-id>'
Exit code: 2 (Build Failed)
```

## Trace Format

JSONL format - one JSON object per line:

```jsonl
{"role":"http","meta":{"http":{"method":"POST","url":"https://api.stripe.com/v1/charges","headers":{},"body":{"amount":1000}}}}
{"role":"sql","meta":{"sql":{"query":"DELETE FROM users WHERE id = 123"}}}
{"role":"redis","meta":{"redis":{"command":"GET user:123"}}}
```

## Why This Works

1. **Vendor-specific knowledge**: We know Stripe needs `Idempotency-Key` in headers, Square needs `idempotency_key` in body. This isn't guesswork.

2. **AST parsing for SQL**: We parse SQL structurally, not with regex. No false positives.

3. **Exit codes for CI/CD**: Non-zero exit fails the build. Standard CI/CD practice.

## CI/CD Integration

### GitHub Actions
```yaml
- name: Test Agent Safety
  run: |
    python run_agent.py > trace.jsonl
    agentcorrect analyze trace.jsonl
```

### GitLab CI
```yaml
test-agent:
  script:
    - python run_agent.py > trace.jsonl
    - agentcorrect analyze trace.jsonl
```

## Testing

Run the verification suite:
```bash
python verify.py        # Test all detections
python ship_tests.py    # 15 acceptance tests
./quick_proof.sh       # 60-second proof
```

## Limitations

- Only catches what we know about (95% of payment providers, common SQL patterns)
- Requires trace data in JSONL format
- Can't prevent disasters if you skip the CI/CD check

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

Built for teams who learned the hard way that AI agents need guardrails.