"""Provider-independent tool execution boundary. No model SDK dependencies."""
import asyncio
import copy
import hashlib
import inspect
import json
import math
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Tuple


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def probability(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Expected a finite probability between zero and one')
    return float(value)


@dataclass(frozen=True)
class Action:
    id: str
    tool: str
    arguments: Dict[str, Any]

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or not isinstance(self.tool, str) or not self.tool:
            raise ValueError('Action id and tool must be nonempty strings')
        if not isinstance(self.arguments, dict):
            raise ValueError('Tool arguments must be a JSON object')
        canonical(self.arguments)


@dataclass(frozen=True)
class Rule:
    id: str
    effect: str  # hard_deny, soft_deny, allow
    tools: Tuple[str, ...]  # exact registered tool names; ('*',) explicitly means all
    instructions: str = ''  # nonempty means classifier evaluates this rule
    equals: Mapping[str, Any] = field(default_factory=dict)  # top-level argument equality
    clears: Tuple[str, ...] = ()  # allow exceptions explicitly name soft-deny rules
    threshold: float = 0.9
    clear_threshold: float = 0.1

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or self.effect not in ('hard_deny', 'soft_deny', 'allow'):
            raise ValueError('Invalid rule id or effect')
        if not isinstance(self.tools, (tuple, list)) or not self.tools or any(not isinstance(t, str) or not t for t in self.tools):
            raise ValueError('Rules must explicitly scope their tool names')
        if not isinstance(self.instructions, str) or not isinstance(self.equals, Mapping):
            raise ValueError('Invalid rule condition')
        canonical(dict(self.equals))
        if not 0 <= probability(self.clear_threshold) < probability(self.threshold) <= 1:
            raise ValueError('Invalid rule thresholds')
        if not isinstance(self.clears, (tuple, list)) or any(not isinstance(t, str) or not t for t in self.clears):
            raise ValueError('clears must be a sequence of rule ids')
        if self.clears and self.effect != 'allow':
            raise ValueError('Only allow rules can clear soft denials')

    def applies(self, action: Action) -> bool:
        return ('*' in self.tools or action.tool in self.tools) and all(
            key in action.arguments and canonical(action.arguments[key]) == canonical(value)
            for key, value in self.equals.items()
        )


@dataclass(frozen=True)
class Policy:
    rules: Tuple[Rule, ...]
    default: str = 'review'

    def __post_init__(self):
        if self.default not in ('allow', 'review', 'deny'):
            raise ValueError('Invalid default decision')
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError('Rule ids must be unique')
        soft = {r.id for r in self.rules if r.effect == 'soft_deny'}
        if any(set(r.clears) - soft for r in self.rules):
            raise ValueError('Exceptions may only reference existing soft-deny rules')


class Classifier(Protocol):
    async def score(self, action: Action, context: Dict[str, Any], rules: Sequence[Rule]) -> Mapping[str, float]:
        """Return a match probability for every supplied rule id; no decisions/execution."""
        ...


@dataclass(frozen=True)
class Decision:
    outcome: str
    reason: str
    rules: Tuple[str, ...] = ()
    approvable: bool = False


class Blocked(Exception):
    def __init__(self, decision: Decision, request_id: Optional[str] = None):
        self.decision = decision
        self.request_id = request_id
        super().__init__(decision.reason)

    def tool_result(self) -> dict:
        # Approval handles are deliberately not exposed to the model.
        return {'executed': False, 'outcome': self.decision.outcome,
                'reason': self.decision.reason, 'rules': list(self.decision.rules)}


class Gate:
    """Trusted host owns this object, tools, policy, context, and approval UI.

    execute() is the enforcement API. evaluate() is advisory and never executes.
    Keep approve() and approval tokens out of the model's tool registry.
    """
    def __init__(self, policy: Policy, tools: Mapping[str, Callable], *,
                 classifier: Optional[Classifier] = None, timeout: float = 10,
                 approval_ttl: float = 300, audit: Optional[Callable[[dict], None]] = None):
        if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(approval_ttl) or approval_ttl <= 0:
            raise ValueError('Timeouts must be positive and finite')
        if any(not callable(tool) for tool in tools.values()):
            raise ValueError('Every registered tool must be callable')
        self._policy = copy.deepcopy(policy)
        self._tools = dict(tools)
        self._classifier = classifier
        self._timeout = timeout
        self._ttl = approval_ttl
        self._audit = audit
        self._pending = {}
        self._approved = {}
        self._lock = threading.Lock()
        self._policy_id = hashlib.sha256(repr(self._policy).encode()).hexdigest()

    def _snapshot(self, action, context):
        # JSON roundtrip detaches everything from caller mutations during awaits.
        if not isinstance(context, dict):
            raise ValueError('Context must be a host-supplied JSON object')
        return Action(action.id, action.tool, json.loads(canonical(action.arguments))), json.loads(canonical(context))

    def _fingerprint(self, action, context):
        return hashlib.sha256(canonical([self._policy_id, action.id, action.tool, action.arguments, context]).encode()).hexdigest()

    def _record(self, event, action, context, decision=None):
        if self._audit:
            self._audit({'event': event, 'fingerprint': self._fingerprint(action, context),
                         'policy': self._policy_id, 'outcome': decision.outcome if decision else None,
                         'rules': list(decision.rules) if decision else []})

    async def evaluate(self, action: Action, context: Optional[dict] = None) -> Decision:
        action, context = self._snapshot(action, {} if context is None else context)
        return await self._evaluate(action, context)

    async def _evaluate(self, action, context):
        if action.tool not in self._tools:
            return Decision('deny', 'Tool is not registered')
        applicable = [r for r in self._policy.rules if r.applies(action)]
        scores = {r.id: 1.0 for r in applicable if not r.instructions}
        # Known hard denials do not depend on a classifier's availability.
        hard = tuple(r.id for r in applicable if r.effect == 'hard_deny' and scores.get(r.id) == 1)
        if hard:
            return Decision('deny', 'Action violates a hard-deny rule', hard)
        semantic = [r for r in applicable if r.instructions]
        if semantic:
            if self._classifier is None:
                return Decision('review', 'Policy requires an unavailable classifier')
            try:
                result = await asyncio.wait_for(self._classifier.score(
                    copy.deepcopy(action), copy.deepcopy(context), copy.deepcopy(semantic)), self._timeout)
                if not isinstance(result, Mapping) or set(result) != {r.id for r in semantic}:
                    raise ValueError('Incomplete classifier result')
                scores.update({key: probability(value) for key, value in result.items()})
            except Exception:
                # Never surface provider errors, arguments, or secrets in model feedback.
                return Decision('review', 'Classifier failed, timed out, or returned invalid scores')
        matched = [r for r in applicable if scores[r.id] >= r.threshold]
        uncertain = [r for r in applicable if r.clear_threshold < scores[r.id] < r.threshold]
        hard = tuple(r.id for r in matched if r.effect == 'hard_deny')
        if hard:
            return Decision('deny', 'Action violates a hard-deny rule', hard)
        if any(r.effect == 'hard_deny' for r in uncertain):
            return Decision('review', 'A hard-deny rule is uncertain', tuple(r.id for r in uncertain))
        cleared = {rule_id for r in matched if r.effect == 'allow' for rule_id in r.clears}
        soft = tuple(r.id for r in matched + uncertain if r.effect == 'soft_deny' and r.id not in cleared)
        if soft:
            return Decision('review', 'Action needs explicit human approval', soft, True)
        if any(r.effect == 'allow' for r in matched):
            return Decision('allow', 'Action matches an allow rule', tuple(r.id for r in matched))
        return Decision(self._policy.default, 'Policy default', approvable=self._policy.default == 'review')

    def _prune(self):
        now = time.monotonic()
        for store in (self._pending, self._approved):
            for key in list(store):
                if store[key][1] <= now:
                    del store[key]

    def approve(self, request_id: str, *, actor: str) -> str:
        """Trusted human-approval handler only. Return a short-lived one-use token."""
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError('Approval requires a human identity')
        with self._lock:
            self._prune()
            pending = self._pending.get(request_id)
            if pending is None:
                raise ValueError('Unknown, expired, or consumed approval request')
            if self._audit:
                self._audit({'event': 'human_approved', 'fingerprint': pending[0],
                             'policy': self._policy_id,
                             'actor_fingerprint': hashlib.sha256(actor.encode()).hexdigest()})
            del self._pending[request_id]
            token = secrets.token_urlsafe(32)
            self._approved[token] = pending
            return token

    async def execute(self, action: Action, context: Optional[dict] = None, *, approval: Optional[str] = None):
        action, context = self._snapshot(action, {} if context is None else context)
        fingerprint = self._fingerprint(action, context)
        if approval is not None:
            with self._lock:
                self._prune()
                grant = self._approved.pop(approval, None)
            if grant is None or grant[0] != fingerprint:
                raise Blocked(Decision('deny', 'Approval is expired, consumed, or bound to another action/context'))
            decision = Decision('allow', 'Explicit human approval')
        else:
            decision = await self._evaluate(action, context)
        self._record('decision', action, context, decision)
        if decision.outcome != 'allow':
            request_id = None
            if decision.approvable:
                with self._lock:
                    self._prune()
                    if len(self._pending) + len(self._approved) >= 10000:
                        raise Blocked(Decision('review', 'Approval queue is full'))
                    request_id = secrets.token_urlsafe(32)
                    self._pending[request_id] = (fingerprint, time.monotonic() + self._ttl)
            raise Blocked(decision, request_id)
        # Audit must succeed before side effects; callback receives no raw args/context.
        self._record('execution_started', action, context, decision)
        tool = self._tools[action.tool]
        arguments = copy.deepcopy(action.arguments)
        try:
            if inspect.iscoroutinefunction(tool):
                result = await tool(**arguments)
            else:
                result = await asyncio.get_running_loop().run_in_executor(None, lambda: tool(**arguments))
                if inspect.isawaitable(result):
                    result = await result
        except BaseException:
            self._record('execution_failed', action, context, decision)
            raise
        self._record('execution_finished', action, context, decision)
        return result
