import os
import unittest
from unittest import mock

from codesentry.llm_providers import create_provider

CFG = {'llm': {'provider': 'groq', 'model': 'm', 'providers': {
    'groq': {'type': 'openai_compatible', 'api_url': 'https://x', 'api_key_env': 'GROQ_API_KEY'},
    'ollama': {'type': 'openai_compatible', 'api_url': 'http://localhost', 'api_key_env': None},
}}}


class ProviderKeyTests(unittest.TestCase):
    def test_specific_env_wins_over_fallback(self):
        with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'specific', 'CODESENTRY_LLM_API_KEY': 'generic'}):
            self.assertEqual(create_provider(CFG).api_key, 'specific')

    def test_generic_fallback(self):
        env = {k: v for k, v in os.environ.items() if k != 'GROQ_API_KEY'}
        env['CODESENTRY_LLM_API_KEY'] = 'generic'
        with mock.patch.dict(os.environ, env, clear=True):
            provider = create_provider(CFG)
            self.assertEqual(provider.api_key, 'generic')
            self.assertTrue(provider.is_configured())

    def test_keyless_provider_ignores_fallback(self):
        cfg = {'llm': {**CFG['llm'], 'provider': 'ollama'}}
        with mock.patch.dict(os.environ, {'CODESENTRY_LLM_API_KEY': 'generic'}):
            provider = create_provider(cfg)
            self.assertIsNone(provider.api_key)
            self.assertTrue(provider.is_configured())


class FakeResp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload, headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


class ProviderRetryTests(unittest.TestCase):
    def test_retries_rate_limit_then_succeeds(self):
        ok = FakeResp(200, {'choices': [{'message': {'content': 'hi'}}]})
        calls = [FakeResp(429, {'error': 'slow down'}, {'retry-after': '0'}), ok]
        with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'k'}), \
                mock.patch('codesentry.llm_providers.requests.post', side_effect=lambda *a, **k: calls.pop(0)), \
                mock.patch('codesentry.llm_providers.time.sleep') as sleep:
            self.assertEqual(create_provider(CFG).chat('p', 's'), 'hi')
            self.assertEqual(sleep.call_count, 1)

    def test_gives_up_after_max_retries(self):
        cfg = {'llm': {**CFG['llm'], 'providers': {'groq': {**CFG['llm']['providers']['groq'], 'max_retries': 1}}}}
        with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'k'}), \
                mock.patch('codesentry.llm_providers.requests.post', return_value=FakeResp(503, 'down')) as post, \
                mock.patch('codesentry.llm_providers.time.sleep'):
            self.assertTrue(create_provider(cfg).chat('p', 's').startswith('Error: API returned status 503'))
            self.assertEqual(post.call_count, 2)

    def test_does_not_retry_client_errors(self):
        with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'k'}), \
                mock.patch('codesentry.llm_providers.requests.post', return_value=FakeResp(401, 'bad key')) as post:
            create_provider(CFG).chat('p', 's')
            self.assertEqual(post.call_count, 1)


if __name__ == '__main__':
    unittest.main()
