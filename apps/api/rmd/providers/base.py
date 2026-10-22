"""Provider interfaces. Concrete implementations live next to this module; selection in factory.py."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatResult:
    text: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0


class EmbeddingProvider(ABC):
    name: str
    model: str
    dimensions: int

    @abstractmethod
    def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]: ...


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult: ...

    @abstractmethod
    def ocr_image(self, png_bytes: bytes, *, model: str | None = None) -> ChatResult: ...


# USD per 1M tokens (input, output). Used only for *estimated* cost reporting.
PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
    "gpt-5-mini": (0.25, 2.00),
    "text-embedding-3-large": (0.13, 0.0),
    "text-embedding-3-small": (0.02, 0.0),
}


def estimate_cost_usd(usage: Usage) -> float | None:
    price = PRICING_USD_PER_1M.get(usage.model)
    if price is None:
        return None
    return round(
        (usage.prompt_tokens * price[0] + usage.completion_tokens * price[1]) / 1_000_000, 6
    )
