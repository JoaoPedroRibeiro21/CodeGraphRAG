"""Provider factory for chat models and embedding models.

Supported providers:
- openai
- anthropic
- google
- ollama

Configuration comes from codexgraph_rag.config.LLMConfig / EmbeddingConfig.
The user provides the API key via env var, config file, or setup wizard before
running the application.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from codexgraph_rag.config import EmbeddingConfig, LLMConfig

logger = logging.getLogger(__name__)


def _pop_none(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


def build_chat_model(cfg: LLMConfig | None = None) -> BaseChatModel:
    """Build a LangChain chat model from config.

    If cfg is None, loads from global settings.
    """
    if cfg is None:
        from codexgraph_rag import settings
        cfg = settings.config.llm

    provider = cfg.provider.lower().strip()
    api_key = cfg.api_key or os.getenv(f"{provider.upper()}_API_KEY") or os.getenv("OPENAI_API_KEY")
    kwargs = _pop_none({
        "model": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "timeout": cfg.timeout,
        "base_url": cfg.base_url,
    })

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=api_key, **kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=api_key, **kwargs)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(google_api_key=api_key, **kwargs)

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(base_url=cfg.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), **kwargs)

    raise ValueError(f"Unsupported chat provider: {provider}")


def build_embeddings(cfg: EmbeddingConfig | None = None) -> Embeddings:
    """Build a LangChain embeddings model from config.

    If cfg is None, loads from global settings.
    """
    if cfg is None:
        from codexgraph_rag import settings
        cfg = settings.config.embeddings

    provider = cfg.provider.lower().strip()
    api_key = cfg.api_key or os.getenv(f"{provider.upper()}_API_KEY") or os.getenv("OPENAI_API_KEY")
    kwargs = _pop_none({
        "model": cfg.model,
        "chunk_size": cfg.chunk_size,
    })

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(api_key=api_key, **kwargs)

    if provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        return GoogleGenerativeAIEmbeddings(google_api_key=api_key, **kwargs)

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(base_url=cfg.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), **kwargs)

    if provider == "anthropic":
        # Anthropic does not provide embeddings models; route to a default local-friendly fallback.
        raise ValueError(
            "Anthropic does not expose embeddings models. "
            "Use openai, google, or ollama for embeddings."
        )

    raise ValueError(f"Unsupported embeddings provider: {provider}")
