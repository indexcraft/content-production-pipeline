"""
llm_client.py
--------------
Every stage of this pipeline (researcher, outliner, writer, editor, SEO
specialist) calls through this one module. One place to swap providers,
one place to add retry logic, one place to test.

Supports OpenAI and Anthropic — auto-detects which to use based on which
API key is set, same pattern as the other tools in this series.
"""

import os
import requests

PROVIDER_ENV_KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-3-5-haiku-20241022"}


def get_configured_provider() -> str:
    explicit = os.environ.get("CONTENT_PIPELINE_LLM_PROVIDER", "").lower()
    if explicit in PROVIDER_ENV_KEYS and os.environ.get(PROVIDER_ENV_KEYS[explicit]):
        return explicit
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def _query_openai(prompt: str, model: str, api_key: str, system: str = None, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _query_anthropic(prompt: str, model: str, api_key: str, system: str = None, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    payload = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": [{"role": "user", "content": prompt}]}
    if system:
        payload["system"] = system

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()
    blocks = [b["text"] for b in resp.json().get("content", []) if b.get("type") == "text"]
    return "\n".join(blocks)


PROVIDER_FUNCTIONS = {"openai": _query_openai, "anthropic": _query_anthropic}


def call_llm(prompt: str, system: str = None, provider: str = None, model: str = None,
             max_tokens: int = 2000, temperature: float = 0.7) -> str:
    provider = provider or get_configured_provider()
    if not provider:
        raise RuntimeError("No LLM API key configured — set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    api_key = os.environ.get(PROVIDER_ENV_KEYS[provider])
    model = model or DEFAULT_MODELS[provider]
    return PROVIDER_FUNCTIONS[provider](prompt, model, api_key, system=system, max_tokens=max_tokens, temperature=temperature)
