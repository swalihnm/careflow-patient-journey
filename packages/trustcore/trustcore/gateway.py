"""LLM gateway: CLAUDE.md's engineering rule is "all LLM calls through
trustcore.gateway" -- one place that audits every call and fails predictably
when no provider is configured, instead of every call site reimplementing
that check.

Wraps LiteLLM so any provider (Anthropic, OpenAI, Ollama Cloud's
OpenAI-compatible endpoint, ...) works from one interface. `litellm` is a
lazy import, not a hard dependency of trustcore itself -- projects that
never call an LLM shouldn't need to install it.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from trustcore.audit import record

# Searches CWD and parent directories for a `.env` file -- finds the repo
# root's .env as long as commands run from within the repo, which they
# always do here. A no-op (not an error) if no .env exists yet.
load_dotenv()

# Ollama Cloud (https://ollama.com) speaks the OpenAI Chat Completions API at
# this base URL, authenticated with OLLAMA_API_KEY rather than OPENAI_API_KEY
# -- litellm's `openai/<model>` prefix routes to any OpenAI-compatible
# endpoint given an explicit api_base + api_key, it just doesn't know to look
# for OLLAMA_API_KEY on its own the way it auto-reads OPENAI_API_KEY.
_OLLAMA_CLOUD_API_BASE = "https://ollama.com/v1"

DEFAULT_MODEL = os.environ.get("CAREFLOW_LLM_MODEL", "claude-haiku-4-5-20251001")
DEFAULT_API_BASE = os.environ.get("CAREFLOW_LLM_API_BASE")


class LLMNotConfigured(Exception):
    pass


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


def _provider_api_key() -> str | None:
    return (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OLLAMA_API_KEY")
        or os.environ.get("LITELLM_API_KEY")
    )


def is_configured() -> bool:
    return bool(_provider_api_key())


def complete(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    actor: str = "assistant",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> LLMResponse:
    """Raises LLMNotConfigured (not a silent fallback) when no API key is set,
    so callers can implement an explicit non-LLM path rather than getting a
    confusing downstream failure."""
    api_key = _provider_api_key()
    if not api_key:
        record(
            actor=actor, actor_role="system", action="llm_call", resource_type=model,
            result="deny", reason="no LLM API key configured",
        )
        raise LLMNotConfigured(
            "No LLM API key configured (set ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
            "OLLAMA_API_KEY in .env)."
        )

    import litellm

    kwargs: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}

    # Anthropic/OpenAI native models: litellm reads their env vars itself,
    # nothing extra to pass. Anything else (Ollama Cloud's openai/* models,
    # or a custom endpoint) needs an explicit api_base + api_key.
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        api_base = DEFAULT_API_BASE or (_OLLAMA_CLOUD_API_BASE if os.environ.get("OLLAMA_API_KEY") else None)
        if api_base:
            kwargs["api_base"] = api_base
            kwargs["api_key"] = api_key

    response = litellm.completion(**kwargs)
    text = response.choices[0].message.content
    usage = response.usage

    record(
        actor=actor, actor_role="system", action="llm_call", resource_type=model,
        result="allow", reason=None,
    )

    return LLMResponse(
        text=text,
        model=model,
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
    )
