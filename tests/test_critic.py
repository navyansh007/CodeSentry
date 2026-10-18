import json
import unittest

from codesentry.critic import FindingCritic, REFUTED, UNCERTAIN, UPHELD
from codesentry.findings import Finding

LINES = [f'line_{i} = {i}' for i in range(1, 61)]


def f(line, title, source='ai', conf=0.9):
    return Finding(file='a.py', line=line, title=title, evidence=f'line_{line} = {line}',
                   confidence=conf, source=source, body='SECRET REASONING')


class CriticTests(unittest.TestCase):
    def test_drops_refuted_keeps_upheld_and_penalizes_uncertain(self):
        prompts = []

        def llm(prompt):
            prompts.append(prompt)
            return json.dumps({'verdicts': [
                {'id': 0, 'verdict': 'UPHELD', 'reason': 'yes'},
                {'id': 1, 'verdict': 'REFUTED', 'reason': 'handled on line 3'},
                {'id': 2, 'verdict': 'uncertain'},
                {'id': 7, 'verdict': 'UPHELD'},  # invented claim id: ignored
            ]})

        critic = FindingCritic({}, llm)
        kept, dropped = critic.verify([f(5, 'a'), f(10, 'b'), f(50, 'c')], {'a.py': LINES})
        self.assertEqual([k.title for k in kept], ['a', 'c'])
        self.assertEqual(kept[1].verdict, UNCERTAIN)
        self.assertAlmostEqual(kept[1].confidence, 0.75)
        self.assertEqual(dropped[0][0].verdict, REFUTED)
        self.assertEqual(len(prompts), 1)
        # The critic must not see the reviewer's reasoning
        self.assertNotIn('SECRET REASONING', prompts[0])
        # Non-adjacent windows are separated, adjacent ones merged
        self.assertIn('...', prompts[0])

    def test_fails_open_when_llm_errors(self):
        critic = FindingCritic({}, lambda p: 'Error: request timeout')
        kept, dropped = critic.verify([f(5, 'a')], {'a.py': LINES})
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])
        self.assertEqual(kept[0].verdict_reason, 'critic unavailable')

    def test_drop_uncertain_option_and_guardrail_passthrough(self):
        critic = FindingCritic({'guardrails': {'critic': {'drop_uncertain': True}}},
                               lambda p: '{"verdicts": []}')
        kept, dropped = critic.verify([f(5, 'a'), f(1, 'secret', source='guardrail:secret')], {'a.py': LINES})
        self.assertEqual([k.title for k in kept], ['secret'])
        self.assertEqual(len(dropped), 1)

    def test_disabled(self):
        critic = FindingCritic({'guardrails': {'critic': {'enabled': False}}}, lambda p: 1 / 0)
        kept, _ = critic.verify([f(5, 'a')], {'a.py': LINES})
        self.assertEqual(len(kept), 1)

    def test_batches_large_claim_sets(self):
        calls = []
        critic = FindingCritic({'guardrails': {'critic': {'max_claims_per_call': 2}}},
                               lambda p: calls.append(p) or '{"verdicts": [{"id": 0, "verdict": "UPHELD"}, {"id": 1, "verdict": "UPHELD"}]}')
        kept, _ = critic.verify([f(i, str(i)) for i in range(1, 6)], {'a.py': LINES})
        self.assertEqual(len(calls), 3)
        self.assertEqual(sum(1 for k in kept if k.verdict == UPHELD), 5)


if __name__ == '__main__':
    unittest.main()
