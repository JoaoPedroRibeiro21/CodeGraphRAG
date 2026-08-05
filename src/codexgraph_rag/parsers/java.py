"""Java language parser for CodexGraph-RAG.

Implements LanguageParser using tree-sitter-java.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from tree_sitter import Language, Parser

from codexgraph_rag.parsers.base import ClassInfo, ImportInfo, LanguageParser, MethodInfo, ParsedFile


@dataclass
class _JavaRuntime:
    language: Language
    parser: Parser


class JavaParser(LanguageParser):
    """Parse Java source files and resolve method calls."""

    def __init__(self, grammar_path: str | None = None, lib_path: str = "build/my-languages.so"):
        self._grammar_path = grammar_path or os.path.abspath("tree-sitter-java")
        self._lib_path = lib_path
        self._runtime = self._build_runtime()

    def _build_runtime(self) -> _JavaRuntime:
        if not os.path.exists(self._lib_path):
            os.makedirs(os.path.dirname(self._lib_path), exist_ok=True)
            if not os.path.exists(self._grammar_path):
                raise FileNotFoundError(
                    f"Java grammar not found at '{self._grammar_path}'. "
                    "Clone https://github.com/tree-sitter/tree-sitter-java.git"
                )
            Language.build_library(self._lib_path, [self._grammar_path])
        language = Language(self._lib_path, "java")
        parser = Parser()
        parser.set_language(language)
        parser.set_timeout_micros(30 * 1000 * 1000)
        return _JavaRuntime(language=language, parser=parser)

    @property
    def name(self) -> str:
        return "java"

    @property
    def extensions(self) -> set[str]:
        return {".java"}

    def node_text(self, node: Any) -> str:
        return node.text.decode("utf8", "ignore") if node else ""

    def _clean_type(self, type_text: str) -> str:
        type_text = re.sub(r"@\w+(?:\([^)]*\))?", "", type_text or "")
        type_text = re.sub(r"\b(extends|implements)\b", "", type_text)
        type_text = re.sub(r"\b(final|public|private|protected|static|volatile|transient)\b", "", type_text)
        type_text = re.sub(r"<.*>", "", type_text)
        type_text = type_text.replace("[]", "").strip()
        return type_text.split(".")[-1] if type_text else ""

    def _find_nodes_by_type(self, start_node: Any, target_type: str):
        nodes = []
        if not start_node:
            return nodes
        for child in start_node.children:
            if child.type == target_type:
                nodes.append(child)
            nodes.extend(self._find_nodes_by_type(child, target_type))
        return nodes

    def _extract_package(self, root_node: Any) -> str:
        for child in root_node.children:
            if child.type == "package_declaration":
                match = re.search(r"package\s+([\w.]+)\s*;", self.node_text(child))
                return match.group(1) if match else ""
        return ""

    def _extract_imports(self, root_node: Any) -> ImportInfo:
        imports = ImportInfo()
        for child in root_node.children:
            if child.type != "import_declaration":
                continue
            text = self.node_text(child)
            match = re.search(r"import\s+(?:static\s+)?([\w.]+)(\.\*)?\s*;", text)
            if not match:
                continue
            imported = match.group(1)
            if match.group(2):
                imports.wildcard_packages.append(imported)
            else:
                imports.exact[imported.split(".")[-1]] = imported
        return imports

    def _extract_type_name(self, node: Any) -> str:
        if not node:
            return ""
        type_node = node.child_by_field_name("type")
        if type_node:
            return self._clean_type(self.node_text(type_node))
        text = self.node_text(node)
        match = re.search(r"\b([\w.]+(?:\s*<[^;=,)]*>)?(?:\s*\[\])?)\s+\w+\s*(?:[=,;)])", text)
        return self._clean_type(match.group(1)) if match else ""

    def _extract_field_declarations(self, class_node: Any) -> dict[str, str]:
        body = class_node.child_by_field_name("body")
        fields_map: dict[str, str] = {}
        if not body:
            return fields_map
        for child in body.children:
            if child.type != "field_declaration":
                continue
            type_name = self._extract_type_name(child)
            if not type_name:
                continue
            for var_node in self._find_nodes_by_type(child, "variable_declarator"):
                name_node = var_node.child_by_field_name("name")
                if name_node:
                    fields_map[self.node_text(name_node)] = type_name
        return fields_map

    def _extract_params(self, method_node: Any) -> list[tuple[str, str]]:
        params = []
        parameters_node = method_node.child_by_field_name("parameters")
        if not parameters_node:
            return params
        for param_node in self._find_nodes_by_type(parameters_node, "formal_parameter"):
            name_node = param_node.child_by_field_name("name")
            type_name = self._extract_type_name(param_node)
            if name_node and type_name:
                params.append((self.node_text(name_node), type_name))
        return params

    def _extract_return_type(self, method_node: Any) -> str:
        type_node = method_node.child_by_field_name("type")
        return self._clean_type(self.node_text(type_node)) if type_node else "void"

    def compute_method_signature(self, name: str, params: list[tuple[str, str]]) -> str:
        return f"{name}({','.join(type_name for _, type_name in params)})"

    def _count_arguments(self, arguments_node: Any) -> int | None:
        if not arguments_node:
            return None
        text = self.node_text(arguments_node).strip()
        if text == "()":
            return 0
        depth = 0
        count = 1
        for char in text[1:-1]:
            if char in "(<[":
                depth += 1
            elif char in ")>]":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                count += 1
        return count

    def count_arguments(self, arguments_node: Any) -> int | None:
        return self._count_arguments(arguments_node)

    def _split_arguments(self, arguments_node: Any) -> list[str]:
        if not arguments_node:
            return []
        text = self.node_text(arguments_node).strip()
        if text == "()":
            return []
        args = []
        depth = 0
        current: list[str] = []
        for char in text[1:-1]:
            if char in "(<[":
                depth += 1
            elif char in ")>]":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
                continue
            current.append(char)
        if current or text != "()":
            args.append("".join(current).strip())
        return args

    def infer_argument_types(self, arguments_node: Any, local_scope: dict[str, str] | None) -> list[str | None]:
        local_scope = local_scope or {}
        inferred: list[str | None] = []
        for arg in self._split_arguments(arguments_node):
            if not arg or arg == "null":
                inferred.append(None)
            elif re.match(r'^".*"$', arg) or re.match(r"^'.*'$", arg):
                inferred.append("String" if arg.startswith('"') else "char")
            elif arg in {"true", "false"}:
                inferred.append("boolean")
            elif re.match(r"^-?\d+[lL]?$", arg):
                inferred.append("long" if arg.lower().endswith("l") else "int")
            elif re.match(r"^-?\d+\.\d+[fFdD]?$", arg):
                inferred.append("float" if arg.lower().endswith("f") else "double")
            elif match := re.match(r"new\s+([\w.]+)", arg):
                inferred.append(self._clean_type(match.group(1)))
            elif arg in local_scope:
                inferred.append(self._clean_type(local_scope[arg]))
            else:
                inferred.append(None)
        return inferred

    def extract_variable_declarations(self, container_node: Any) -> dict[str, str]:
        variables: dict[str, str] = {}
        for declaration in (
            self._find_nodes_by_type(container_node, "field_declaration")
            + self._find_nodes_by_type(container_node, "local_variable_declaration")
        ):
            type_name = self._extract_type_name(declaration)
            if not type_name:
                continue
            for var_node in self._find_nodes_by_type(declaration, "variable_declarator"):
                name_node = var_node.child_by_field_name("name")
                if name_node:
                    variables[self.node_text(name_node)] = type_name
        for parameter in self._find_nodes_by_type(container_node, "formal_parameter"):
            type_name = self._extract_type_name(parameter)
            name_node = parameter.child_by_field_name("name")
            if type_name and name_node:
                variables[self.node_text(name_node)] = type_name
        return variables

    def _to_node_id(self, repo_name: str, local_id: str) -> str:
        return f"{repo_name}::{local_id}"

    def parse_file(
        self,
        source_code: str,
        repo_name: str,
        file_path: str,
        relative_file_path: str,
        source_url: str,
        source_branch: str,
        source_commit: str,
    ) -> ParsedFile:
        tree = self._runtime.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node
        package_name = self._extract_package(root_node)
        imports = self._extract_imports(root_node)
        classes: list[ClassInfo] = []

        for class_node in self._find_nodes_by_type(root_node, "class_declaration"):
            class_name_node = class_node.child_by_field_name("name")
            if not class_name_node:
                continue
            class_name = self.node_text(class_name_node)
            class_fqn = f"{package_name}.{class_name}" if package_name else class_name
            class_id = self._to_node_id(repo_name, class_fqn)
            superclass_node = class_node.child_by_field_name("superclass")
            interfaces_node = class_node.child_by_field_name("interfaces")

            class_info = ClassInfo(
                id=class_id,
                name=class_name,
                fqn=class_fqn,
                package=package_name,
                file_path=file_path,
                node=class_node,
                imports=imports,
                repo_name=repo_name,
                source_url=source_url,
                source_branch=source_branch,
                source_commit=source_commit,
                relative_file_path=relative_file_path,
                fields=self._extract_field_declarations(class_node),
                extends_name=self._clean_type(self.node_text(superclass_node)) if superclass_node else None,
                implements_names=[
                    self._clean_type(self.node_text(n))
                    for n in self._find_nodes_by_type(interfaces_node, "type_identifier")
                ],
            )

            for method_node in self._find_nodes_by_type(class_node, "method_declaration"):
                name_node = method_node.child_by_field_name("name")
                if not name_node:
                    continue
                method_name = self.node_text(name_node)
                params = self._extract_params(method_node)
                signature = self.compute_method_signature(method_name, params)
                method_local_id = f"{class_fqn}#{signature}"
                method_id = self._to_node_id(repo_name, method_local_id)
                method_info = MethodInfo(
                    id=method_id,
                    name=method_name,
                    signature=signature,
                    params=params,
                    return_type=self._extract_return_type(method_node),
                    class_fqn=class_fqn,
                    file_path=file_path,
                    node=method_node,
                    line_start=method_node.start_point[0] + 1,
                    line_end=method_node.end_point[0] + 1,
                    repo_name=repo_name,
                    source_url=source_url,
                    source_branch=source_branch,
                    source_commit=source_commit,
                    relative_file_path=relative_file_path,
                )
                class_info.methods.setdefault(method_name, []).append(method_info)

            classes.append(class_info)

        return ParsedFile(package=package_name, imports=imports, classes=classes)

    def find_invocations(self, method_node: Any) -> list[Any]:
        return self._find_nodes_by_type(method_node, "method_invocation")

    def resolve_type(
        self,
        type_name: str,
        class_info: ClassInfo,
        classes_by_key: dict[tuple[str, str], ClassInfo],
        classes_by_repo_simple: dict[tuple[str, str], list[tuple[str, str]]],
        classes_by_global_fqn: dict[str, list[tuple[str, str]]],
        classes_by_global_simple: dict[str, list[tuple[str, str]]],
    ) -> tuple[str, str] | None:
        simple = self._clean_type(type_name)
        if not simple or simple in {"void", "boolean", "byte", "short", "int", "long", "float", "double", "char"}:
            return None

        same_repo_key = (class_info.repo_name, type_name)
        if same_repo_key in classes_by_key:
            return same_repo_key

        imported_fqn = class_info.imports.exact.get(simple)
        if imported_fqn and (class_info.repo_name, imported_fqn) in classes_by_key:
            return class_info.repo_name, imported_fqn

        same_package = f"{class_info.package}.{simple}" if class_info.package else simple
        if (class_info.repo_name, same_package) in classes_by_key:
            return class_info.repo_name, same_package

        for package_name in class_info.imports.wildcard_packages:
            wildcard_candidate = f"{package_name}.{simple}"
            if (class_info.repo_name, wildcard_candidate) in classes_by_key:
                return class_info.repo_name, wildcard_candidate

        same_repo_candidates = classes_by_repo_simple.get((class_info.repo_name, simple), [])
        if len(same_repo_candidates) == 1:
            return same_repo_candidates[0]

        global_fqn_candidates = classes_by_global_fqn.get(type_name, [])
        if len(global_fqn_candidates) == 1:
            return global_fqn_candidates[0]

        global_simple_candidates = classes_by_global_simple.get(simple, [])
        if len(global_simple_candidates) == 1:
            return global_simple_candidates[0]

        return None

    def _resolve_type(
        self,
        type_name: str,
        class_info: ClassInfo,
        classes_by_key: dict[tuple[str, str], ClassInfo],
        classes_by_repo_simple: dict[tuple[str, str], list[tuple[str, str]]],
        classes_by_global_fqn: dict[str, list[tuple[str, str]]],
        classes_by_global_simple: dict[str, list[tuple[str, str]]],
    ) -> tuple[str, str] | None:
        return self.resolve_type(
            type_name, class_info, classes_by_key, classes_by_repo_simple, classes_by_global_fqn, classes_by_global_simple
        )

    def _types_compatible(self, expected: str, actual: str | None) -> bool:
        if actual is None:
            return True
        expected = self._clean_type(expected)
        actual = self._clean_type(actual)
        primitive_boxes = {
            "int": "Integer",
            "long": "Long",
            "double": "Double",
            "float": "Float",
            "boolean": "Boolean",
            "char": "Character",
            "byte": "Byte",
            "short": "Short",
        }
        if expected == actual:
            return True
        if primitive_boxes.get(expected) == actual or primitive_boxes.get(actual) == expected:
            return True
        if expected in {"Object", "Number"}:
            return True
        return False

    def _filter_candidates_by_args(
        self,
        candidates: list[MethodInfo],
        arg_count: int | None,
        arg_types: list[str | None] | None,
    ) -> list[MethodInfo]:
        if arg_count is not None:
            arity_matches = [method for method in candidates if len(method.params) == arg_count]
            if arity_matches:
                candidates = arity_matches
        if arg_types:
            typed_matches = [
                method
                for method in candidates
                if len(method.params) == len(arg_types)
                and all(
                    self._types_compatible(param_type, arg_types[index])
                    for index, (_, param_type) in enumerate(method.params)
                )
            ]
            if typed_matches:
                candidates = typed_matches
        return candidates

    def resolve_method_candidates(
        self,
        target_class_key: tuple[str, str],
        method_name: str,
        arg_count: int | None,
        classes_by_key: dict[tuple[str, str], ClassInfo],
        arg_types: list[str | None] | None = None,
        visited: set[tuple[str, str]] | None = None,
    ) -> list[MethodInfo]:
        visited = visited or set()
        if target_class_key in visited:
            return []
        visited.add(target_class_key)

        class_info = classes_by_key.get(target_class_key)
        if not class_info:
            return []

        candidates = list(class_info.methods.get(method_name, []))
        candidates = self._filter_candidates_by_args(candidates, arg_count, arg_types)
        if candidates:
            return candidates

        inherited_candidates: list[MethodInfo] = []
        if class_info.extends_key:
            inherited_candidates.extend(
                self.resolve_method_candidates(
                    class_info.extends_key, method_name, arg_count, classes_by_key, arg_types, visited
                )
            )
        for interface_key in class_info.implements_keys:
            inherited_candidates.extend(
                self.resolve_method_candidates(
                    interface_key, method_name, arg_count, classes_by_key, arg_types, visited
                )
            )
        return inherited_candidates

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
        name_node = invocation_node.child_by_field_name("name")
        if not name_node:
            return None

        method_name = self.node_text(name_node)
        arguments_node = invocation_node.child_by_field_name("arguments")
        arg_count = self._count_arguments(arguments_node)
        arg_types = self.infer_argument_types(arguments_node, local_scope)
        object_node = invocation_node.child_by_field_name("object")
        object_text = self.node_text(object_node).strip()
        invocation_text = self.node_text(invocation_node)
        target_class_key: tuple[str, str] | None = None

        # Apply configured factory patterns (e.g. "MyFactory.create({class}).{method}").
        for pattern in factory_patterns:
            # Convert simple {class}/{method} placeholders to a regex.
            regex = (
                pattern.replace("{class}", r"(\w+)")
                .replace("{method}", re.escape(method_name))
                .replace(".", r"\.")
            )
            match = re.search(regex, invocation_text)
            if match:
                target_class_key = self._resolve_type(
                    match.group(1),
                    class_info,
                    classes_by_key,
                    classes_by_repo_simple,
                    classes_by_global_fqn,
                    classes_by_global_simple,
                )
                break

        if not target_class_key and object_text in {"this", ""}:
            target_class_key = (class_info.repo_name, class_info.fqn)
        elif not target_class_key and object_text == "super":
            target_class_key = class_info.extends_key
        elif not target_class_key and object_text in local_scope:
            target_class_key = self._resolve_type(
                local_scope[object_text],
                class_info,
                classes_by_key,
                classes_by_repo_simple,
                classes_by_global_fqn,
                classes_by_global_simple,
            )
        elif not target_class_key and object_node and object_node.type == "method_invocation":
            target_class_key = self.resolve_invocation(
                object_node,
                class_info,
                local_scope,
                classes_by_key,
                classes_by_repo_simple,
                classes_by_global_fqn,
                classes_by_global_simple,
                factory_patterns,
            )
        elif not target_class_key and object_text and re.match(r"^[A-Z]\w*$", object_text):
            target_class_key = self._resolve_type(
                object_text,
                class_info,
                classes_by_key,
                classes_by_repo_simple,
                classes_by_global_fqn,
                classes_by_global_simple,
            )

        if not target_class_key:
            return None

        return target_class_key
