"""Google OAuth authentication provider."""

import logging
import os

import chainlit as cl
import httpx

from codexgraph_rag.auth.base import AuthProvider

logger = logging.getLogger(__name__)


class GoogleAuthProvider(AuthProvider):
    @property
    def name(self) -> str:
        return "google"

    def is_enabled(self) -> bool:
        disable = os.getenv("DISABLE_GOOGLE_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}
        if disable:
            return False
        return bool(
            os.getenv("OAUTH_GOOGLE_CLIENT_ID", "").strip()
            and os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "").strip()
        )

    def setup(self) -> None:
        if not self.is_enabled():
            logger.info("OAuth Google desabilitado para esta execução")
            return

        @cl.oauth_callback
        def oauth_callback(
            provider_id: str,
            token: str,
            raw_user_data: dict,
            default_user: cl.User,
        ) -> cl.User | None:
            if provider_id == "google":
                picture_url = raw_user_data.get("picture", "")
                return cl.User(
                    identifier=raw_user_data.get("email", default_user.identifier),
                    metadata={
                        "name": raw_user_data.get("name", ""),
                        "email": raw_user_data.get("email", ""),
                        "image": picture_url,
                        "picture": picture_url,
                        "provider": "google",
                    },
                )
            return default_user

    async def process_user_metadata(self, user: cl.User | None) -> cl.User | None:
        if not user or not user.metadata.get("image"):
            return user
        try:
            image_url = user.metadata.get("image")
            avatar_dir = os.path.join(os.getcwd(), "public", "avatars")
            os.makedirs(avatar_dir, exist_ok=True)
            avatar_path = os.path.join(avatar_dir, f"{user.identifier}.png")
            if not os.path.exists(avatar_path):
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url)
                    if response.status_code == 200:
                        with open(avatar_path, "wb") as f:
                            f.write(response.content)
                        logger.info("Avatar salvo para %s", user.identifier)
        except Exception as e:
            logger.error("Erro ao processar avatar: %s", e)
        return user
