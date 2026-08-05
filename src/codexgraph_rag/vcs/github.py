"""GitHub repository synchronizer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from codexgraph_rag.vcs.base import RepoSyncer, RepoTarget


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _run_git(args: List[str], cwd: Optional[Path] = None, mask: Optional[str] = None) -> str:
    cmd = ["git", *args]
    shown = " ".join(cmd)
    if mask:
        shown = shown.replace(mask, "***")
    print(f"[sync] {shown}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        details = stderr or stdout or "erro desconhecido do git"
        if mask:
            details = details.replace(mask, "***")
        raise RuntimeError(f"git {' '.join(args)} falhou: {details}")
    return proc.stdout.strip()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _with_auth(url: str, token: str) -> str:
    if not token:
        return url
    prefix = "https://github.com/"
    if url.startswith(prefix):
        return f"https://x-access-token:{token}@github.com/{url[len(prefix):]}"
    return url


def _fetch_release_name(client: httpx.Client, org: str, repo: str) -> Optional[str]:
    endpoint = f"https://api.github.com/repos/{org}/{repo}/releases/latest"
    resp = client.get(endpoint)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("name") or payload.get("tag_name")


def _fetch_default_branch(client: httpx.Client, org: str, repo: str) -> Optional[str]:
    endpoint = f"https://api.github.com/repos/{org}/{repo}"
    resp = client.get(endpoint)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("default_branch")


def _discover_topic_repos(client: httpx.Client, org: str, topic: str) -> List[str]:
    if not topic:
        return []

    query = f"org:{org} topic:{topic}"
    endpoint = "https://api.github.com/search/repositories"
    repos: List[str] = []
    page = 1

    while True:
        resp = client.get(endpoint, params={"q": query, "per_page": 100, "page": page})
        if resp.status_code == 422:
            print(f"[sync] aviso: busca por tópico retornou 422; ignorando descoberta automática para '{topic}'")
            return []
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            name = item.get("name")
            if name:
                repos.append(name)

        if len(items) < 100:
            break
        page += 1

    return repos


def _github_client(token: str) -> httpx.Client:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(timeout=30.0, headers=headers)


class GitHubSyncer(RepoSyncer):
    name = "github"

    def discover_repositories(self, config: Dict[str, Any]) -> List[RepoTarget]:
        topic = str(config.get("github_topic") or "").strip()
        org = str(config.get("github_org") or "").strip()
        default_branch = str(config.get("default_branch") or "main").strip() or "main"
        if not org and topic:
            print("[sync] aviso: tópico definido sem GITHUB_ORG; descoberta ignorada")
            return []
        if not org:
            return []

        token = os.getenv("GITHUB_TOKEN", "").strip()
        discovered: List[str] = []
        with _github_client(token) as client:
            discovered = _discover_topic_repos(client, org, topic)

        seen: set[str] = set()
        targets: List[RepoTarget] = []
        for repo in discovered:
            if repo in seen:
                continue
            seen.add(repo)
            targets.append(
                RepoTarget(
                    name=repo,
                    url=f"https://github.com/{org}/{repo}.git",
                    org=org,
                    repo=repo,
                    branch=None,
                    priority="secondary",
                    vcs_provider="github",
                )
            )
        return targets

    def sync_repository(
        self,
        target: RepoTarget,
        base_dir: Path,
        token: str,
        ttl: timedelta,
        previous: Optional[Dict[str, Any]],
        client: Any,
    ) -> Dict[str, Any]:
        full_name = f"{target.org}/{target.repo}"
        local_path = base_dir / target.org / target.repo
        synced_at = utc_now().isoformat()

        cached_at = parse_iso((previous or {}).get("synced_at"))
        cache_valid = (
            previous
            and previous.get("status") == "ok"
            and cached_at is not None
            and utc_now() - cached_at < ttl
            and local_path.exists()
            and (local_path / ".git").exists()
        )

        clone_url = target.url
        auth_url = _with_auth(clone_url, token)
        branch = target.branch or _fetch_default_branch(client, target.org, target.repo) or "main"

        if cache_valid:
            print(f"[sync] cache hit para {full_name}; pulando git sync")
        else:
            _ensure_dir(local_path.parent)
            if local_path.exists() and not (local_path / ".git").exists():
                shutil.rmtree(local_path)

            if not local_path.exists():
                _run_git(["clone", "--branch", branch, "--single-branch", auth_url, str(local_path)], mask=token)
            else:
                _run_git(["fetch", "origin", branch], cwd=local_path, mask=token)
                _run_git(["checkout", branch], cwd=local_path)
                _run_git(["pull", "--ff-only", "origin", branch], cwd=local_path, mask=token)

        commit_sha = _run_git(["rev-parse", "HEAD"], cwd=local_path)

        release_name = None
        try:
            release_name = _fetch_release_name(client, target.org, target.repo)
        except Exception as exc:
            print(f"[sync] aviso: não foi possível buscar release de {full_name}: {exc}")

        return {
            "full_name": full_name,
            "name": target.repo,
            "org": target.org,
            "branch": branch,
            "priority": target.priority,
            "clone_url": clone_url,
            "local_path": str(local_path),
            "commit_sha": commit_sha,
            "release_name": release_name,
            "synced_at": synced_at,
            "status": "ok",
            "error": None,
            "configured_name": target.name,
            "configured_url": target.url,
            "vcs_provider": "github",
        }
