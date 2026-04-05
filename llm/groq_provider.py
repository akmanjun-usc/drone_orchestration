"""
Groq provider.

Groq runs open-source models (Llama, Mixtral, Gemma) with very low
latency inference. Requires GROQ_API_KEY in environment or .env file.
"""

import os
from groq import Groq

from llm.provider import LLMProvider, CompletionRequest, CompletionResponse


class GroqProvider(LLMProvider):
    """
    Calls the Groq Chat Completions API.

    Groq's API is structurally identical to OpenAI's, but uses the
    groq package and a different key. Temperature 0 is supported and
    recommended for code generation.
    """

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str | None = None):
        self._client = Groq(
            api_key=api_key or os.environ["GROQ_API_KEY"]
        )

    @property
    def provider_name(self) -> str:
        return "groq"

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
