"""Simple password authentication provider (Chainlit native)."""

import logging
import os

import chainlit as cl

from codexgraph_rag.auth.base import AuthProvider

logger = logging.getLogger(__name__)


class PasswordAuthProvider(AuthProvider):
    @property
    def name(self) -> str:
        return "password"

    def is_enabled(self) -> bool:
        return bool(os.getenv("CHAINLIT_AUTH_SECRET", "").strip())

    def setup(self) -> None:
        if not self.is_enabled():
            logger.warning("CHAINLIT_AUTH_SECRET não configurado; auth por senha desabilitado.")
            return

        @cl.password_auth_callback
        def auth_callback(username: str, password: str) -> cl.User | None:
            # Accept any non-empty password in the default implementation.
            # Replace with real validation for production use.
            if username and password:
                return cl.User(
                    identifier=username,
                    metadata={"name": username, "provider": "password"},
                )
            return None

    async def process_user_metadata(self, user: cl.User | None) -> cl.User | None:
        return user
