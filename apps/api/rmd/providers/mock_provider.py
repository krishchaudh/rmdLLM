"""Deterministic offline providers for tests and local development without API keys."""

from __future__ import annotations

import hashlib
import json
import math
import re

from rmd.providers.base import ChatResult, EmbeddingProvider, LLMProvider, Usage


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class MockEmbeddings(EmbeddingProvider):
    """Hashed bag-of-words embedding: deterministic, overlaps on shared tokens, unit-normalised."""

    name = "mock"
    model = "mock-hash"

    def __init__(self, dimensions: int = 1024):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        out = []
        for t in texts:
            v = [0.0] * self.dimensions
            for tok in _tokens(t):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % self.dimensions] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out, Usage(prompt_tokens=sum(len(_tokens(t)) for t in texts), model=self.model)


class MockLLM(LLMProvider):
    name = "mock"

    def __init__(self, scripted: list[str] | None = None):
        self.scripted = list(scripted or [])
        self.calls: list[list[dict]] = []

    def chat(self, messages, *, model=None, temperature=0.0, max_tokens=None, json_mode=False):
        self.calls.append(messages)
        if self.scripted:
            text = self.scripted.pop(0)
        elif json_mode:
            text = json.dumps({"mock": True})
        else:
            text = "[mock answer]"
        return ChatResult(text=text, usage=Usage(10, 5, "mock"), latency_ms=1.0)

    def ocr_image(self, png_bytes: bytes, *, model=None) -> ChatResult:
        return ChatResult(text="[mock ocr]", usage=Usage(1, 1, "mock"), latency_ms=1.0)
