# Provedores de LLM e Embeddings

CodexGraph-RAG suporta múltiplos provedores via LangChain.

## OpenAI

```yaml
llm:
  provider: openai
  model: gpt-4o

embeddings:
  provider: openai
  model: text-embedding-3-small
```

Env: `OPENAI_API_KEY=sk-...`

## Anthropic

Anthropic não fornece embeddings. Use Anthropic para LLM e outro provider para embeddings.

```yaml
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022

embeddings:
  provider: openai
  model: text-embedding-3-small
```

Env: `ANTHROPIC_API_KEY=...`, `OPENAI_API_KEY=sk-...`

## Google / Gemini

```yaml
llm:
  provider: google
  model: gemini-1.5-pro

embeddings:
  provider: google
  model: models/text-embedding-004
```

Env: `GOOGLE_API_KEY=...`

## Ollama (local)

```yaml
llm:
  provider: ollama
  model: llama3.1
  base_url: http://localhost:11434

embeddings:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434
```

Não é necessário API key.

## Configuração via wizard

```bash
./venv/bin/python setup_config.py
```
