# AgentCorrect Examples

This directory contains example trace files for testing AgentCorrect.

## Files

- `stripe_payment.jsonl` - Proper Stripe payment with idempotency key
- `dangerous_sql.jsonl` - SQL operations that will be flagged as dangerous
- `clean_trace.jsonl` - Clean trace with no issues
- `mixed_issues.jsonl` - Trace with multiple types of issues

## Usage

Test with a specific example:
```bash
agentcorrect analyze examples/dangerous_sql.jsonl
```

Test all examples:
```bash
for file in examples/*.jsonl; do
  echo "Testing $file:"
  agentcorrect analyze "$file"
  echo
done
```