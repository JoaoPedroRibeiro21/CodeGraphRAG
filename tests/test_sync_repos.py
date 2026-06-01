import json

from sync_repos import load_repo_targets, parse_repo_identity


def test_parse_repo_identity_from_https_url():
    org, repo = parse_repo_identity("https://github.com/vrsoftbr/VRMaster.git")

    assert org == "vrsoftbr"
    assert repo == "VRMaster"


def test_load_repo_targets_from_config(tmp_path):
    config_file = tmp_path / "repos.json"
    config_file.write_text(
        json.dumps(
            {
                "default_branch": "main",
                "repositories": [
                    {
                        "name": "VRMaster",
                        "url": "https://github.com/vrsoftbr/VRMaster.git",
                        "priority": "primary",
                    },
                    {
                        "url": "https://github.com/vrsoftbr/VRPdv.git",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    targets, payload = load_repo_targets(config_file)

    assert payload["default_branch"] == "main"
    assert len(targets) == 2
    assert targets[0].name == "VRMaster"
    assert targets[0].repo == "VRMaster"
    assert targets[1].name == "VRPdv"
    assert targets[1].priority == "secondary"
