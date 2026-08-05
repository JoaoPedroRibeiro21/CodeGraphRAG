"""Global settings loaded from config.yaml and the configured domain profile.

This module is a convenience bridge: legacy scripts at the repository root can
import ``config`` and ``profile`` from here without caring about file paths.
"""

from __future__ import annotations

import os
from pathlib import Path

from codexgraph_rag.config import Config, load_config
from codexgraph_rag.profile import DomainProfile, built_in_profile_path, load_profile


_CONFIG_PATH = Path(os.getenv("CG_CONFIG_PATH", "config.yaml"))


def _load_settings() -> tuple[Config, DomainProfile | None]:
    if _CONFIG_PATH.exists():
        cfg = load_config(_CONFIG_PATH)
    else:
        # Fall back to an empty default when no config file exists yet.
        cfg = Config()

    prof: DomainProfile | None = None
    if cfg.profile:
        profile_path = Path(cfg.profile)
        if not profile_path.exists():
            # Try built-in profile next to the package.
            builtin = built_in_profile_path(cfg.profile)
            if builtin.exists():
                profile_path = builtin
        try:
            prof = load_profile(profile_path)
        except FileNotFoundError:
            prof = None

    return cfg, prof


config, profile = _load_settings()


def reload_settings() -> None:
    """Reload config and profile from disk. Useful in tests or after wizard changes."""
    global config, profile
    config, profile = _load_settings()
