"""No-op authentication provider (development / open installations)."""

import logging

import chainlit as cl

from codexgraph_rag.auth.base import AuthProvider

logger = logging.getLogger(__name__)


class NoAuthProvider(AuthProvider):
    @property
    def name(self) -> str:
        return "none"

    def is_enabled(self) -> bool:
        return True

    def setup(self) -> None:
        logger.info("Auth desabilitado: sessões serão anônimas.")

    async def process_user_metadata(self, user: cl.User | None) -> cl.User | None:
        return user
