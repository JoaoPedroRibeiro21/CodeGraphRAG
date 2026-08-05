"""Factory for language-specific parsers.

Registers built-in parsers and resolves them by name or file extension.
"""

from __future__ import annotations

from pathlib import Path
from typing import Type

from codexgraph_rag.parsers.base import LanguageParser
from codexgraph_rag.parsers.java import JavaParser


# Stub parsers for future implementation. They raise NotImplementedError on use.
class _StubParser(LanguageParser):
    def __init__(self, language: str, extensions: set[str]):
        self._language = language
        self._extensions = extensions

    @property
    def name(self) -> str:
        return self._language

    @property
    def extensions(self) -> set[str]:
        return self._extensions

    def parse_file(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def find_invocations(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def resolve_invocation(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def resolve_method_candidates(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def node_text(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def compute_method_signature(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def count_arguments(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def infer_argument_types(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def extract_variable_declarations(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")

    def resolve_type(self, *args, **kwargs):
        raise NotImplementedError(f"Parser for {self._language} is not implemented yet.")


_PARSER_CLASSES: dict[str, Type[LanguageParser]] = {
    "java": JavaParser,
    "python": lambda: _StubParser("python", {".py"}),
    "typescript": lambda: _StubParser("typescript", {".ts", ".tsx"}),
    "go": lambda: _StubParser("go", {".go"}),
}


def list_parsers() -> list[str]:
    """Return all registered parser names."""
    return list(_PARSER_CLASSES.keys())


def get_parser(name: str) -> LanguageParser:
    """Instantiate a parser by language name."""
    name = name.lower().strip()
    if name not in _PARSER_CLASSES:
        raise ValueError(f"Unknown parser: {name}. Available: {list_parsers()}")
    cls = _PARSER_CLASSES[name]
    return cls() if callable(cls) else cls


def get_parser_for_file(path: str | Path, languages: list[str] | None = None) -> LanguageParser | None:
    """Pick the first parser that handles the file extension.

    If languages is provided, restrict the search to those parsers.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    allowed = {l.lower().strip() for l in (languages or list_parsers())}
    for name in allowed:
        parser = get_parser(name)
        if suffix in parser.extensions:
            return parser
    return None


def register_parser(name: str, cls: Type[LanguageParser]) -> None:
    """Register a new parser implementation at runtime."""
    _PARSER_CLASSES[name.lower().strip()] = cls
