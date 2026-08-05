# Perfis de Domínio

Perfis YAML em `profiles/` descrevem o domínio de aplicação do CodexGraph-RAG.

## Estrutura

```yaml
product_name: "MeuProduto"
language: "pt-BR"

categories:
  - name: funcional
    keywords: [regra, processo, fluxo]
    multiplier: 1.0
    max_nodes: 24
    min_score: 0.35
    max_expansions: 12
    max_depth: 2
    artifact_defaults: []

domain_cards:
  - repo: core
    aliases: [core, erp, parametros]
    responsibilities: [regras centrais]

artifact_hints:
  sql: [tabela, coluna, query]
  messages: [erro, falha, mensagem]
  parameters: [parametro, configuracao]
  permissions: [permissao, acesso]

stopwords: [como, quando, qual]

deep_analysis_keywords: [tecnico, codigo, classe]
explicit_deep_analysis_keywords: [tecnico, codigo, classe]

factory_patterns:
  - "MyFactory\\.create\\({class}\\.class\\)\\.{method}"

prompts:
  system: "..."
  light: "..."
  classifier: "..."
  batch_analysis: "..."
  consolidation: "..."
  verification: "..."

i18n:
  tables: "Tabelas confirmadas"
  columns: "Colunas confirmadas"
```

## Profiles de exemplo

- `profiles/generic.yaml` — domínio agnóstico.
- `profiles/erp-fiscal.example.yaml` — exemplo fiscal genérico.
- `profiles/empty.yaml` — mínimo, em inglês.

## Factory patterns

Padrões de factory/injeção específicos do domínio são regex com placeholders `{class}` e `{method}`.
