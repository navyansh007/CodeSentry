import unittest

from codesentry.findings import Finding
from codesentry.guardrails import (
    DROP_DUP_STATIC, DROP_DUPLICATE, DROP_LOW_CONFIDENCE, DROP_MISSING_EVIDENCE,
    DROP_NITPICK, DROP_NO_OP, DROP_OUTSIDE_DIFF, DROP_OVER_CAP, DROP_UNGROUNDED,
    OutputGuardrails, locate_evidence,
)

SOURCE = [
    'import sqlite3',
    '',
    'def get_user(conn, user_id):',
    '    cur = conn.cursor()',
    '    cur.execute(f"SELECT * FROM users WHERE id = {user_id}")',
    '    return cur.fetchone()',
    '',
    'def unused():',
    '    x = 1',
    '    return 2',
]
FILES = {'app.py': SOURCE}


def make(**kw):
    base = dict(file='app.py', line=5, title='SQL injection via f-string query',
                severity='major', category='security', confidence=0.9,
                evidence='cur.execute(f"SELECT * FROM users WHERE id = {user_id}")')
    base.update(kw)
    return Finding(**base)


def reasons(report):
    return [r for _, r in report.dropped]


class LocateEvidenceTests(unittest.TestCase):
    def test_strips_line_number_and_diff_prefixes(self):
        self.assertEqual(locate_evidence('5: cur = conn.cursor()', SOURCE, 1), 4)
        self.assertEqual(locate_evidence('+    return cur.fetchone()', SOURCE, 1), 6)

    def test_missing(self):
        self.assertEqual(locate_evidence('eval(user_input)', SOURCE, 1), 0)


class OutputGuardrailsTests(unittest.TestCase):
    def setUp(self):
        self.guard = OutputGuardrails({})

    def test_keeps_grounded_high_confidence_finding(self):
        report = self.guard.apply([make()], FILES)
        self.assertEqual(len(report.kept), 1)
        self.assertEqual(report.dropped, [])

    def test_drops_hallucinated_evidence(self):
        report = self.guard.apply([make(evidence='os.system(cmd)')], FILES)
        self.assertEqual(reasons(report), [DROP_UNGROUNDED])

    def test_fixes_line_drift(self):
        report = self.guard.apply([make(line=9)], FILES)
        self.assertEqual(report.kept[0].line, 5)
        self.assertEqual(report.kept[0].meta['relocated_from'], 9)

    def test_missing_evidence(self):
        self.assertEqual(reasons(self.guard.apply([make(evidence='')], FILES)), [DROP_MISSING_EVIDENCE])

    def test_low_confidence(self):
        self.assertEqual(reasons(self.guard.apply([make(confidence=0.3)], FILES)), [DROP_LOW_CONFIDENCE])

    def test_nitpicks(self):
        f = make(severity='nit', category='style', title='Rename variable', evidence='x = 1', line=9)
        self.assertEqual(reasons(self.guard.apply([f], FILES)), [DROP_NITPICK])

    def test_no_op_suggestion(self):
        f = make(suggestion='cur.execute(f"SELECT * FROM users WHERE id = {user_id}")')
        self.assertEqual(reasons(self.guard.apply([f], FILES)), [DROP_NO_OP])

    def test_duplicate_of_static(self):
        static = [{'file': 'app.py', 'line': 9, 'message': "Unused variable 'x'", 'code': 'unused-variable'}]
        f = make(line=9, title="Unused variable 'x'", category='maintainability', evidence='x = 1')
        self.assertEqual(reasons(self.guard.apply([f], FILES, static)), [DROP_DUP_STATIC])

    def test_duplicates_collapse_to_highest_priority(self):
        report = self.guard.apply([make(confidence=0.7), make(confidence=0.95)], FILES)
        self.assertEqual(len(report.kept), 1)
        self.assertEqual(report.kept[0].confidence, 0.95)
        self.assertEqual(reasons(report), [DROP_DUPLICATE])

    def test_overlapping_ranges_are_duplicates(self):
        wide = make(line=4, end_line=5, title='Query built unsafely', confidence=0.7,
                    evidence='cur = conn.cursor()')
        narrow = make(title='SQL injection via f-string query')  # line 5, same category
        report = self.guard.apply([wide, narrow], FILES)
        self.assertEqual([f.title for f in report.kept], ['SQL injection via f-string query'])
        other = make(line=4, title='Cursor never closed', category='bug', evidence='cur = conn.cursor()')
        self.assertEqual(len(self.guard.apply([other, make()], FILES).kept), 2)

    def test_outside_diff(self):
        report = self.guard.apply([make()], FILES, allowed_lines={'app.py': {9, 10}})
        self.assertEqual(reasons(report), [DROP_OUTSIDE_DIFF])

    def test_caps(self):
        guard = OutputGuardrails({'guardrails': {'output': {'max_findings_per_file': 1}}})
        a = make()
        b = make(line=4, title='Cursor never closed', category='bug', evidence='cur = conn.cursor()', confidence=0.7)
        report = guard.apply([a, b], FILES)
        self.assertEqual([f.title for f in report.kept], [a.title])
        self.assertEqual(reasons(report), [DROP_OVER_CAP])

    def test_guardrail_findings_bypass_confidence_and_evidence(self):
        f = Finding(file='app.py', line=1, title='Hardcoded secret', confidence=0.1, source='guardrail:secret')
        self.assertEqual(len(self.guard.apply([f], FILES).kept), 1)


if __name__ == '__main__':
    unittest.main()
