import unittest

from codesentry.findings import Finding, extract_json, parse_findings


class ExtractJsonTests(unittest.TestCase):
    def test_fenced_block(self):
        text = 'Here you go:\n```json\n{"findings": []}\n```\nThanks'
        self.assertEqual(extract_json(text), {'findings': []})

    def test_leading_prose(self):
        self.assertEqual(extract_json('Sure! {"a": 1} hope it helps'), {'a': 1})

    def test_strips_reasoning_block(self):
        text = '<think>maybe {"verdict": "wrong"}? let me check</think>\n{"verdict": "LGTM", "findings": []}'
        self.assertEqual(extract_json(text), {'verdict': 'LGTM', 'findings': []})

    def test_garbage(self):
        self.assertIsNone(extract_json('no json here'))
        self.assertIsNone(extract_json(''))


class ParseFindingsTests(unittest.TestCase):
    def test_normalizes_fields(self):
        response = '''{"verdict": "NEEDS_CHANGES", "findings": [
            {"line": "12", "title": "SQL built with f-string", "severity": "HIGH",
             "category": "Security Vulnerability", "confidence": 85,
             "evidence": "cur.execute(f\\"SELECT {x}\\")"}]}'''
        findings = parse_findings(response, 'app.py')
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.file, 'app.py')
        self.assertEqual(f.line, 12)
        self.assertEqual(f.severity, 'major')
        self.assertEqual(f.category, 'security')
        self.assertAlmostEqual(f.confidence, 0.85)

    def test_lgtm_is_empty_list_not_none(self):
        self.assertEqual(parse_findings('{"verdict": "LGTM", "findings": []}', 'a.py'), [])

    def test_unparseable_is_none(self):
        self.assertIsNone(parse_findings('Looks fine to me!', 'a.py'))

    def test_skips_findings_without_title(self):
        self.assertEqual(parse_findings('[{"line": 3}]', 'a.py'), [])

    def test_deterministic_sources(self):
        self.assertTrue(Finding(file='a', line=1, title='t', source='static:bandit').is_deterministic)
        self.assertTrue(Finding(file='a', line=1, title='t', source='guardrail:secret').is_deterministic)
        self.assertFalse(Finding(file='a', line=1, title='t', source='heuristic:security').is_deterministic)
        self.assertFalse(Finding(file='a', line=1, title='t').is_deterministic)

    def test_fingerprint_ignores_line_drift(self):
        a = Finding(file='a.py', line=3, title='Unused variable x', category='style')
        b = Finding(file='a.py', line=9, title='unused variable  X!', category='style')
        self.assertEqual(a.fingerprint, b.fingerprint)


if __name__ == '__main__':
    unittest.main()
