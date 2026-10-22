from __future__ import annotations

import base64
import time

from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from rmd.config import get_settings
from rmd.providers.base import ChatResult, EmbeddingProvider, LLMProvider, Usage

OCR_PROMPT = (
    "Transcribe ALL text on this scanned book page exactly as printed, preserving line breaks, "
    "paragraph breaks and diacritics (ā ī ū ṛ ṣ ṇ ṁ ñ ś etc.). Keep Sanskrit/Hindi transliterations "
    "exactly as written; do not translate, correct, summarize or add anything. Include headers, footers "
    "and the printed page number if present. If a region is unreadable write [illegible]. "
    "If the page has no text, output exactly [blank page]. Output only the transcription."
)


def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.openai_api_key or None, timeout=60, max_retries=0)


_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)


class OpenAIEmbeddings(EmbeddingProvider):
    name = "openai"

    def __init__(self, model: str | None = None, dimensions: int | None = None):
        s = get_settings()
        self.model = model or s.embedding_model
        self.dimensions = dimensions or s.embedding_dimensions
        self._client = _client()

    @_retry
    def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        if not texts:
            return [], Usage(model=self.model)
        resp = self._client.embeddings.create(
            model=self.model,
            input=[t.replace("\n", " ") for t in texts],
            dimensions=self.dimensions,
        )
        vectors = [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        return vectors, Usage(prompt_tokens=resp.usage.prompt_tokens, model=self.model)


class OpenAILLM(LLMProvider):
    name = "openai"

    def __init__(self):
        self._client = _client()
        self._settings = get_settings()

    @_retry
    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        model = model or self._settings.generation_model
        kwargs: dict = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(**kwargs)
        latency = (time.perf_counter() - t0) * 1000
        u = resp.usage
        return ChatResult(
            text=resp.choices[0].message.content or "",
            usage=Usage(u.prompt_tokens, u.completion_tokens, model),
            latency_ms=round(latency, 1),
        )

    def ocr_image(self, png_bytes: bytes, *, model: str | None = None) -> ChatResult:
        b64 = base64.b64encode(png_bytes).decode()
        return self.chat(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
                        },
                    ],
                }
            ],
            model=model or self._settings.generation_model,
            temperature=0.0,
        )
