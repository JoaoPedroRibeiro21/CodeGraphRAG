import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_graph_path() -> Path:
    configured = os.getenv("CODE_GRAPH_PATH", "").strip()
    if configured:
        return Path(configured)

    container_path = Path("/app/code_graph_storage/code_graph.gpickle")
    if container_path.parent.exists():
        return container_path

    return Path("./code_graph.gpickle")


def resolve_meta_path(graph_path: Path) -> Path:
    configured = os.getenv("CODE_GRAPH_META_PATH", "").strip()
    if configured:
        return Path(configured)
    return graph_path.with_name("code_graph_meta.json")


def resolve_repo_state_path() -> Path:
    configured = os.getenv("REPO_STATE_FILE", "").strip()
    if configured:
        return Path(configured)
    return Path("/app/repos_sources/repos_state.json")


def resolve_chroma_dir() -> Path:
    configured = os.getenv("CODE_GRAPH_DB_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path("./chroma_graph_db")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def collect_repo_commits(repo_state: dict) -> dict[str, str]:
    commits: dict[str, str] = {}
    for repo in repo_state.get("repositories", []):
        if (repo or {}).get("status") != "ok":
            continue
        name = str((repo or {}).get("configured_name") or (repo or {}).get("name") or "").strip()
        sha = str((repo or {}).get("commit_sha") or "").strip()
        if name and sha:
            commits[name] = sha
    return commits


def chroma_is_empty(chroma_dir: Path) -> bool:
    if not chroma_dir.exists() or not chroma_dir.is_dir():
        return True
    return not any(chroma_dir.iterdir())


def graph_is_stale(
    graph_exists: bool,
    graph_meta: dict,
    current_commits: dict[str, str],
    ttl_hours: int,
    now: datetime | None = None,
) -> tuple[bool, str]:
    if not graph_exists:
        return True, "grafo_ausente"
    if not current_commits:
        return True, "repos_sem_commits"
    if not graph_meta:
        return True, "meta_ausente"

    previous_commits = graph_meta.get("repo_commits") or {}
    if previous_commits != current_commits:
        return True, "commits_alterados"

    built_at = parse_iso(graph_meta.get("built_at"))
    if not built_at:
        return True, "meta_sem_data"

    now = now or utc_now()
    if now - built_at >= timedelta(hours=max(ttl_hours, 1)):
        return True, "ttl_expirado"

    return False, "atualizado"


def run_python(script_name: str, env: dict[str, str]) -> int:
    cmd = [sys.executable, script_name]
    print(f"[refresh] executando: {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def persist_graph_meta(meta_path: Path, commits: dict[str, str], reason: str) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "built_at": utc_now().isoformat(),
        "repo_commits": commits,
        "reason": reason,
    }
    meta_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_refresh_once() -> int:
    load_dotenv()

    graph_path = resolve_graph_path()
    meta_path = resolve_meta_path(graph_path)
    repo_state_path = resolve_repo_state_path()
    chroma_dir = resolve_chroma_dir()
    ttl_hours = int(os.getenv("CODE_GRAPH_REBUILD_TTL_HOURS", os.getenv("REPO_SYNC_TTL_HOURS", "336")))
    force_rebuild = os.getenv("CODE_GRAPH_FORCE_REBUILD", "false").strip().lower() in {"1", "true", "yes"}

    env = os.environ.copy()
    env["REPO_STATE_FILE"] = str(repo_state_path)
    env["CODE_GRAPH_OUTPUT"] = str(graph_path)
    env["CODE_GRAPH_PATH"] = str(graph_path)

    print("[refresh] iniciando sincronização dos repositórios")
    sync_rc = run_python("sync_repos.py", env)
    if sync_rc != 0:
        print(f"[refresh] aviso: sync_repos.py retornou {sync_rc}. Tentando continuar com estado existente.")

    repo_state = load_json(repo_state_path)
    commits = collect_repo_commits(repo_state)
    graph_meta = load_json(meta_path)

    rebuild_reason = "forcado" if force_rebuild else ""
    needs_rebuild = force_rebuild
    if not needs_rebuild:
        needs_rebuild, rebuild_reason = graph_is_stale(
            graph_exists=graph_path.exists() and graph_path.stat().st_size > 0,
            graph_meta=graph_meta,
            current_commits=commits,
            ttl_hours=ttl_hours,
        )

    if needs_rebuild:
        print(f"[refresh] rebuild necessário: {rebuild_reason}")
        build_rc = run_python("build_graph.py", env)
        if build_rc != 0:
            print(f"[refresh] erro: build_graph.py retornou {build_rc}")
            return build_rc

        index_rc = run_python("preCarregaGrafo.py", env)
        if index_rc != 0:
            print(f"[refresh] erro: preCarregaGrafo.py retornou {index_rc}")
            return index_rc

        persist_graph_meta(meta_path, commits, rebuild_reason)
        print(f"[refresh] rebuild concluído. Meta atualizada em {meta_path}")
        return 0

    if chroma_is_empty(chroma_dir):
        print("[refresh] chroma de código ausente/vazio; executando somente indexação")
        index_rc = run_python("preCarregaGrafo.py", env)
        if index_rc != 0:
            print(f"[refresh] erro: preCarregaGrafo.py retornou {index_rc}")
            return index_rc
        print("[refresh] indexação concluída")
    else:
        print("[refresh] grafo e índice de código já estão atualizados")

    return 0


def run_loop() -> int:
    interval_hours = float(os.getenv("CODE_GRAPH_REFRESH_INTERVAL_HOURS", "12"))
    sleep_seconds = max(int(interval_hours * 3600), 60)

    while True:
        rc = run_refresh_once()
        if rc != 0:
            print(f"[refresh] ciclo terminou com erro ({rc}); novo ciclo em {sleep_seconds}s")
        else:
            print(f"[refresh] ciclo finalizado com sucesso; próximo ciclo em {sleep_seconds}s")
        time.sleep(sleep_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Orquestrador de sync/rebuild/index do grafo de código")
    parser.add_argument("--once", action="store_true", help="Executa um ciclo único")
    parser.add_argument("--loop", action="store_true", help="Executa em loop contínuo")
    args = parser.parse_args()

    if args.loop:
        return run_loop()
    return run_refresh_once()


if __name__ == "__main__":
    raise SystemExit(main())
