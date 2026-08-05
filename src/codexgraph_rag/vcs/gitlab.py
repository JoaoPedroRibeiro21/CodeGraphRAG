"""GitLab repository synchronizer (stub)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from codexgraph_rag.vcs.base import RepoSyncer, RepoTarget


class GitLabSyncer(RepoSyncer):
    name = "gitlab"

    def discover_repositories(self, config: Dict[str, Any]) -> List[RepoTarget]:
        """GitLab discovery is not implemented yet."""
        raise NotImplementedError("GitLab repository discovery is not implemented yet.")

    def sync_repository(
        self,
        target: RepoTarget,
        base_dir: Path,
        token: str,
        ttl: timedelta,
        previous: Optional[Dict[str, Any]],
        client: Any,
    ) -> Dict[str, Any]:
        """GitLab sync is not implemented yet."""
        raise NotImplementedError("GitLab repository sync is not implemented yet.")
