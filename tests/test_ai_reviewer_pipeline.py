import json
import re
import os
import tempfile
import unittest

from codesentry.ai_reviewer import AIReviewer

FAKE_GH = 'ghp_' + 'Q7w8E9r0' * 5

RISKY = f'''import sqlite3

TOKEN = "{FAKE_GH}"


def get_user(conn, user_id):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE id = {{user_id}}")
    return cur.fetchone()
'''

CLEAN = '''def add(a, b):
    """Return the sum."""
    return a + b


def sub(a, b):
    """Return the difference."""
    return a - b
'''


class FakeRAG:
    def get_diverse_samples(self, n_samples=8):
        return []

    def retrieve_file_context(self, path):
        return []


class FakeProvider:
    def __init__(self):
        self.prompts = []

    def is_configured(self):
        return True

    def missing_key_message(self):
        return ''

    def chat(self, prompt, system_prompt):
        self.prompts.append(prompt)
        if 'triaging files' in prompt:
            return '{"verdict": "LGTM", "confidence": 0.95, "reason": "trivial arithmetic"}'
        if 'skeptical senior engineer' in prompt:
            verdicts = []
            for match in re.finditer(r'^\[(\d+)\] line \d+: (.+)$', prompt, re.MULTILINE):
                refuted = 'Cursor' in match.group(2)
                verdicts.append({'id': int(match.group(1)),
                                 'verdict': 'REFUTED' if refuted else 'UPHELD', 'reason': 'mock'})
            return json.dumps({'verdicts': verdicts})
        if 'Review the following code file' in prompt:
            return '```json\n' + json.dumps({'verdict': 'NEEDS_CHANGES', 'findings': [
                {'line': 8, 'title': 'SQL injection through f-string query', 'severity': 'critical',
                 'category': 'security', 'confidence': 0.95,
                 'evidence': 'cur.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                 'suggestion': 'cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))'},
                {'line': 7, 'title': 'Cursor is never closed', 'severity': 'minor',
                 'category': 'bug', 'confidence': 0.7, 'evidence': 'cur = conn.cursor()'},
                {'line': 3, 'title': 'Calls eval on input', 'severity': 'major',
                 'category': 'security', 'confidence': 0.9, 'evidence': 'eval(data)'},
                {'line': 1, 'title': 'Import order', 'severity': 'nit', 'category': 'style',
                 'confidence': 0.9, 'evidence': 'import sqlite3'},
            ]}) + '\n```'
        return 'General text'


class PipelineTests(unittest.TestCase):
    def test_end_to_end_with_fake_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            risky = os.path.join(tmp, 'db.py')
            clean = os.path.join(tmp, 'math_utils.py')
            open(risky, 'w').write(RISKY)
            open(clean, 'w').write(CLEAN)

            reviewer = AIReviewer({'llm': {'provider': 'x', 'providers': {}}}, FakeRAG())
            provider = FakeProvider()
            reviewer.provider = provider
            reviews = reviewer._review_files([risky, clean], {'issues': []})

            triage = {os.path.basename(t['file']): t for t in reviewer.review_results['triage']}
            self.assertEqual(triage['math_utils.py']['action'], 'skip')
            self.assertEqual(triage['db.py']['action'], 'review')

            titles = [f['title'] for f in reviewer.review_results['findings']]
            self.assertIn('SQL injection through f-string query', titles)
            self.assertTrue(any('Hardcoded secret' in t for t in titles))
            self.assertNotIn('Calls eval on input', titles)   # ungrounded
            self.assertNotIn('Import order', titles)          # nitpick
            self.assertNotIn('Cursor is never closed', titles)  # refuted by critic

            stats = reviewer.review_results['guardrail_stats']
            self.assertEqual(stats['dropped_by_reason'].get('ungrounded_evidence'), 1)
            self.assertEqual(stats['dropped_by_reason'].get('refuted_by_critic'), 1)

            # The secret never reaches the provider
            self.assertFalse(any(FAKE_GH in p for p in provider.prompts))
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]['verdict'], 'NEEDS_CHANGES')

    def test_budget_is_enforced(self):
        reviewer = AIReviewer({'llm': {'provider': 'x', 'providers': {}},
                               'guardrails': {'budget': {'max_llm_calls': 1}}}, FakeRAG())
        reviewer.provider = FakeProvider()
        self.assertEqual(reviewer._call_llm('hi'), 'General text')
        self.assertTrue(reviewer._call_llm('hi').startswith('Error: LLM call budget exhausted'))


if __name__ == '__main__':
    unittest.main()
