"""
Anthropic (Claude) provider.

Requires ANTHROPIC_API_KEY in environment or .env file.
"""

import os
import anthropic

from llm.provider import LLMProvider, CompletionRequest, CompletionResponse, Message


class AnthropicProvider(LLMProvider):
    """
    Calls the Anthropic Messages API.

    Default model is claude-sonnet-4-6 but any model string
    passed in CompletionRequest.model overrides it.
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or self.DEFAULT_MODEL

        response = self._client.messages.create(
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system_prompt,
            messages=[
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
        )

        content = response.content[0].text if response.content else ""

        return CompletionResponse(
            content=content,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
