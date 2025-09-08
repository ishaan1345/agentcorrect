# AgentCorrect - Autocorrect for AI Agents

**Stop AI agents from making the same mistakes over and over.**

AgentCorrect automatically fixes common AI agent mistakes before they cause problems - missing auth headers, dangerous SQL queries, forgotten idempotency keys, poor customer tone, and more.

## What It Does

✅ **Adds missing auth headers** - Never forget API authentication  
✅ **Adds idempotency keys** - Prevent duplicate payments  
✅ **Blocks dangerous SQL** - No more `DELETE FROM users`  
✅ **Fixes customer tone** - Professional, helpful responses  
✅ **Validates API calls** - Correct parameters and headers  

## Installation

```bash
pip install agentcorrect
```

## Quick Start

```python
import agentcorrect

# Fix any AI agent action
action = {
    "url": "https://api.stripe.com/v1/charges",
    "method": "POST",
    "body": {"amount": 5000}
}

fixed = agentcorrect.fix(action)
# Automatically adds Authorization header and Idempotency-Key
```

## LangChain Integration

```python
from langchain.agents import initialize_agent
from agentcorrect import protect_agent

agent = initialize_agent(tools, llm, ...)
safe_agent = protect_agent(agent)

# All agent actions are now auto-corrected
result = safe_agent.run("Process refund for order 123")
```

## OpenAI Integration

```python
from agentcorrect import OpenAIFunctionCorrector

corrector = OpenAIFunctionCorrector()

# Fix function calls before execution
function_call = response.choices[0].message.function_call
fixed_call = corrector.fix_function_call(function_call)
```

## Common Fixes

### API Calls
- Adds missing Authorization headers
- Adds Idempotency-Key for payments
- Adds Content-Type for POST/PUT

### SQL Queries
- Blocks DELETE/UPDATE without WHERE
- Blocks TRUNCATE and DROP operations
- Adds LIMIT to SELECT queries

### Customer Messages
- Replaces "I understand your frustration" → "I can help you with this"
- Replaces "Unfortunately, I cannot" → "Let me find a solution"
- Fixes negative and unhelpful language

### Payments
- Always adds idempotency keys
- Validates amounts
- Checks for customer identifiers

## How It Works

AgentCorrect uses deterministic rules to fix common mistakes. No machine learning, no training, no complexity - just simple fixes that work.

```python
corrector = AgentCorrect()

# Fix a dangerous SQL query
action = {"query": "DELETE FROM users"}
fixed = corrector.fix(action)
# Returns: {"query": "DELETE FROM users", "blocked": True, "error": "DELETE without WHERE clause is dangerous"}

# Fix missing auth
action = {"url": "https://api.stripe.com/v1/charges", "method": "POST"}
fixed = corrector.fix(action)
# Returns: {..., "headers": {"Authorization": "Bearer ${STRIPE_KEY}", "Idempotency-Key": "..."}}
```

## CLI Usage

```bash
# Fix an action from command line
echo '{"url": "https://api.stripe.com/v1/charges", "method": "POST"}' | agentcorrect

# Run demo
agentcorrect --demo
```

## Why This Exists

AI agents make predictable mistakes:
- They forget auth headers
- They write dangerous SQL
- They don't add idempotency keys
- They use poor customer service tone

Instead of fixing these manually every time, AgentCorrect fixes them automatically.

## License

MIT