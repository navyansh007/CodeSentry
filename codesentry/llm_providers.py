"""
LLM Provider Abstraction - Talks to any commercial or open-source LLM backend

Every provider is called over plain HTTPS via `requests`, so adding support
for a new backend never requires a vendor SDK - just a new entry in
config.yaml's `llm.providers` map.
"""

import os
from typing import Any, Dict, Optional

import requests


class LLMProviderError(Exception):
    """Raised when a provider is misconfigured (missing key, unknown type, ...)"""


class BaseLLMProvider:
    """Common interface every provider implements"""

    def __init__(self, provider_name: str, provider_config: Dict[str, Any], llm_config: Dict[str, Any]):
        self.provider_name = provider_name
        self.provider_config = provider_config
        self.model = llm_config.get('model', '')
        self.max_tokens = llm_config.get('max_tokens', 2000)
        self.temperature = llm_config.get('temperature', 0.3)
        self.timeout = llm_config.get('timeout', 60)

        api_key_env = provider_config.get('api_key_env')
        # CODESENTRY_LLM_API_KEY is a provider-agnostic fallback, so CI
        # (e.g. the GitHub Action) can pass one secret whatever the provider
        self.api_key = (os.getenv(api_key_env) or os.getenv('CODESENTRY_LLM_API_KEY')) if api_key_env else None
        self.requires_key = api_key_env is not None

    def is_configured(self) -> bool:
        """Whether this provider has everything it needs to make a call"""
        return not self.requires_key or bool(self.api_key)

    def missing_key_message(self) -> str:
        api_key_env = self.provider_config.get('api_key_env')
        return f"{api_key_env} environment variable not set (required for provider '{self.provider_name}')"

    def chat(self, prompt: str, system_prompt: str) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Covers any backend that speaks the OpenAI /chat/completions wire format:
    OpenAI, Hugging Face router, Ollama, OpenRouter, Groq, Together, Mistral,
    DeepSeek, and self-hosted servers like vLLM/LocalAI/LM Studio.
    """

    def chat(self, prompt: str, system_prompt: str) -> str:
        api_url = self.provider_config.get('api_url')
        if not api_url:
            return f"Error: no api_url configured for provider '{self.provider_name}'"

        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'stream': False,
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                choices = data.get('choices') or []
                if choices:
                    return choices[0].get('message', {}).get('content', '') or 'Error: empty response'
                return "Error: unexpected response format"
            return f"Error: API returned status {response.status_code}: {response.text[:500]}"
        except requests.exceptions.Timeout:
            return "Error: request timeout"
        except requests.exceptions.RequestException as e:
            return f"Error: request failed - {str(e)}"


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI Service - same payload shape as OpenAI, different auth/URL"""

    def chat(self, prompt: str, system_prompt: str) -> str:
        api_url = self.provider_config.get('api_url')
        if not api_url:
            return "Error: no api_url configured for provider 'azure_openai' (set it to your deployment URL)"

        api_version = self.provider_config.get('api_version', '2024-06-01')
        separator = '&' if '?' in api_url else '?'
        url = f"{api_url}{separator}api-version={api_version}"

        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['api-key'] = self.api_key

        payload = {
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'stream': False,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                choices = data.get('choices') or []
                if choices:
                    return choices[0].get('message', {}).get('content', '') or 'Error: empty response'
                return "Error: unexpected response format"
            return f"Error: API returned status {response.status_code}: {response.text[:500]}"
        except requests.exceptions.Timeout:
            return "Error: request timeout"
        except requests.exceptions.RequestException as e:
            return f"Error: request failed - {str(e)}"


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude - /v1/messages, system prompt is a top-level field"""

    def chat(self, prompt: str, system_prompt: str) -> str:
        api_url = self.provider_config.get('api_url', 'https://api.anthropic.com/v1/messages')
        api_version = self.provider_config.get('api_version', '2023-06-01')

        headers = {
            'Content-Type': 'application/json',
            'anthropic-version': api_version,
        }
        if self.api_key:
            headers['x-api-key'] = self.api_key

        payload = {
            'model': self.model,
            'system': system_prompt,
            'messages': [
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                content = data.get('content') or []
                text_parts = [block.get('text', '') for block in content if block.get('type') == 'text']
                if text_parts:
                    return ''.join(text_parts)
                return "Error: unexpected response format"
            return f"Error: API returned status {response.status_code}: {response.text[:500]}"
        except requests.exceptions.Timeout:
            return "Error: request timeout"
        except requests.exceptions.RequestException as e:
            return f"Error: request failed - {str(e)}"


class GoogleGeminiProvider(BaseLLMProvider):
    """Google Gemini - generateContent endpoint, key passed as a query param"""

    def chat(self, prompt: str, system_prompt: str) -> str:
        base_url = self.provider_config.get(
            'api_url', 'https://generativelanguage.googleapis.com/v1beta/models'
        )
        url = f"{base_url}/{self.model}:generateContent"
        if self.api_key:
            url = f"{url}?key={self.api_key}"

        payload = {
            'system_instruction': {'parts': [{'text': system_prompt}]},
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {
                'maxOutputTokens': self.max_tokens,
                'temperature': self.temperature,
            },
        }

        try:
            response = requests.post(
                url,
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                candidates = data.get('candidates') or []
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    text = ''.join(p.get('text', '') for p in parts)
                    return text or 'Error: empty response'
                return "Error: unexpected response format"
            return f"Error: API returned status {response.status_code}: {response.text[:500]}"
        except requests.exceptions.Timeout:
            return "Error: request timeout"
        except requests.exceptions.RequestException as e:
            return f"Error: request failed - {str(e)}"


_PROVIDER_TYPES = {
    'openai_compatible': OpenAICompatibleProvider,
    'azure_openai': AzureOpenAIProvider,
    'anthropic': AnthropicProvider,
    'google': GoogleGeminiProvider,
}


def create_provider(config: Dict[str, Any]) -> BaseLLMProvider:
    """Factory: build the configured provider from config['llm']"""
    llm_config = config.get('llm', {})
    provider_name = llm_config.get('provider', 'huggingface')
    providers = llm_config.get('providers', {})

    provider_config = providers.get(provider_name)
    if provider_config is None:
        raise LLMProviderError(
            f"Unknown LLM provider '{provider_name}'. "
            f"Available providers: {', '.join(providers.keys()) or 'none configured'}"
        )

    provider_type = provider_config.get('type', 'openai_compatible')
    provider_cls = _PROVIDER_TYPES.get(provider_type)
    if provider_cls is None:
        raise LLMProviderError(
            f"Unknown provider type '{provider_type}' for provider '{provider_name}'. "
            f"Supported types: {', '.join(_PROVIDER_TYPES.keys())}"
        )

    return provider_cls(provider_name, provider_config, llm_config)
