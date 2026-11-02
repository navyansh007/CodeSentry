import unittest

from codesentry.guardrails import detect_security_regressions


class SecurityRegressionTests(unittest.TestCase):
    def test_removed_control_without_replacement(self):
        removed = ['    if not hmac.compare_digest(sig, expected):', '        raise Forbidden()']
        added = ['    # signature check simplified']
        kinds = [s['type'] for s in detect_security_regressions(removed, added)]
        self.assertEqual(kinds, ['security_control_removed'])

    def test_refactor_that_keeps_the_control_is_fine(self):
        removed = ['    value = sanitize(raw)']
        added = ['    value = sanitize(raw.strip())']
        self.assertEqual(detect_security_regressions(removed, added), [])

    def test_dangerous_additions(self):
        added = [
            'requests.get(url, verify=False)',
            'subprocess.run(cmd, shell=True)',
            'data = pickle.loads(blob)',
            'cfg = yaml.load(fh)',
            'el.innerHTML = userInput',
            'x = 1  # nosec',
        ]
        kinds = [s['type'] for s in detect_security_regressions([], added)]
        self.assertEqual(kinds, ['tls_verification_disabled', 'shell_injection_risk',
                                 'unsafe_deserialization', 'unsafe_deserialization',
                                 'xss_sink', 'security_check_suppressed'])

    def test_safe_variants_and_comments_are_ignored(self):
        added = ['cfg = yaml.load(fh, Loader=yaml.SafeLoader)', '# never use verify=False here']
        self.assertEqual(detect_security_regressions(['# validate input later'], added), [])


if __name__ == '__main__':
    unittest.main()
