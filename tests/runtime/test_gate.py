import asyncio
import json
import math
import unittest
from unittest.mock import patch
from agentcorrect.runtime import Action, Blocked, Gate, Policy, Rule, normalize, feedback, JevClassifier


class Scores:
    def __init__(self, values):
        self.values = values

    async def score(self, action, context, rules):
        return self.values


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.calls = []
        self.action = Action('call-1', 'write', {'value': 'safe'})
        self.context = {'session': 's1', 'tenant': 't1', 'user': 'u1'}

    async def write(self, value):
        self.calls.append(value)
        return {'saved': value}

    def gate(self, rules=(), **kwargs):
        return Gate(Policy(tuple(rules)), {'write': self.write}, **kwargs)

    async def blocked(self, gate, action=None, **kwargs):
        with self.assertRaises(Blocked) as caught:
            await gate.execute(action or self.action, self.context, **kwargs)
        self.assertEqual(self.calls, [])
        return caught.exception

    async def test_allow_executes_and_preserves_result(self):
        gate = self.gate([Rule('ok', 'allow', ('write',))])
        self.assertEqual(await gate.execute(self.action), {'saved': 'safe'})
        self.assertEqual(self.calls, ['safe'])

    async def test_unknown_tool_never_executes(self):
        gate = Gate(Policy((), default='allow'), {'write': self.write})
        error = await self.blocked(gate, Action('2', 'shell', {}))
        self.assertEqual(error.decision.outcome, 'deny')

    async def test_default_review_and_explicit_approval_once(self):
        gate = self.gate()
        error = await self.blocked(gate)
        token = gate.approve(error.request_id, actor='human')
        await gate.execute(self.action, self.context, approval=token)
        with self.assertRaises(Blocked):
            await gate.execute(self.action, self.context, approval=token)
        self.assertEqual(self.calls, ['safe'])
        self.assertNotIn(error.request_id, json.dumps(error.tool_result()))

    async def test_approval_cannot_change_action_or_context(self):
        for changed in ('arguments', 'context', 'call_id', 'tool'):
            gate = self.gate()
            error = await self.blocked(gate)
            token = gate.approve(error.request_id, actor='human')
            action, context = self.action, dict(self.context)
            if changed == 'arguments':
                action = Action('call-1', 'write', {'value': 'unsafe'})
            if changed == 'context':
                context['tenant'] = 'other'
            if changed == 'call_id':
                action = Action('other', 'write', self.action.arguments)
            if changed == 'tool':
                action = Action('call-1', 'shell', self.action.arguments)
            with self.assertRaises(Blocked):
                await gate.execute(action, context, approval=token)
            self.assertEqual(self.calls, [])

    async def test_expired_approval(self):
        gate = self.gate()
        with patch('agentcorrect.runtime.core.time.monotonic', return_value=10):
            error = await self.blocked(gate)
            token = gate.approve(error.request_id, actor='human')
        with patch('agentcorrect.runtime.core.time.monotonic', return_value=1000):
            await self.blocked(gate, approval=token)

    async def test_token_is_gate_local(self):
        gate = self.gate()
        error = await self.blocked(gate)
        token = gate.approve(error.request_id, actor='human')
        await self.blocked(self.gate(), approval=token)

    async def test_concurrent_approval_replay_executes_once(self):
        gate = self.gate()
        error = await self.blocked(gate)
        token = gate.approve(error.request_id, actor='human')
        results = await asyncio.gather(*(gate.execute(self.action, self.context, approval=token) for _ in range(10)), return_exceptions=True)
        self.assertEqual(self.calls, ['safe'])
        self.assertEqual(sum(isinstance(r, Blocked) for r in results), 9)

    async def test_hard_deny_wins_over_allow_without_classifier(self):
        rules = [Rule('never', 'hard_deny', ('write',)), Rule('yes', 'allow', ('write',), instructions='Allow this')]
        error = await self.blocked(self.gate(rules))
        self.assertEqual(error.decision.outcome, 'deny')
        self.assertIsNone(error.request_id)

    async def test_soft_deny_needs_explicit_scoped_exception(self):
        soft = Rule('review-write', 'soft_deny', ('write',))
        generic = Rule('yes', 'allow', ('write',))
        await self.blocked(self.gate([soft, generic]))
        scoped = Rule('safe', 'allow', ('write',), equals={'value': 'safe'}, clears=('review-write',))
        await self.gate([soft, scoped]).execute(self.action)
        self.assertEqual(self.calls, ['safe'])

    async def test_semantic_scores_control_execution(self):
        rules = [Rule('danger', 'hard_deny', ('write',), instructions='Dangerous action'), Rule('ok', 'allow', ('write',))]
        for score, outcome in [(0, 'allow'), (0.1, 'allow'), (0.5, 'review'), (0.9, 'deny'), (1, 'deny')]:
            self.calls.clear()
            gate = self.gate(rules, classifier=Scores({'danger': score}))
            if outcome == 'allow':
                await gate.execute(self.action)
                self.assertEqual(self.calls, ['safe'])
            else:
                error = await self.blocked(gate)
                self.assertEqual(error.decision.outcome, outcome)
                self.assertIsNone(error.request_id)

    async def test_invalid_classifier_responses_fail_closed(self):
        rule = Rule('risk', 'hard_deny', ('write',), instructions='Check risk')
        for values in [{}, {'extra': 0}, {'risk': math.nan}, {'risk': True}, {'risk': '0'}, {'risk': -1}, {'risk': 2}, None]:
            error = await self.blocked(self.gate([rule], classifier=Scores(values)))
            self.assertEqual(error.decision.outcome, 'review')
            self.assertIsNone(error.request_id)

    async def test_missing_classifier_cannot_be_approved(self):
        rule = Rule('risk', 'hard_deny', ('write',), instructions='Check risk')
        error = await self.blocked(self.gate([rule]))
        self.assertIsNone(error.request_id)

    async def test_timeout_and_provider_exception_fail_closed(self):
        class Slow:
            async def score(self, *args):
                await asyncio.sleep(1)
        class Broken:
            async def score(self, *args):
                raise RuntimeError('secret-provider-error')
        rule = Rule('risk', 'hard_deny', ('write',), instructions='Check risk')
        for classifier in (Slow(), Broken()):
            error = await self.blocked(self.gate([rule], classifier=classifier, timeout=.01))
            self.assertNotIn('secret', str(error))
            self.assertIsNone(error.request_id)

    async def test_input_and_classifier_mutation_cannot_change_execution(self):
        action = Action('1', 'write', {'value': 'safe'})
        started, resume = asyncio.Event(), asyncio.Event()
        class Mutating:
            async def score(self, candidate, context, rules):
                started.set()
                await resume.wait()
                candidate.arguments['value'] = 'classifier-mutated'
                return {'ok': 1}
        gate = self.gate([Rule('ok', 'allow', ('write',), instructions='safe')], classifier=Mutating())
        task = asyncio.create_task(gate.execute(action))
        await started.wait()
        action.arguments['value'] = 'caller-mutated'
        resume.set()
        await task
        self.assertEqual(self.calls, ['safe'])

    async def test_audit_does_not_contain_arguments_or_context(self):
        events = []
        gate = self.gate([Rule('ok', 'allow', ('write',))], audit=events.append)
        await gate.execute(Action('secret-id', 'write', {'value': 'secret-argument'}), {'secret': 'secret-context'})
        self.assertNotIn('secret', json.dumps(events))
        self.assertEqual([r['event'] for r in events], ['decision', 'execution_started', 'execution_finished'])

    async def test_audit_failure_prevents_execution(self):
        def broken(event):
            raise OSError('disk full')
        gate = self.gate([Rule('ok', 'allow', ('write',))], audit=broken)
        with self.assertRaises(OSError):
            await gate.execute(self.action)
        self.assertEqual(self.calls, [])

    async def test_approval_audit_identifies_actor_without_raw_identity(self):
        events = []
        gate = self.gate(audit=events.append)
        error = await self.blocked(gate)
        gate.approve(error.request_id, actor='person@example.test')
        event = events[-1]
        self.assertEqual(event['event'], 'human_approved')
        self.assertEqual(len(event['actor_fingerprint']), 64)
        self.assertNotIn('person@example.test', json.dumps(events))

    async def test_policy_mutation_after_construction_has_no_effect(self):
        equals = {'value': 'safe'}
        rule = Rule('ok', 'allow', ('write',), equals=equals)
        gate = self.gate([rule])
        equals['value'] = 'unsafe'
        await gate.execute(self.action)
        self.assertEqual(self.calls, ['safe'])

    async def test_cancellation_while_classifying_never_calls_tool(self):
        started = asyncio.Event()
        class Waiting:
            async def score(self, *args):
                started.set()
                await asyncio.Event().wait()
        gate = self.gate([Rule('risk', 'hard_deny', ('write',), instructions='risk')], classifier=Waiting())
        task = asyncio.create_task(gate.execute(self.action))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.calls, [])

    async def test_sync_tool_support(self):
        gate = Gate(Policy((Rule('ok', 'allow', ('sum',)),)), {'sum': lambda a, b: a+b})
        self.assertEqual(await gate.execute(Action('1', 'sum', {'a': 2, 'b': 3})), 5)

    async def test_all_provider_formats_enforce_same_policy(self):
        calls = {
            'openai_responses': {'type': 'function_call', 'call_id': '1', 'name': 'write', 'arguments': '{"value":"unsafe"}'},
            'openai_chat': {'type': 'function', 'id': '1', 'function': {'name': 'write', 'arguments': '{"value":"unsafe"}'}},
            'anthropic': {'type': 'tool_use', 'id': '1', 'name': 'write', 'input': {'value': 'unsafe'}},
            'gemini': {'functionCall': {'id': '1', 'name': 'write', 'args': {'value': 'unsafe'}}},
            'mcp': {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'write', 'arguments': {'value': 'unsafe'}}},
        }
        for provider, call in calls.items():
            gate = self.gate([Rule('never', 'hard_deny', ('write',), equals={'value': 'unsafe'})])
            action = normalize(provider, call)
            error = await self.blocked(gate, action)
            self.assertIn('hard-deny', json.dumps(feedback(provider, action, error)))

    def test_malformed_arguments_and_partial_streams_rejected(self):
        for args in ['{', '[]', 'null', '{"x":NaN}', '{"x":1,"x":2}']:
            with self.assertRaises(ValueError):
                normalize('openai_responses', {'type': 'function_call', 'call_id': '1', 'name': 'write', 'arguments': args})
        with self.assertRaises(ValueError):
            normalize('openai_responses', {'type': 'function_call', 'status': 'in_progress', 'call_id': '1', 'name': 'write', 'arguments': '{}'})

    def test_invalid_policy_fails_at_construction(self):
        with self.assertRaises(ValueError):
            Policy((Rule('x', 'hard_deny', ('*',)), Rule('y', 'allow', ('*',), clears=('x',))))
        with self.assertRaises(ValueError):
            Rule('bad', 'allow', ())

    async def test_jev_wire_contract(self):
        rule = Rule('risk', 'hard_deny', ('write',), instructions='Delete production data')
        classifier = JevClassifier('test-only-key')
        with patch.object(classifier, '_request', return_value={'answers': {'risk': {'type': 'noul', 'noul': .95}}}) as request:
            scores = await classifier.score(self.action, self.context, [rule])
        self.assertEqual(scores, {'risk': .95})
        payload = request.call_args.args[0]
        self.assertEqual(payload['questions']['risk']['type'], 'noul')
        self.assertEqual(payload['state']['host_context'], self.context)
        self.assertNotIn('test-only-key', json.dumps(payload))
        with patch.object(classifier, '_request', return_value={'answers': {}}):
            with self.assertRaises(ValueError):
                await classifier.score(self.action, self.context, [rule])


if __name__ == '__main__':
    unittest.main()
