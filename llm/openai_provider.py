"""
OpenAI (GPT) provider.

Requires OPENAI_API_KEY in environment or .env file.
Also works with any OpenAI-compatible endpoint (Ollama, vLLM, etc.)
by passing a custom base_url.
"""

import os
from openai import OpenAI

from llm.provider import LLMProvider, CompletionRequest, CompletionResponse


class OpenAIProvider(LLMProvider):
    """
    Calls the OpenAI Chat Completions API.

    Pass base_url to point at any OpenAI-compatible server,
    e.g. Ollama running locally:
        OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama")
    """

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY", "ollama"),
            base_url=base_url,
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or self.DEFAULT_MODEL

        response = self._client.chat.completions.create(
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=[
                {"role": "system", "content": request.system_prompt},
                *[{"role": m.role, "content": m.content} for m in request.messages],
            ],
        )

        choice = response.choices[0]
        content = choice.message.content or ""

        return CompletionResponse(
            content=content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )
