"""Artifact extraction strategies for different languages/domains."""

from codexgraph_rag.artifacts.strategies import (
    GenericArtifactStrategy,
    JavaArtifactStrategy,
    _ArtifactStrategy,
    get_strategy,
)

__all__ = [
    "_ArtifactStrategy",
    "GenericArtifactStrategy",
    "JavaArtifactStrategy",
    "get_strategy",
]
