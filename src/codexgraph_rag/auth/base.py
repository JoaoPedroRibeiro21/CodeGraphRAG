"""Base authentication provider for CodexGraph-RAG."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import chainlit as cl


class AuthProvider(ABC):
    """Pluggable authentication provider for Chainlit."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Return True if the provider is configured and should be used."""

    @abstractmethod
    def setup(self) -> None:
        """Register callbacks or configuration with Chainlit."""

    @abstractmethod
    async def process_user_metadata(self, user: cl.User | None) -> cl.User | None:
        """Optional post-login hook (avatar download, etc.)."""
