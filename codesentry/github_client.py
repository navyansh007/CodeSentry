"""
GitHub Client - Minimal REST wrapper for reviewing pull requests

Uses plain `requests` (no PyGithub dependency) and works against
github.com or GitHub Enterprise Server via `api_url`. Only the endpoints
CodeSentry needs are wrapped: reading a PR and its files, reading existing
comments (so re-runs don't repeat themselves), and posting a review.
"""

import base64
import time
from typing import Any, Dict, List, Optional

import requests

DEFAULT_API_URL = 'https://api.github.com'


class GitHubError(Exception):
    """Raised when the GitHub API returns an error"""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class GitHubClient:
    """Thin client for the pull request endpoints CodeSentry uses"""

    def __init__(self, token: str, repo: str, api_url: str = DEFAULT_API_URL,
                 timeout: int = 30, session: Optional[requests.Session] = None):
        if not token:
            raise GitHubError('A GitHub token is required (set GITHUB_TOKEN)')
        if not repo or '/' not in repo:
            raise GitHubError(f"Repository must be in 'owner/name' form, got '{repo}'")
        self.repo = repo
        self.api_url = (api_url or DEFAULT_API_URL).rstrip('/')
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'codesentry-pr-review',
        })

    # ------------------------------------------------------------------
    # Low-level
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, retries: int = 2, **kwargs) -> requests.Response:
        url = path if path.startswith('http') else f'{self.api_url}{path}'
        for attempt in range(retries + 1):
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            # Retry secondary rate limits and transient server errors
            if response.status_code in (429, 502, 503, 504) or (
                response.status_code == 403 and 'rate limit' in response.text.lower()
            ):
                if attempt < retries:
                    wait = int(response.headers.get('Retry-After', 2 ** (attempt + 1)))
                    time.sleep(min(wait, 30))
                    continue
            if response.status_code >= 400:
                raise GitHubError(
                    f'{method} {path} failed with {response.status_code}: {response.text[:300]}',
                    response.status_code,
                )
            return response
        return response  # pragma: no cover

    def _paginate(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        params = {'per_page': 100, **(params or {})}
        url: Optional[str] = path
        while url:
            response = self._request('GET', url, params=params)
            items.extend(response.json())
            url = response.links.get('next', {}).get('url')
            params = None  # the "next" link already carries the query string
        return items

    # ------------------------------------------------------------------
    # Pull requests
    # ------------------------------------------------------------------

    def get_pull(self, number: int) -> Dict[str, Any]:
        return self._request('GET', f'/repos/{self.repo}/pulls/{number}').json()

    def list_pull_files(self, number: int) -> List[Dict[str, Any]]:
        return self._paginate(f'/repos/{self.repo}/pulls/{number}/files')

    def get_file_content(self, path: str, ref: str) -> Optional[str]:
        """Return a file's text at `ref`, or None if it is missing or binary"""
        try:
            data = self._request('GET', f'/repos/{self.repo}/contents/{path}', params={'ref': ref}).json()
        except GitHubError as e:
            if e.status == 404:
                return None
            raise
        if isinstance(data, list) or data.get('type') != 'file':
            return None
        if data.get('encoding') == 'base64' and data.get('content') is not None:
            raw = base64.b64decode(data['content'])
        elif data.get('download_url'):
            raw = self._request('GET', data['download_url']).content
        else:
            return None
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return None

    def list_review_comments(self, number: int) -> List[Dict[str, Any]]:
        return self._paginate(f'/repos/{self.repo}/pulls/{number}/comments')

    def list_issue_comments(self, number: int) -> List[Dict[str, Any]]:
        return self._paginate(f'/repos/{self.repo}/issues/{number}/comments')

    def create_review(self, number: int, commit_id: str, body: str,
                      comments: List[Dict[str, Any]], event: str = 'COMMENT') -> Dict[str, Any]:
        payload = {'commit_id': commit_id, 'body': body, 'event': event, 'comments': comments}
        return self._request('POST', f'/repos/{self.repo}/pulls/{number}/reviews', json=payload).json()

    def upsert_issue_comment(self, number: int, body: str, marker: str) -> Dict[str, Any]:
        """Edit the comment containing `marker` if one exists, otherwise create it"""
        for comment in self.list_issue_comments(number):
            if marker in (comment.get('body') or ''):
                return self._request(
                    'PATCH', f"/repos/{self.repo}/issues/comments/{comment['id']}", json={'body': body}
                ).json()
        return self._request('POST', f'/repos/{self.repo}/issues/{number}/comments', json={'body': body}).json()
