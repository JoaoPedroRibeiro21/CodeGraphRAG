"""Pluggable artifact extraction strategies.

This module replaces the previous monolithic hardcoded regexes with
language/domain-specific strategies driven by the configured profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


MAX_ARTIFACT_ITEMS = 40


def _unique_limited(values: Iterable[str], limit: int = MAX_ARTIFACT_ITEMS) -> list[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", (value or "").strip().strip('`"\''))
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        result.append(cleaned[:300])
        if len(result) >= limit:
            break
    return result


def _regex_flag_string(terms: Iterable[str]) -> str:
    """Return a regex-safe string of case-insensitive alternatives."""
    normalized = set()
    for term in terms:
        term = term.strip()
        if not term:
            continue
        normalized.add(re.escape(term))
    if not normalized:
        return "(?!.*)"  # never match
    return "|".join(sorted(normalized))


@dataclass
class _ArtifactStrategy:
    """Base artifact extraction strategy.

    Subclasses provide compiled regexes; the base class contains the
    shared deduplication pipeline used by all strategies.
    """

    name: str = "base"
    language: str = "*"

    sql_pattern: re.Pattern | None = None
    table_pattern: re.Pattern | None = None
    column_pattern: re.Pattern | None = None
    message_pattern: re.Pattern | None = None
    parameter_pattern: re.Pattern | None = None
    permission_pattern: re.Pattern | None = None
    exception_pattern: re.Pattern | None = None

    def extract(self, code: str) -> dict[str, list[str]]:
        code = code or ""

        tables: list[str] = []
        if self.table_pattern:
            for match in self.table_pattern.finditer(code):
                tables.append(match.group(1) or match.group(2) or "")

        columns: list[str] = []
        if self.column_pattern:
            for match in self.column_pattern.finditer(code):
                columns.append(match.group(1) or "")

        artifacts: dict[str, list[str]] = {
            "sql_fragments": _unique_limited(
                match.group(0) for match in (self.sql_pattern or re.compile("(?!.*)")).finditer(code)
            ),
            "tables": _unique_limited(tables),
            "columns": _unique_limited(columns),
            "messages": _unique_limited(
                match.group(1) for match in (self.message_pattern or re.compile("(?!.*)")).finditer(code)
            ),
            "parameters": _unique_limited(
                match.group(0) for match in (self.parameter_pattern or re.compile("(?!.*)")).finditer(code)
            ),
            "permissions": _unique_limited(
                match.group(0) for match in (self.permission_pattern or re.compile("(?!.*)")).finditer(code)
            ),
            "exceptions": _unique_limited(
                match.group(1) for match in (self.exception_pattern or re.compile("(?!.*)")).finditer(code)
            ),
        }
        return {key: value for key, value in artifacts.items() if value}


# Default Portuguese/ERP vocabulary preserved for backward compatibility.
_DEFAULT_PT_ERP_MESSAGES = [
    "erro",
    "falha",
    "invalid",
    "inválid",
    "obrigatorio",
    "obrigatório",
    "nao",
    "não",
    "sem permissao",
    "sem permissão",
    "atencao",
    "atenção",
]

_DEFAULT_PT_ERP_PARAMETERS = [
    "Parametro",
    "ParametroDAO",
    "Parametros",
    "Configuracao",
    "Configuração",
    "getParametro",
    "isParametro",
]

_DEFAULT_PT_ERP_PERMISSIONS = [
    "permissao",
    "permissão",
    "Permissao",
    "Permissão",
    "acesso",
    "autorizacao",
    "autorização",
]


class JavaArtifactStrategy(_ArtifactStrategy):
    """Java/JPA-oriented strategy with ERP Portuguese defaults.

    The message, parameter and permission patterns are built from the profile
    ``artifact_hints`` merged with a built-in Portuguese ERP fallback. When no
    profile is provided the legacy behavior is preserved.
    """

    def __init__(self, profile=None):
        super().__init__(name="java", language="java")

        hints = self._hints_from_profile(profile)

        message_terms = self._merge_hints(hints.get("messages"), _DEFAULT_PT_ERP_MESSAGES)
        parameter_terms = self._merge_hints(hints.get("parameters"), _DEFAULT_PT_ERP_PARAMETERS)
        permission_terms = self._merge_hints(hints.get("permissions"), _DEFAULT_PT_ERP_PERMISSIONS)

        self.sql_pattern = re.compile(
            r"\b(select|insert\s+into|update|delete\s+from|from|join)\s+[\w.\"`]+",
            re.IGNORECASE,
        )
        self.table_pattern = re.compile(
            r"(?:@Table\s*\([^)]*name\s*=\s*\"([^\"]+)\"|\b(?:from|join|update|into)\s+([\w.\"`]+))",
            re.IGNORECASE,
        )
        self.column_pattern = re.compile(
            r"@Column\s*\([^)]*name\s*=\s*\"([^\"]+)\"",
            re.IGNORECASE,
        )
        # Word boundaries prevent matching keywords inside identifiers such as
        # "VRException" while still capturing natural-language messages.
        self.message_pattern = re.compile(
            r"\"([^\"]*\b(?:" + _regex_flag_string(message_terms) + r")\b[^\"]*)\"",
            re.IGNORECASE,
        )
        self.parameter_pattern = re.compile(
            r"\b(?:" + _regex_flag_string(parameter_terms) + r")\b[\w.()\s,\"']{0,120}",
            re.IGNORECASE,
        )
        self.permission_pattern = re.compile(
            r"\b(?:" + _regex_flag_string(permission_terms) + r")\b[\w.()\s,\"']{0,120}",
            re.IGNORECASE,
        )
        self.exception_pattern = re.compile(
            r"\b(?:throw\s+new\s+|throws\s+)([A-Z]\w*(?:Exception|Error)?)"
        )

    @staticmethod
    def _hints_from_profile(profile) -> dict[str, list[str]]:
        """Return raw hint lists keyed by artifact type from the profile."""
        if profile is None or not hasattr(profile, "artifact_hints"):
            return {}
        hints = profile.artifact_hints
        return {
            "sql": list(getattr(hints, "sql", []) or []),
            "tables": list(getattr(hints, "tables", []) or []),
            "columns": list(getattr(hints, "columns", []) or []),
            "messages": list(getattr(hints, "messages", []) or []),
            "parameters": list(getattr(hints, "parameters", []) or []),
            "permissions": list(getattr(hints, "permissions", []) or []),
            "exceptions": list(getattr(hints, "exceptions", []) or []),
            "flow": list(getattr(hints, "flow", []) or []),
        }

    @staticmethod
    def _merge_hints(profile_hints: list[str] | None, defaults: list[str]) -> list[str]:
        """Merge profile hints with defaults, preserving the legacy vocabulary."""
        merged = set(defaults)
        if profile_hints:
            merged.update(profile_hints)
        return sorted(merged)

    @classmethod
    def from_profile(cls, profile) -> "JavaArtifactStrategy":
        """Factory method for symmetry with future strategy classes."""
        return cls(profile)


class GenericArtifactStrategy(_ArtifactStrategy):
    """Language-agnostic strategy using generic English patterns.

    Useful for codebases that are not Java or when no JPA annotations are
    expected.
    """

    def __init__(self):
        super().__init__(name="generic", language="*")
        self.sql_pattern = re.compile(
            r"\b(select|insert\s+into|update|delete\s+from|from|join)\s+[\w.\"`]+",
            re.IGNORECASE,
        )
        self.message_pattern = re.compile(
            r"\"([^\"]*(?:error|fail|invalid|required|not allowed|no permission|warning)[^\"]*)\"",
            re.IGNORECASE,
        )
        self.permission_pattern = re.compile(
            r"\b(?:permission|permissions|access|authorize|authentication|auth)\b[\w.()\s,\"']{0,120}",
            re.IGNORECASE,
        )
        self.exception_pattern = re.compile(
            r"\b(?:throw\s+new\s+|raises?\s+|throws\s+)([A-Z]\w*(?:Exception|Error)?)",
            re.IGNORECASE,
        )


def get_strategy(language: str, profile=None) -> _ArtifactStrategy:
    """Return the best artifact strategy for *language* and optional profile."""
    lang = (language or "java").lower()
    if lang in {"java"}:
        return JavaArtifactStrategy.from_profile(profile)
    return GenericArtifactStrategy()
