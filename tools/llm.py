from langchain.chat_models import init_chat_model

# Maps shorthand config values to (provider, model_name)
_SHORTCUTS = {
    "gemini-flash": ("google_genai", "gemini-2.0-flash"),
    "gemini-pro": ("google_genai", "gemini-2.5-pro"),
    "claude-haiku": ("anthropic", "claude-haiku-4-5-20251001"),
    "claude-sonnet": ("anthropic", "claude-sonnet-4-6"),
}

_PROVIDER_ALIASES = {
    "groq": "groq",
    "gemini": "google_genai",
    "google_genai": "google_genai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "ollama": "ollama",
}


import re as _re


def _extract_retry_after(err_str: str) -> str:
    m = _re.search(r"Please try again in ([\d]+m[\d.]+s|[\d.]+s|[\d]+ minutes?)", err_str)
    return m.group(1) if m else "a few minutes"


class _RateLimitAwareLLM:
    """Thin wrapper that converts provider rate-limit errors to a clean RuntimeError."""

    def __init__(self, model):
        self._model = model

    def invoke(self, prompt, **kwargs):
        try:
            return self._model.invoke(prompt, **kwargs)
        except Exception as e:
            name = type(e).__name__.lower()
            msg = str(e).lower()
            if "ratelimit" in name or "rate_limit" in name or "429" in msg or "rate limit" in msg:
                retry_in = _extract_retry_after(str(e))
                raise RuntimeError(
                    f"RATE_LIMIT:Groq token limit reached — try again in {retry_in}"
                ) from e
            raise


def get_model(model_str: str):
    """Parse a model string from .env and return a LangChain chat model.

    Accepted formats:
      groq/llama-3.3-70b-versatile
      gemini-flash
      claude-haiku
      ollama/mistral
    """
    if model_str in _SHORTCUTS:
        provider, model_name = _SHORTCUTS[model_str]
        return _RateLimitAwareLLM(init_chat_model(model_name, model_provider=provider))

    if "/" in model_str:
        provider_raw, model_name = model_str.split("/", 1)
        provider = _PROVIDER_ALIASES.get(provider_raw, provider_raw)
        return _RateLimitAwareLLM(init_chat_model(model_name, model_provider=provider))

    return _RateLimitAwareLLM(init_chat_model(model_str))
