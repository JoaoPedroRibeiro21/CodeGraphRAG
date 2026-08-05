"""Factory for VCS repository synchronizers."""

from __future__ import annotations

from typing import Dict, Type

from codexgraph_rag.vcs.base import RepoSyncer
from codexgraph_rag.vcs.github import GitHubSyncer
from codexgraph_rag.vcs.gitlab import GitLabSyncer


_SYNCER_CLASSES: Dict[str, Type[RepoSyncer]] = {
    "github": GitHubSyncer,
    "gitlab": GitLabSyncer,
}


def list_syncers() -> list[str]:
    """Return all registered VCS provider names."""
    return list(_SYNCER_CLASSES.keys())


def get_syncer(provider: str) -> RepoSyncer:
    """Return a synchronizer instance for the given provider name."""
    name = provider.lower().strip()
    if name not in _SYNCER_CLASSES:
        raise ValueError(
            f"Unknown VCS provider: {provider!r}. Available: {list_syncers()}"
        )
    return _SYNCER_CLASSES[name]()
