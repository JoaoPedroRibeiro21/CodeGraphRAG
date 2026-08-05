# Parsers de Linguagem

CodexGraph-RAG usa uma interface abstrata `LanguageParser` para suportar múltiplas linguagens via tree-sitter.

## Linguagens suportadas

| Linguagem | Status |
|-----------|--------|
| Java      | Implementado |
| Python    | Stub |
| TypeScript| Stub |
| Go        | Stub |

## Como funciona

O `build_graph.py` orquestrador lê `code_graph.code_languages` do `config.yaml`. Para cada arquivo, ele escolhe o parser pela extensão via `get_parser_for_file()` e chama:

- `parse_file()` — extrai classes, métodos, imports, campos.
- `resolve_invocation()` — resolve o alvo de chamadas de método.
- `resolve_method_candidates()` — encontra métodos candidatos, incluindo herança.

## Adicionar uma nova linguagem

1. Implemente `LanguageParser` em `src/codexgraph_rag/parsers/{lang}.py`.
2. Registre o parser em `src/codexgraph_rag/parsers/factory.py`.
3. Adicione a linguagem em `config.yaml`:

```yaml
code_graph:
  code_languages:
    - java
    - python
```

4. Adicione a gramática tree-sitter no `dockerfile` se for usar em container.

## Exemplo: parser Java

O parser Java (`src/codexgraph_rag/parsers/java.py`) implementa toda a interface e inclui:

- Compilação automática do `tree-sitter-java`.
- Extração de package, imports, classes, métodos, campos.
- Resolução de tipos por import, mesmo pacote, wildcard e herança.
- Inferência de tipos de argumentos literais.
- Aplicação de `factory_patterns` do profile.
