from __future__ import annotations

from functools import lru_cache

from rmd.config import get_settings
from rmd.providers.base import EmbeddingProvider, LLMProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    s = get_settings()
    if s.embedding_provider == "mock":
        from rmd.providers.mock_provider import MockEmbeddings

        return MockEmbeddings(s.embedding_dimensions)
    from rmd.providers.openai_provider import OpenAIEmbeddings

    return OpenAIEmbeddings()


@lru_cache
def get_llm_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "mock":
        from rmd.providers.mock_provider import MockLLM

        return MockLLM()
    from rmd.providers.openai_provider import OpenAILLM

    return OpenAILLM()
