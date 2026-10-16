import unittest
from agentcorrect.runtime import Action, Rule, LayaClassifier


class Tokenizer:
    mask_token = '[MASK]'
    def encode(self, value, **kwargs):
        return value.split()


class Agent:
    tok = Tokenizer()
    cfg = {'max_len': 1024, 'head_max_len': 256}
    def __init__(self):
        self.calls = 0
        self.answer = {'answers': {'risk': {'type':'noul','noul':.95}}}
    def predict(self, state, questions):
        self.calls += 1
        return self.answer


class LayaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.agent = Agent()
        self.classifier = LayaClassifier(self.agent)
        self.action = Action('1','transfer',{'amount':100})
        self.rules = [Rule('risk','hard_deny',('transfer',),instructions='Unauthorized transfer')]

    async def test_typed_probability(self):
        self.assertEqual(await self.classifier.score(self.action,{},self.rules),{'risk':.95})
        self.assertEqual(self.agent.calls,1)

    async def test_bad_outputs(self):
        for answer in [{}, {'answers':{}}, {'answers':{'risk':{'type':'choice','noul':.1}}},
                       {'answers':{'risk':{'type':'noul','noul':float('nan')}}},
                       {'answers':{'risk':{'type':'noul','noul':.1,'abstention':True}}}]:
            self.agent.answer=answer
            with self.assertRaises((ValueError,AttributeError)):
                await self.classifier.score(self.action,{},self.rules)

    async def test_rejects_truncation_and_reserved_marker(self):
        for context in [{'data':'word '*1100}, {'data':'[MASK]'}]:
            with self.assertRaises(ValueError):
                await self.classifier.score(self.action,context,self.rules)
        self.assertEqual(self.agent.calls,0)

    async def test_rejects_long_question(self):
        with self.assertRaises(ValueError):
            await self.classifier.score(self.action,{},[Rule('risk','hard_deny',('transfer',),instructions='word '*300)])
        self.assertEqual(self.agent.calls,0)

    async def test_busy_fails_closed(self):
        self.classifier._lock.acquire()
        try:
            with self.assertRaises(ValueError):
                await self.classifier.score(self.action,{},self.rules)
        finally:
            self.classifier._lock.release()
        self.assertEqual(self.agent.calls,0)
