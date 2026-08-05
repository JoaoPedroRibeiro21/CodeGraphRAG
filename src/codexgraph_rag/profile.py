"""Domain profile loader.

A domain profile is a YAML file that describes:
- product name and locale
- question categories and keywords
- domain cards (logical modules/repos)
- artifact extraction hints
- stopwords
- prompt templates
- language-specific factory patterns

Profiles allow the same Graph-RAG engine to target different domains
(ERP fiscal, SaaS, generic codebases) without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class QuestionCategory(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)
    multiplier: float = 1.0
    max_nodes: int | None = None
    min_score: float | None = None
    max_expansions: int | None = None
    max_depth: int | None = None
    artifact_defaults: list[str] = Field(default_factory=list)


class DomainCard(BaseModel):
    repo: str
    aliases: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)


class ArtifactHints(BaseModel):
    sql: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    flow: list[str] = Field(default_factory=list)


class PromptTemplates(BaseModel):
    system: str | None = None
    light: str | None = None
    classifier: str | None = None
    batch_analysis: str | None = None
    consolidation: str | None = None
    verification: str | None = None


class DomainProfile(BaseModel):
    product_name: str | None = None
    language: str = "pt-BR"
    categories: list[QuestionCategory] = Field(default_factory=list)
    domain_cards: list[DomainCard] = Field(default_factory=list)
    artifact_hints: ArtifactHints = Field(default_factory=ArtifactHints)
    stopwords: list[str] = Field(default_factory=list)
    deep_analysis_keywords: list[str] = Field(default_factory=list)
    explicit_deep_analysis_keywords: list[str] = Field(default_factory=list)
    factory_patterns: list[str] = Field(default_factory=list)
    prompts: PromptTemplates = Field(default_factory=PromptTemplates)
    i18n: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


def load_profile(path: str | Path) -> DomainProfile:
    """Load a domain profile from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return DomainProfile(**data)


def built_in_profile_path(name: str) -> Path:
    """Resolve a profile path relative to the package profiles directory."""
    package_dir = Path(__file__).parent
    return package_dir / "profiles" / f"{name}.yaml"
