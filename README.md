# AgentCorrect

A provider-agnostic execution guard for AI agent tools.

Your model proposes an action. AgentCorrect evaluates policy **before** calling the
tool, then allows it, blocks it, or pauses for a human. Your model provider and your
policy classifier are independent choices.

```text
Any model → complete tool call → AgentCorrect → registered tool → result
                                    │
                       hard deny / human review / allow
                                    │
                       deterministic rules + optional classifier
```

This is an **alpha Python library**, not a sandbox or an installed coding-agent
plugin. It guards calls routed through `Gate.execute()`. It cannot intercept a
provider's hosted tools, another process, or calls made directly to an unwrapped tool.

## Quick start

Python 3.8+:

```sh
pip install .
python examples/runtime_gate.py
```

The example writes real files in a temporary directory, verifies that a protected
file was never created, pauses a second write for approval, and rejects approval replay.
No API key is needed.

```python
from agentcorrect.runtime import Action, Gate, Policy, Rule, Blocked

# Your existing callable; async callables work too.
def save_draft(text):
    return {"saved": text}

gate = Gate(
    Policy(rules=(
        Rule("drafts", "allow", ("save_draft",)),
        Rule("no-production-delete", "hard_deny", ("delete_database",)),
    )),
    tools={"save_draft": save_draft},
)

# Inside your async agent loop, instead of calling the tool directly:
result = await gate.execute(
    Action("call-123", "save_draft", {"text": "Hello"}),
    context={"session": "session-1", "user": "user-1", "tenant": "tenant-1"},
)
```

Tools are registered by the host. An unregistered tool is always denied, including
with an allow-by-default policy. The default for registered but unmatched actions is
human review. Policy must explicitly allow ordinary work; there is no universal
"safe shell command" heuristic.

## Provider adapters

`normalize(provider, call)` accepts one **complete** tool call:

| Adapter | Input |
| --- | --- |
| `openai_responses` | Responses `function_call` output item |
| `openai_chat` | Chat Completions `tool_calls[]` entry; also compatible providers |
| `anthropic` | Messages `tool_use` content block |
| `gemini` | REST part containing `functionCall` |
| `mcp` | JSON-RPC `tools/call` request |

```python
from agentcorrect.runtime import normalize, feedback

action = normalize("openai_responses", complete_call)
try:
    result = await gate.execute(action, trusted_context)
except Blocked as blocked:
    result = blocked
output_item = feedback("openai_responses", action, result)
```

Feed the result back to the original agent so it can choose a different action.
Preserve the original model response, reasoning items, thought signatures and
provider-specific transcript requirements. These adapters normalize calls and format
results; they are not complete SDK clients or an MCP transport server. Aggregate
streaming arguments completely before normalization. Evaluate **every** call in a
multi-call response. Old Gemini calls without IDs require a stable `call_id=` supplied
by the host. MCP feedback returns a `CallToolResult`; your transport retains the
original JSON-RPC id and envelope.

## Rules and decisions

- `hard_deny`: a match blocks execution and cannot be overridden by an allow rule or human token.
- `soft_deny`: a match requires explicit human approval, unless a matched allow rule names it in `clears`.
- `allow`: permits matching calls, subject to every hard/soft rule above.
- `tools` uses exact tool names. Use `("*",)` only for an intentionally global rule.
- `equals` checks exact top-level JSON argument values; all supplied fields must match.
- `instructions` turns a rule into a semantic classifier question, within its tool/argument scope.

```python
policy = Policy((
    Rule("review-refunds", "soft_deny", ("refund",)),
    Rule("sandbox-refunds", "allow", ("refund",),
         equals={"environment": "sandbox"}, clears=("review-refunds",)),
    Rule("never-exfiltrate", "hard_deny", ("*",),
         instructions="Sends credentials or private customer data to an untrusted destination."),
))
```

Use trusted host facts to establish the actual environment and permissions. A model
claiming `environment="sandbox"` does not make it true; a tool must validate and bind
that field to its real target. Arguments, retrieved content, and tool output are
untrusted. Do not let the model construct the policy, tool registry, user identity,
or trusted authorization context.

Semantic scores at or above `threshold` (default 0.9) match; at or below
`clear_threshold` (0.1) do not match. Between them, a hard-deny rule stops the call
without an approval bypass; a soft-deny rule requires approval. An uncertain allow
rule grants no exception. Classifier failures, timeouts, missing/invalid scores, or
missing classifiers stop execution without approval bypass. These thresholds are
starting values, **not calibrated safety guarantees**.

## Choose a classifier independently of your agent model

The deterministic path makes no network calls. Any async implementation of
`Classifier.score(action, context, rules) -> {rule_id: probability}` can be used:
local models, another vendor, or your own policy service.

For a local non-generative open-weight decision model, use **Laya** (optional,
Python 3.10+). Install `laya` separately, choosing the PyTorch build appropriate for
your CPU/GPU. Load the checkpoint once before serving requests:

```python
import laya
from agentcorrect.runtime import LayaClassifier

agent = laya.load("convaiinnovations/laya-typed-decisions", device="cpu")
classifier = LayaClassifier(agent)
gate = Gate(policy, tools, classifier=classifier, timeout=10)
```

Weights download on the first load; inference runs locally with no paid API key.
This is a typed yes/no decision model, with no generated JSON to parse. The adapter
checks every answer, rejects potentially truncated policy/context and concurrent
inference, and stops execution on inference errors. A timeout stops tool execution,
but cannot cancel an already-running native inference call. Probabilities still
require evaluation and calibration on your own rules; high confidence is not proof
of correctness. Laya is not a financial authorization or idempotency system.

Run the actual model against the frozen synthetic transaction/privacy cases:

```sh
python examples/local_classifier_qa.py --out local-classifier-evidence.json
```

The runner records every expected/actual decision, tool side effect, and latency,
including unsafe allows and false blocks. It is a small smoke evaluation, not a
production safety benchmark. The question prefix is `RULE_PREFIX` in
[laya.py](agentcorrect/runtime/laya.py). No real money or financial APIs are used.

An optional Jev adapter uses OpenRouter's Decisions API:

```python
import os
from agentcorrect.runtime import JevClassifier

classifier = JevClassifier(os.environ["OPENROUTER_API_KEY"])
gate = Gate(policy, tools, classifier=classifier, timeout=10)
```

Jev receives the proposed tool name, arguments, supplied context, and applicable
semantic rules. Only provide context approved for that provider. The adapter uses
HTTPS, disables redirects, bounds the response size, validates all scores, and
uses a bounded HTTP timeout. The default model is `typesafe/jev-1.14`; override `model=`
explicitly. No provider is contacted unless you configure a classifier and a semantic
rule applies. A classifier timeout does not execute the tool; a background HTTP
request can finish later, bounded by the adapter's own timeout.

## Human review

`Blocked.request_id` is for a **trusted human interface**, never a tool exposed to the
model. The host authenticates the approver and displays the exact action/context.

```python
try:
    result = await gate.execute(action, context)
except Blocked as blocked:
    # Persist/display action + context in your authenticated approval UI.
    # Later, ONLY after a human approves this exact request:
    if blocked.request_id:
        token = gate.approve(blocked.request_id, actor=authenticated_user_id)
        result = await gate.execute(action, context, approval=token)
```

The snippet shows the host integration points; do not automatically call `approve`
from your agent loop. Tokens are bound to the policy instance, call ID, tool,
arguments and entire context; expire after five minutes by default; and are consumed
atomically before execution. Modified/replayed/expired grants fail closed. Approval
storage is in-memory and local to one `Gate`; restarts invalidate pending requests.
This library does not authenticate users or supply a review UI. Human approval is
explicit: conversation text never silently substitutes for it.

## Auditing and boundaries

Pass `audit=callback` to receive decision, execution-started, execution-failed and
execution-finished events. Events contain a fingerprint, policy fingerprint, outcome
and rule IDs, **not raw arguments, context, results, tokens, or provider errors**.
Keep rule IDs free of secrets. Persist events with a host-controlled sink. Audit
failure before execution prevents the tool call; failure after execution cannot undo
its side effects. Fingerprints are correlation hashes, not encryption.

`evaluate()` is advisory only. `execute()` performs its own evaluation and executes a
snapshot of the checked arguments, preventing mutation during classifier waits.
Cancellation cannot undo a tool already running, including a synchronous tool in a
worker thread. This does not provide exactly-once business operations or distributed
idempotency; payment/remote-write tools still need their own idempotency controls.
Keep resource permissions, credentials, filesystem isolation and tool input validation
at the tool boundary. Classifiers can miss attacks and suffer prompt injection.

## Validation

```sh
python -m unittest discover -s tests/runtime -v
python examples/runtime_gate.py
```

Runtime checks cover actual callback suppression, all adapter formats, deny
precedence, scoped exceptions, malformed classifier output, timeout, mutated inputs,
concurrent approval replay, expiry, and redacted audit records. The Jev wire contract
is tested with a fixture; that alone does not establish live classifier accuracy.

`verify.py` is an older suite that references missing `fixtures/disasters` and
`fixtures/clean` files in the source branch; it is not a passing runtime gate.

The earlier trace analyzer remains available as `agentcorrect analyze trace.jsonl`.
See [legacy trace analysis](docs/legacy-trace-analyzer.md). Its detector heuristics
are not silently promoted into runtime authorization rules.

Protocol references: [OpenRouter Armor](https://openrouter.ai/docs/guides/features/plugins/armor),
[Jev Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request),
[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling),
[Claude tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling).
