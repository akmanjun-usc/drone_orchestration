"""
LLM provider interface.

Every concrete provider (Anthropic, OpenAI, Ollama, etc.)
must subclass LLMProvider and implement `complete`.
The orchestrator only ever calls this interface — it never
imports a vendor SDK directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Message:
    """A single turn in a conversation."""
    role: str        # "user" or "assistant"
    content: str


@dataclass
class CompletionRequest:
    """Everything needed to make one LLM call."""
    system_prompt: str
    messages: list[Message]
    model: str
    max_tokens: int = 2048
    temperature: float = 0.0   # deterministic by default for code generation


@dataclass
class CompletionResponse:
    """Normalised response from any provider."""
    content: str                    # the raw text the model produced
    model: str                      # model identifier that was actually used
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implement this to add a new model backend without
    touching any other part of the codebase.
    """

    @abstractmethod
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Send a completion request and return the response.

        Args:
            request: A CompletionRequest with system prompt, messages, and config.

        Returns:
            A CompletionResponse with the model's text and token counts.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name for logging, e.g. 'anthropic' or 'openai'."""
        ...
