"""Base abstraction for repository synchronization providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RepoTarget:
    name: str
    url: str
    org: str
    repo: str
    branch: Optional[str]
    priority: str
    vcs_provider: str = "github"


class RepoSyncer(ABC):
    """Abstract interface for discovering and syncing repositories from a VCS."""

    name: str = ""

    @abstractmethod
    def discover_repositories(self, config: Dict[str, Any]) -> List[RepoTarget]:
        """Return a list of repositories discovered via this provider.

        Args:
            config: free-form configuration dict (e.g. from repos.json).
        """
        ...

    @abstractmethod
    def sync_repository(
        self,
        target: RepoTarget,
        base_dir: Path,
        token: str,
        ttl: timedelta,
        previous: Optional[Dict[str, Any]],
        client: Any,
    ) -> Dict[str, Any]:
        """Clone or update a single repository and return its state entry."""
        ...
