import base64
import json
import unittest

from codesentry.github_client import GitHubClient, GitHubError


class FakeResponse:
    def __init__(self, status=200, payload=None, links=None, headers=None, content=b''):
        self.status_code = status
        self._payload = payload
        self.links = links or {}
        self.headers = headers or {}
        self.text = json.dumps(payload) if payload is not None else ''
        self.content = content

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, timeout=None, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def client(responses):
    session = FakeSession(responses)
    return GitHubClient('t0k', 'octo/repo', session=session), session


class GitHubClientTests(unittest.TestCase):
    def test_validates_inputs(self):
        with self.assertRaises(GitHubError):
            GitHubClient('', 'octo/repo')
        with self.assertRaises(GitHubError):
            GitHubClient('t', 'repo-without-owner')

    def test_paginates_files(self):
        c, s = client([
            FakeResponse(payload=[{'filename': 'a.py'}],
                         links={'next': {'url': 'https://api.github.com/x?page=2'}}),
            FakeResponse(payload=[{'filename': 'b.py'}]),
        ])
        self.assertEqual([f['filename'] for f in c.list_pull_files(7)], ['a.py', 'b.py'])
        self.assertEqual(s.calls[0][1], 'https://api.github.com/repos/octo/repo/pulls/7/files')
        self.assertEqual(s.calls[0][2]['params'], {'per_page': 100})
        self.assertIsNone(s.calls[1][2]['params'])

    def test_file_content_decodes_and_handles_missing(self):
        encoded = base64.b64encode('print("hi")\n'.encode()).decode()
        c, _ = client([
            FakeResponse(payload={'type': 'file', 'encoding': 'base64', 'content': encoded}),
            FakeResponse(status=404, payload={'message': 'Not Found'}),
            FakeResponse(payload={'type': 'file', 'encoding': 'base64',
                                  'content': base64.b64encode(b'\xff\xfe\x00').decode()}),
        ])
        self.assertEqual(c.get_file_content('a.py', 'sha'), 'print("hi")\n')
        self.assertIsNone(c.get_file_content('gone.py', 'sha'))
        self.assertIsNone(c.get_file_content('bin.dat', 'sha'))

    def test_errors_raise(self):
        c, _ = client([FakeResponse(status=422, payload={'message': 'Unprocessable'})])
        with self.assertRaises(GitHubError) as ctx:
            c.create_review(1, 'sha', 'body', [])
        self.assertEqual(ctx.exception.status, 422)

    def test_retries_rate_limit(self):
        c, s = client([FakeResponse(status=429, headers={'Retry-After': '0'}), FakeResponse(payload={'id': 1})])
        self.assertEqual(c.get_pull(1), {'id': 1})
        self.assertEqual(len(s.calls), 2)

    def test_upsert_edits_existing_marker_comment(self):
        c, s = client([
            FakeResponse(payload=[{'id': 5, 'body': 'old <!-- codesentry:summary -->'}]),
            FakeResponse(payload={'id': 5}),
        ])
        c.upsert_issue_comment(3, 'new <!-- codesentry:summary -->', '<!-- codesentry:summary -->')
        self.assertEqual(s.calls[1][0], 'PATCH')
        self.assertTrue(s.calls[1][1].endswith('/issues/comments/5'))

    def test_upsert_creates_when_absent(self):
        c, s = client([FakeResponse(payload=[]), FakeResponse(payload={'id': 9})])
        c.upsert_issue_comment(3, 'body', '<!-- m -->')
        self.assertEqual(s.calls[1][0], 'POST')


if __name__ == '__main__':
    unittest.main()
