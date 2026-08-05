"""Central configuration for CodexGraph-RAG.

Loads `config.yaml` and environment variables. Environment variables take
precedence over file values when the same key is defined.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_CONFIG_PATH = Path("config.yaml")


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    extra_headers: dict[str, str] | None = None
    timeout: float | None = None


class EmbeddingConfig(BaseModel):
    provider: str = "openai"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    chunk_size: int | None = None
    extra_headers: dict[str, str] | None = None


class RepoDefaults(BaseModel):
    default_branch: str = "main"
    sync_ttl_hours: int = 336
    base_dir: str = "./repos_sources"
    state_file: str = "./repos_sources/repos_state.json"


class CodeGraphConfig(BaseModel):
    code_languages: list[str] = Field(default_factory=lambda: ["java"])
    graph_path: str = "./code_graph.gpickle"
    container_graph_path: str = "/app/code_graph_storage/code_graph.gpickle"
    chroma_path: str = "./chroma_graph_db"
    container_chroma_path: str = None
    rebuild_ttl_hours: int = 336
    refresh_interval_hours: int = 12
    background_refresh: bool = True
    index_schema_version: str = "code_graph_v3_multirepo"


class RetrievalConfig(BaseModel):
    code_k: int = 6
    doc_k: int = 4
    max_final_nodes: int = 24
    max_expansions: int = 12
    max_depth: int = 2
    min_score: float = 0.35
    profile_path: str | None = None


class ChainlitConfig(BaseModel):
    name: str = "CodexGraph"
    port: int = 8000
    host: str = "0.0.0.0"
    auth_secret: str | None = None


class AuthConfig(BaseModel):
    provider: Literal["none", "password", "google"] = "none"
    # OAuth Google
    google_client_id: str | None = None
    google_client_secret: str | None = None


class BenchConfig(BaseModel):
    enabled: bool = False
    api_token: str | None = None


class Config(BaseModel):
    product_name: str = "CodexGraph"
    language: str = "pt-BR"
    profile: str | None = None
    llm: LLMConfig = Field(default_factory=LLMConfig)
    classifier: LLMConfig = Field(default_factory=LLMConfig)
    code_analysis: LLMConfig = Field(default_factory=LLMConfig)
    code_verification: LLMConfig = Field(default_factory=LLMConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    code_graph: CodeGraphConfig = Field(default_factory=CodeGraphConfig)
    repos: RepoDefaults = Field(default_factory=RepoDefaults)
    chainlit: ChainlitConfig = Field(default_factory=ChainlitConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    bench: BenchConfig = Field(default_factory=BenchConfig)

    @field_validator("product_name", "language", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v


def _env_prefix_key(prefix: str, key: str) -> str:
    """Build an env-var key.

    The first level uses a single underscore (e.g. CG_REPOS) and deeper levels
    use a double underscore (e.g. CG_REPOS__STATE_FILE).
    """
    key = key.upper()
    if not prefix:
        return key
    prefix = prefix.upper()
    return f"{prefix}__{key}" if "_" in prefix else f"{prefix}_{key}"


def _apply_env_overrides(model: BaseModel, prefix: str = "") -> None:
    """Recursively fill None-ish or scalar fields from env vars.

    Nested keys follow the convention CG_SECTION__FIELD, e.g. CG_REPOS__STATE_FILE.
    """
    fields = type(model).model_fields
    for name, field_info in fields.items():
        value = getattr(model, name)
        env_key = _env_prefix_key(prefix, name)
        env_value = os.getenv(env_key)

        if env_value is not None:
            field_type = field_info.annotation
            if field_type is bool or (isinstance(field_type, type) and issubclass(field_type, bool)):
                setattr(model, name, env_value.lower() in ("true", "1", "yes"))
            elif field_type is int or (isinstance(field_type, type) and issubclass(field_type, int)):
                try:
                    setattr(model, name, int(env_value))
                except ValueError:
                    pass
            elif field_type is float or (isinstance(field_type, type) and issubclass(field_type, float)):
                try:
                    setattr(model, name, float(env_value))
                except ValueError:
                    pass
            else:
                setattr(model, name, env_value)
            continue

        if isinstance(value, BaseModel):
            _apply_env_overrides(value, env_key)
        elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
            for i, item in enumerate(value):
                _apply_env_overrides(item, f"{env_key}__{i}")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH, env_prefix: str = "CG") -> Config:
    """Load configuration from YAML and environment overrides.

    Args:
        path: path to the YAML config file.
        env_prefix: prefix used when looking for environment overrides.
    """
    path = Path(path)
    data: dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    config = Config(**data)

    # Environment variables take precedence.
    # Example: CG_PRODUCT_NAME, CG_LLM__MODEL, CG_RETRIEVAL__CODE_K
    _apply_env_overrides(config, env_prefix)

    # Propagate common defaults if not set.
    if config.classifier.provider == "openai" and config.classifier.model is None:
        config.classifier.model = "gpt-4o-mini"
    if config.code_analysis.provider == "openai" and config.code_analysis.model is None:
        config.code_analysis.model = "gpt-4o"
    if config.code_verification.provider == "openai" and config.code_verification.model is None:
        config.code_verification.model = "gpt-4o"
    if config.embeddings.provider == "openai" and config.embeddings.model is None:
        config.embeddings.model = "text-embedding-3-small"

    return config


def save_config_example(path: str | Path = "config.example.yaml") -> None:
    """Write an example configuration file."""
    example = Config()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(example.model_dump(exclude_none=True), f, sort_keys=False, allow_unicode=True)
