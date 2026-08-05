"""Factory for authentication providers."""

from __future__ import annotations

from codexgraph_rag.auth.base import AuthProvider
from codexgraph_rag.auth.google import GoogleAuthProvider
from codexgraph_rag.auth.no_auth import NoAuthProvider
from codexgraph_rag.auth.password import PasswordAuthProvider


_PROVIDER_CLASSES: dict[str, type[AuthProvider]] = {
    "none": NoAuthProvider,
    "password": PasswordAuthProvider,
    "google": GoogleAuthProvider,
}


def list_auth_providers() -> list[str]:
    """Return all registered auth provider names."""
    return list(_PROVIDER_CLASSES.keys())


def get_auth_provider(name: str) -> AuthProvider:
    """Instantiate an auth provider by name."""
    name = name.lower().strip()
    if name not in _PROVIDER_CLASSES:
        raise ValueError(f"Unknown auth provider: {name}. Available: {list_auth_providers()}")
    return _PROVIDER_CLASSES[name]()
