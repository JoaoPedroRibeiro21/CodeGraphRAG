# CodexGraph-RAG

**Assistente Graph-RAG open source para bases de código.**

O CodexGraph-RAG combina documentação, grafo de dependências de código e LLMs para responder perguntas técnicas e funcionais sobre repositórios de software.

---

## O que ele faz

- Responde perguntas sobre regras de negócio, fluxos e comportamentos.
- Localiza onde rotinas são processadas no código.
- Identifica tabelas, colunas, consultas SQL e parâmetros envolvidos em fluxos.
- Analisa código multi-linguagem (Java implementado; Python, TypeScript e Go como stubs).
- Usa perfis de domínio configuráveis para adaptar a recuperação e os prompts.

---

## Arquitetura

```text
Usuário
  │
  ▼
Chainlit UI
  │
  ▼
app_chainlit.py
  │
  ├── Base documental (ChromaDB)
  │       └── PDFs/TXTs em files/documents/
  │
  ├── Code Graph RAG
  │       ├── ChromaDB de código
  │       ├── Grafo NetworkX (code_graph.gpickle)
  │       └── Language parser plugin (tree-sitter)
  │
  └── Pipeline multiagente de análise de código
          ├── Analisador
          ├── Consolidador
          └── Verificador
  │
  ▼
LLM final com contexto documental + análise técnica verificada
```

---

## Início rápido com Docker Compose

O jeito mais simples de rodar o projeto é com `./start.sh`, que sobe Redis, PostgreSQL e a aplicação em containers.

### 1. Clone e entre no diretório

```bash
git clone https://github.com/JoaoPedroRibeiro21/codexgraph-rag.git
cd codexgraph-rag
```

### 2. Configure as credenciais

```bash
cp .env.example .env
# Edite .env e preencha CG_LLM__API_KEY (ou OPENAI_API_KEY)
```

### 3. Configure os repositórios de código

```bash
cp repos.example.json repos.json
# Edite repos.json apontando para os repositórios que deseja indexar
```

### 4. Inicie tudo

```bash
./start.sh
```

O script valida o `.env`, cria os diretórios de dados, sobe os serviços e aguarda a aplicação responder em `http://localhost:8000`.

> Na primeira execução o build do grafo pode levar vários minutos.

---

## Execução local (sem Docker)

```bash
python -m venv venv
./venv/bin/pip install -e ".[all]"

# Sincronize e construa o grafo
./venv/bin/python sync_repos.py
./venv/bin/python build_graph.py
./venv/bin/python preCarregaGrafo.py

# (Opcional) Indexe documentos em files/documents/
./venv/bin/python preCarregaDataBase.py

# Rode a UI
./venv/bin/chainlit run app_chainlit.py --host 0.0.0.0 --port 8000
```

Acesse: http://localhost:8000

---

## Configuração

### Variáveis de ambiente (.env)

```bash
CG_LLM__PROVIDER=openai
CG_LLM__MODEL=gpt-4o
CG_LLM__API_KEY=sk-...

CG_EMBEDDINGS__PROVIDER=openai
CG_EMBEDDINGS__MODEL=text-embedding-3-small

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codexgraph
```

Outros providers suportados: `anthropic`, `google`, `ollama`.

### Perfis de domínio (`config.yaml`)

```yaml
profile: "profiles/generic.yaml"          # agnóstico
# profile: "profiles/petclinic.yaml"       # exemplo com Spring PetClinic
# profile: "profiles/erp-fiscal.example.yaml" # exemplo para ERP fiscal
```

Os perfis definem:
- Nome/idioma do produto.
- Categorias de pergunta e palavras-chave.
- Domain cards (módulos/repositórios lógicos).
- Hints de extração de artefatos (SQL, tabelas, mensagens, parâmetros, permissões, exceções).
- Templates de prompts.

---

## Estrutura do projeto

```text
.
├── app_chainlit.py            # UI e orquestração de respostas
├── sync_repos.py              # Sincroniza repositórios
├── build_graph.py             # Constrói o grafo de código
├── refresh_code_index.py      # Orquestrador de refresh periódico
├── preCarregaGrafo.py         # Popula índices de código
├── preCarregaDataBase.py      # Indexa documentos em files/documents/
├── loader.py                  # Carrega PDFs/TXTs
├── config.yaml                # Configuração central
├── repos.example.json         # Exemplo de configuração de repositórios
├── start.sh                   # Inicialização via Docker Compose
├── docker-compose.yml         # Serviços (Redis, PostgreSQL, app)
├── dockerfile                 # Imagem da aplicação
├── entrypoint.sh              # Entrypoint do container
├── profiles/                  # Perfis de domínio
├── docs/                      # Documentação
├── tests/                     # Testes automatizados
└── src/codexgraph_rag/        # Pacote Python em refatoração
```

---

## Testes

```bash
python -m pytest -q
```

---

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Áreas bem-vindas: novos perfis de domínio, parsers de linguagem, provedores de LLM/embedding, melhorias na documentação e traduções.

---

## Licença

Apache 2.0 — veja [LICENSE](LICENSE).
