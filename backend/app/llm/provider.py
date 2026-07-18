"""
Provider-agnostic LLM interface.

`get_llm()` picks a provider based on configured API keys (or an explicit
override) and returns an object with a single async `generate(messages,
system=None, stream=False)` method. Every provider adapter implements the
same interface, so agents never know or care which backend answered.

Priority when OMNIMIND_FORCE_PROVIDER is unset:
  anthropic > openai > gemini > ollama > offline

The offline provider is deterministic (no network, no randomness) so the
whole app -- auth, chat, agent routing, RAG citations -- stays demoable
with zero configuration.
"""
from __future__ import annotations

import abc
from collections.abc import AsyncIterator

from app.config import settings


class LLMProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def generate(
        self, messages: list[dict], system: str | None = None
    ) -> str:
        """Return the full text response."""

    async def stream(
        self, messages: list[dict], system: str | None = None
    ) -> AsyncIterator[str]:
        """
        Default streaming shim: providers that support real token
        streaming should override this. Falls back to yielding the
        full response as a single chunk.
        """
        text = await self.generate(messages, system=system)
        yield text


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(self, messages, system=None) -> str:
        resp = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system or "",
            messages=messages,
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    async def stream(self, messages, system=None):
        async with self.client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system or "",
            messages=messages,
        ) as s:
            async for text in s.text_stream:
                yield text


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str):
        import openai
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate(self, messages, system=None) -> str:
        full = ([{"role": "system", "content": system}] if system else []) + messages
        resp = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=full,
        )
        return resp.choices[0].message.content or ""

    async def stream(self, messages, system=None):
        full = ([{"role": "system", "content": system}] if system else []) + messages
        stream = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=full,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.genai = genai

    async def generate(self, messages, system=None) -> str:
        model = self.genai.GenerativeModel(
            "gemini-1.5-flash", system_instruction=system or None
        )
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        resp = await model.generate_content_async(prompt)
        return resp.text


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, messages, system=None) -> str:
        import httpx
        full = ([{"role": "system", "content": system}] if system else []) + messages
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": full, "stream": False},
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]


class OfflineProvider(LLMProvider):
    """
    Zero-dependency, zero-network fallback. Deliberately simple and
    honest about what it is, rather than pretending to be a real model --
    this keeps the demo trustworthy instead of silently low-quality.
    """
    name = "offline"

    async def generate(self, messages, system=None) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        preview = last_user.strip()[:300]
        return (
            "[offline mode -- no LLM provider configured]\n\n"
            f"I received your message: \"{preview}\"\n\n"
            "This response was generated by the deterministic offline "
            "fallback, not a real language model. Add an API key "
            "(OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY) or run "
            "Ollama locally and set OLLAMA_BASE_URL to get real answers. "
            "All other systems (auth, routing, RAG retrieval, memory) are "
            "fully functional in this mode."
        )


_provider_instance: LLMProvider | None = None


def get_llm() -> LLMProvider:
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    forced = (settings.OMNIMIND_FORCE_PROVIDER or "").lower().strip() or None

    def build(name: str) -> LLMProvider | None:
        try:
            if name == "anthropic" and settings.ANTHROPIC_API_KEY:
                return AnthropicProvider(settings.ANTHROPIC_API_KEY)
            if name == "openai" and settings.OPENAI_API_KEY:
                return OpenAIProvider(settings.OPENAI_API_KEY)
            if name == "gemini" and settings.GEMINI_API_KEY:
                return GeminiProvider(settings.GEMINI_API_KEY)
            if name == "ollama":
                return OllamaProvider(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)
            if name == "offline":
                return OfflineProvider()
        except Exception:
            return None
        return None

    if forced:
        _provider_instance = build(forced) or OfflineProvider()
        return _provider_instance

    for name in ("anthropic", "openai", "gemini"):
        provider = build(name)
        if provider:
            _provider_instance = provider
            return _provider_instance

    # Ollama needs a live local server to be worth trying first; we don't
    # ping it here to keep startup fast, so it's only auto-picked when
    # forced. Default auto-selection ends at offline.
    _provider_instance = OfflineProvider()
    return _provider_instance


def reset_provider_cache():
    """Used by tests / hot-reload after changing env config."""
    global _provider_instance
    _provider_instance = None
