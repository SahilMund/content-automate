from langchain.chat_models import init_chat_model

# Maps shorthand config values to (provider, model_name)
_SHORTCUTS = {
    "gemini-flash": ("google_genai", "gemini-1.5-flash"),
    "gemini-pro": ("google_genai", "gemini-1.5-pro"),
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
        return init_chat_model(model_name, model_provider=provider)

    if "/" in model_str:
        provider_raw, model_name = model_str.split("/", 1)
        provider = _PROVIDER_ALIASES.get(provider_raw, provider_raw)
        return init_chat_model(model_name, model_provider=provider)

    return init_chat_model(model_str)
