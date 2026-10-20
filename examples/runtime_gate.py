"""Real temporary-file side effects through the guard; no model key needed.

Run: python examples/runtime_gate.py
"""
import asyncio
import json
import tempfile
from pathlib import Path
from agentcorrect.runtime import Gate, Policy, Rule, Blocked, normalize, feedback


async def main():
    with tempfile.TemporaryDirectory(prefix='agentcorrect-demo-') as directory:
        root = Path(directory)

        def write_file(name, text):
            # Tool itself enforces its resource boundary independently of policy.
            if name not in ('draft.txt', 'review.txt', 'protected.txt'):
                raise ValueError('Unknown demo file')
            (root / name).write_text(text)
            return {'saved': name}

        gate = Gate(Policy((
            Rule('protected-file', 'hard_deny', ('write_file',), equals={'name': 'protected.txt'}),
            Rule('review-file', 'soft_deny', ('write_file',), equals={'name': 'review.txt'}),
            Rule('draft-file', 'allow', ('write_file',), equals={'name': 'draft.txt'}),
        )), {'write_file': write_file})
        context = {'session': 'demo', 'user': 'demo-human', 'workspace': directory}
        report = []
        for name in ('draft.txt', 'protected.txt', 'review.txt'):
            call = {'type': 'function_call', 'call_id': name, 'name': 'write_file',
                    'arguments': json.dumps({'name': name, 'text': 'Written through AgentCorrect'})}
            action = normalize('openai_responses', call)
            try:
                result = await gate.execute(action, context)
                report.append({'file': name, 'decision': 'allow', 'exists': (root / name).exists()})
            except Blocked as error:
                assert not (root / name).exists()
                report.append({'file': name, 'decision': error.decision.outcome, 'exists_before_approval': False})
                # In a real app this is a separate authenticated human UI handler.
                if error.request_id:
                    token = gate.approve(error.request_id, actor='demo-human')
                    result = await gate.execute(action, context, approval=token)
                    assert (root / name).read_text() == 'Written through AgentCorrect'
                    report.append({'file': name, 'decision': 'human_approved', 'readback': True})
                    try:
                        await gate.execute(action, context, approval=token)
                        raise AssertionError('Replay succeeded')
                    except Blocked:
                        report.append({'approval_replay': 'blocked'})
                else:
                    result = error
            print(json.dumps(feedback('openai_responses', action, result)))
        assert not (root / 'protected.txt').exists()
        assert (root / 'draft.txt').read_text() == 'Written through AgentCorrect'
        print(json.dumps({'side_effect_proof': report}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
