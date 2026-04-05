"""
Provider factory.

Reads LLM_PROVIDER and LLM_MODEL from the environment
and returns a ready-to-use LLMProvider instance.
"""

import os
from llm.provider import LLMProvider


def get_provider(
    provider_name: str | None = None,
    model: str | None = None,
    **kwargs,
) -> tuple[LLMProvider, str]:
    """
    Build and return (provider, model_name).

    Args:
        provider_name: "anthropic" | "openai" | "groq". Falls back to LLM_PROVIDER env var.
        model: Model string. Falls back to LLM_MODEL env var, then provider default.
        **kwargs: Extra args forwarded to the provider constructor (e.g. base_url).

    Returns:
        Tuple of (LLMProvider instance, model string to use in requests).
    """
    name = (provider_name or os.getenv("LLM_PROVIDER", "anthropic")).lower()
    resolved_model = model or os.getenv("LLM_MODEL", "")

    if name == "anthropic":
        from llm.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider(**kwargs)
        if not resolved_model:
            resolved_model = AnthropicProvider.DEFAULT_MODEL

    elif name == "openai":
        from llm.openai_provider import OpenAIProvider
        provider = OpenAIProvider(**kwargs)
        if not resolved_model:
            resolved_model = OpenAIProvider.DEFAULT_MODEL

    elif name == "groq":
        from llm.groq_provider import GroqProvider
        provider = GroqProvider(**kwargs)
        if not resolved_model:
            resolved_model = GroqProvider.DEFAULT_MODEL

    else:
        raise ValueError(
            f"Unknown provider '{name}'. "
            "Add a new subclass of LLMProvider and register it here."
        )

    return provider, resolved_model
