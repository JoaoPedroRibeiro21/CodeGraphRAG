"""Base interface for language-specific code parsers.

A LanguageParser is responsible for:
- initializing its tree-sitter grammar (or equivalent parser)
- listing the file extensions it handles
- extracting package/module, imports, types, fields and methods from AST nodes
- providing language-specific helpers for type resolution and call resolution

The generic `build_graph.py` orchestrator calls these methods to build a
multi-language code graph.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportInfo:
    exact: dict[str, str] = field(default_factory=dict)
    wildcard_packages: list[str] = field(default_factory=list)


@dataclass
class MethodInfo:
    id: str
    name: str
    signature: str
    params: list[tuple[str, str]]
    return_type: str
    class_fqn: str
    file_path: str
    node: Any
    line_start: int
    line_end: int
    repo_name: str
    source_url: str
    source_branch: str
    source_commit: str
    relative_file_path: str


@dataclass
class ClassInfo:
    id: str
    name: str
    fqn: str
    package: str
    file_path: str
    node: Any
    imports: ImportInfo
    repo_name: str
    source_url: str
    source_branch: str
    source_commit: str
    relative_file_path: str
    fields: dict[str, str] = field(default_factory=dict)
    methods: dict[str, list[MethodInfo]] = field(default_factory=dict)
    extends_name: str | None = None
    implements_names: list[str] = field(default_factory=list)
    extends_key: tuple[str, str] | None = None
    implements_keys: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ParsedFile:
    package: str
    imports: ImportInfo
    classes: list[ClassInfo]


class LanguageParser(ABC):
    """Abstract base class for language-specific parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Language name, e.g. 'java', 'python', 'typescript', 'go'."""

    @property
    @abstractmethod
    def extensions(self) -> set[str]:
        """File extensions handled by this parser, including the dot."""

    @abstractmethod
    def parse_file(self, source_code: str, repo_name: str, file_path: str, relative_file_path: str,
                   source_url: str, source_branch: str, source_commit: str) -> ParsedFile:
        """Parse source code and return extracted symbols."""

    @abstractmethod
    def find_invocations(self, method_node: Any) -> list[Any]:
        """Return all method/function call nodes inside a method body."""

    @abstractmethod
    def resolve_invocation(
        self,
        invocation_node: Any,
        class_info: ClassInfo,
        local_scope: dict[str, str],
        classes_by_key: dict[tuple[str, str], ClassInfo],
        classes_by_repo_simple: dict[tuple[str, str], list[tuple[str, str]]],
        classes_by_global_fqn: dict[str, list[tuple[str, str]]],
        classes_by_global_simple: dict[str, list[tuple[str, str]]],
        factory_patterns: list[str],
    ) -> tuple[str, str] | None:
        """Resolve the target class key of a method invocation, if possible."""

    @abstractmethod
    def resolve_method_candidates(
        self,
        target_class_key: tuple[str, str],
        method_name: str,
        arg_count: int | None,
        classes_by_key: dict[tuple[str, str], ClassInfo],
        arg_types: list[str | None] | None = None,
        visited: set[tuple[str, str]] | None = None,
    ) -> list[MethodInfo]:
        """Find candidate target methods for a call, including inheritance."""

    @abstractmethod
    def node_text(self, node: Any) -> str:
        """Return the text of an AST node."""

    @abstractmethod
    def compute_method_signature(self, name: str, params: list[tuple[str, str]]) -> str:
        """Compute a stable signature string for a method."""

    @abstractmethod
    def count_arguments(self, arguments_node: Any) -> int | None:
        """Count the number of arguments in a call expression."""

    @abstractmethod
    def infer_argument_types(self, arguments_node: Any, local_scope: dict[str, str] | None) -> list[str | None]:
        """Infer types of literal arguments in a call expression."""

    @abstractmethod
    def extract_variable_declarations(self, container_node: Any) -> dict[str, str]:
        """Extract local variable / parameter names and their simple types."""

    @abstractmethod
    def resolve_type(
        self,
        type_name: str,
        class_info: ClassInfo,
        classes_by_key: dict[tuple[str, str], ClassInfo],
        classes_by_repo_simple: dict[tuple[str, str], list[tuple[str, str]]],
        classes_by_global_fqn: dict[str, list[tuple[str, str]]],
        classes_by_global_simple: dict[str, list[tuple[str, str]]],
    ) -> tuple[str, str] | None:
        """Resolve a simple or qualified type name to a concrete class key."""
