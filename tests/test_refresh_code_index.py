from datetime import datetime, timedelta, timezone

from refresh_code_index import collect_repo_commits, graph_is_stale


def test_collect_repo_commits_filters_status_and_missing_data():
    state = {
        "repositories": [
            {"configured_name": "core", "commit_sha": "abc", "status": "ok"},
            {"name": "pdv", "commit_sha": "def", "status": "ok"},
            {"name": "BrokenRepo", "status": "error"},
            {"name": "NoSha", "status": "ok"},
        ]
    }

    commits = collect_repo_commits(state)

    assert commits == {"core": "abc", "pdv": "def"}


def test_graph_is_stale_when_commits_change():
    stale, reason = graph_is_stale(
        graph_exists=True,
        graph_meta={"built_at": "2026-06-01T00:00:00+00:00", "repo_commits": {"core": "old"}},
        current_commits={"core": "new"},
        ttl_hours=336,
    )

    assert stale is True
    assert reason == "commits_alterados"


def test_graph_is_not_stale_with_same_commits_and_valid_ttl():
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    built_at = (now - timedelta(hours=1)).isoformat()
    stale, reason = graph_is_stale(
        graph_exists=True,
        graph_meta={"built_at": built_at, "repo_commits": {"core": "sha"}},
        current_commits={"core": "sha"},
        ttl_hours=336,
        now=now,
    )

    assert stale is False
    assert reason == "atualizado"


def test_graph_is_stale_when_ttl_expires():
    now = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)
    built_at = (now - timedelta(hours=400)).isoformat()
    stale, reason = graph_is_stale(
        graph_exists=True,
        graph_meta={"built_at": built_at, "repo_commits": {"core": "sha"}},
        current_commits={"core": "sha"},
        ttl_hours=336,
        now=now,
    )

    assert stale is True
    assert reason == "ttl_expirado"
