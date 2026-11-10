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


if __name__ == '__main__':
    unittest.main()
