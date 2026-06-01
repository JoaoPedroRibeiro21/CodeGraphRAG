# VRChat - Assistente Graph RAG do ERP VRMaster

O VRChat é um assistente interno para suporte, analistas e desenvolvedores consultarem regras de negócio, fluxos funcionais e detalhes técnicos do ERP VRMaster.

O projeto combina base de conhecimento documental, análise de código Java, grafo de dependências e uma pipeline de multiagentes para entregar respostas com contexto verificado e menor risco de alucinação.

## Objetivo

O sistema foi criado para responder perguntas como:

- Como funciona determinada regra de negócio no ERP?
- Onde uma rotina é processada no código?
- Quais tabelas, colunas ou consultas SQL participam de um fluxo?
- Qual parâmetro ou configuração influencia determinado comportamento?
- Por que uma mensagem de erro pode aparecer para o usuário?
- Como orientar o suporte sem expor detalhes técnicos desnecessários?
- Como ajudar novos desenvolvedores a entenderem o sistema legado?

## Visão Geral Da Arquitetura

```text
Usuário
  |
  v
Chainlit UI
  |
  v
app_chainlit.py
  |
  +--> Base documental ChromaDB
  |       |
  |       +--> PDFs e TXTs de conhecimento funcional
  |
  +--> Code Graph RAG
  |       |
  |       +--> ChromaDB de código
  |       +--> NetworkX code_graph.gpickle
  |       +--> Tree-sitter Java parser
  |
  +--> Pipeline multiagente de análise de código
  |       |
  |       +--> Agente analisador por batch
  |       +--> Agente consolidador
  |       +--> Agente verificador
  |
  v
LLM final com contexto documental + análise técnica verificada
  |
  v
Resposta em linguagem funcional/técnica conforme a pergunta
```

## Componentes Principais

| Arquivo | Responsabilidade |
|---|---|
| `app_chainlit.py` | Interface principal via Chainlit, autenticação OAuth, recuperação de contexto, streaming de resposta e suporte a imagens. |
| `question_classifier.py` | Classifica a pergunta com LLM antes da recuperação para escolher a estratégia mais adequada. |
| `graph_retrieval.py` | Centraliza recuperação de código, expansão por grafo, score de confiança e montagem dos `CodeNode`. |
| `build_graph.py` | Analisa o código Java com tree-sitter e gera o grafo NetworkX `code_graph.gpickle`. |
| `preCarregaGrafo.py` | Indexa os nós do grafo no ChromaDB de código. |
| `refresh_code_index.py` | Orquestra sync/build/index com TTL, detecção de mudanças e agendamento em loop. |
| `code_artifacts.py` | Extrai artefatos funcionais do código, como SQL, tabelas, mensagens, parâmetros e permissões. |
| `code_analysis_pipeline.py` | Pipeline multiagente de análise, consolidação e verificação do contexto técnico. |
| `preCarregaDataBase.py` | Indexa documentos funcionais em PDF/TXT no ChromaDB documental. |
| `loader.py` | Carrega PDFs e TXTs da base de conhecimento. |
| `vector_db.py` | Cria e carrega o banco vetorial documental. |
| `cleanup_db.py` | Remove histórico antigo do Chainlit no PostgreSQL. |
| `init_db.py` | Inicializa e migra as tabelas usadas pelo Chainlit. |
| `entrypoint.sh` | Sequência de inicialização do container. |
| `docker-compose.yml` | Sobe Redis, PostgreSQL e aplicação Chainlit. |

## Fontes De Conhecimento

| Fonte | Caminho | Uso |
|---|---|---|
| Documentos PDF | `files/BaseDeConhecimento_PDF` | Regras funcionais, procedimentos e material de suporte. |
| Documentos TXT | `files/BaseDeConhecimento_TXT` | Conhecimento textual complementar, geralmente mais granular. |
| Código Java (multi-repo) | `repos.json` + `sync_repos.py` | Sincroniza os repositórios do ecossistema ERP para geração do grafo unificado. |
| Grafo de código | `code_graph.gpickle` ou `/app/code_graph_storage/code_graph.gpickle` | Relações estruturais e chamadas entre classes/métodos Java. |
| Chroma documental | `arquivos/chat_retrieval_db` | Embeddings da base documental. |
| Chroma de código | `chroma_graph_db` | Embeddings dos nós do grafo de código. |

## Fluxo De Uma Pergunta

1. O usuário envia uma pergunta pela interface Chainlit.
2. `question_classifier.py` classifica a pergunta, por exemplo como `funcional`, `erro`, `sql_dados`, `parametro`, `tela`, `tecnico` ou `geral`.
3. `app_chainlit.py` busca documentos relevantes no Chroma documental usando MMR.
4. `graph_retrieval.py` busca nós relevantes no Chroma de código, usando score vetorial quando disponível.
5. Os nós recuperados são expandidos pelo grafo NetworkX com filtros de relação e confiança.
6. A recuperação recebe score explícito considerando similaridade vetorial, profundidade, tipo de relação, confiança da aresta e aderência à categoria da pergunta.
7. `code_analysis_pipeline.py` analisa o código recuperado em batches, usando os metadados de confiança para evitar conclusões fortes com evidência fraca.
8. O agente consolidador junta os fatos confirmados dos batches.
9. O agente verificador aprova, rebaixa ou rejeita afirmações sem evidência suficiente.
10. O prompt final recebe documentos, análise técnica verificada, diagnóstico da recuperação, histórico e pergunta atual.
11. O LLM final responde em streaming para o usuário.

## Multiagentes De Código

O projeto usa uma pipeline interna de agentes em `code_analysis_pipeline.py` antes da resposta final. Essa etapa existe para reduzir imprecisão técnica e evitar que o modelo final use código fora de contexto.

| Agente | Função |
|---|---|
| Analisador por batch | Lê partes do código recuperado e extrai fatos confirmados, regras, fluxo, SQL, evidências e incertezas. |
| Consolidador | Une as análises dos batches, remove duplicidades e preserva incertezas. |
| Verificador | Confere se cada afirmação da consolidação está sustentada pelas evidências dos batches. |
| Agente final | Responde ao usuário combinando documentos, análise técnica verificada e histórico da conversa. |

## Estados Da Análise Técnica

| Status | Significado |
|---|---|
| `approved` | O verificador aprovou a análise técnica e ela pode ser usada na resposta final. |
| `failed` | A verificação não aprovou a análise; a resposta final deve tratar o código como incerto. |
| `revisar` ou `rejeitado` no verificador | O pipeline tenta reparar a análise conforme `CODE_VERIFICATION_REPAIR_ATTEMPTS`. |

## Grafo De Código

O grafo é gerado por `build_graph.py` usando `tree-sitter-java` para parsear o código Java dos repositórios sincronizados via `sync_repos.py`.

O grafo é salvo em formato `pickle` como `code_graph.gpickle`.

### Tipos De Nós

| Tipo | Descrição |
|---|---|
| `class` | Classe Java identificada por package e nome qualificado. |
| `method` | Método Java identificado por classe, nome e tipos dos parâmetros. |

### Metadados Dos Nós

| Campo | Descrição |
|---|---|
| `type` | Tipo do nó, como `class` ou `method`. |
| `name` | Nome legível do símbolo. |
| `qualified_name` | Identificador qualificado usado no grafo. |
| `package` | Package Java. |
| `class_name` | Nome simples da classe. |
| `class_fqn` | Nome completo da classe para métodos. |
| `method_name` | Nome simples do método para nós de método. |
| `signature` | Assinatura simplificada do método. |
| `file_path` | Caminho do arquivo Java. |
| `code` | Trecho de código associado ao nó. |
| `line_start` | Linha inicial no arquivo. |
| `line_end` | Linha final no arquivo. |
| `source_repo` | Nome do repositório de origem do nó. |
| `source_branch` | Branch sincronizada para o repositório. |
| `source_commit` | Commit exato usado para gerar o nó. |
| `relative_file_path` | Caminho relativo no repositório de origem. |
| `artifacts` | Artefatos funcionais extraídos do código, como SQL, tabelas, mensagens, parâmetros, permissões e exceções. |

### Tipos De Arestas

| Tipo | Descrição |
|---|---|
| `CONTAINS` | Classe contém método. |
| `CALLS` | Método chama outro método. |
| `IMPORTS` | Classe importa outra classe do projeto. |
| `EXTENDS` | Classe herda de outra classe. |
| `IMPLEMENTS` | Classe implementa interface. |

### Confiança Das Chamadas

As arestas `CALLS` possuem `confidence` para diferenciar chamadas resolvidas com maior ou menor segurança.

| Confiança | Exemplo de origem |
|---|---|
| `high` | Chamada resolvida por tipo de campo, parâmetro, variável local, `this`, `super` ou `VRInstance.criar(X.class)`. |
| `medium` | Chamada resolvida por contexto parcial, chamada estática ou overload com ambiguidade controlada. |
| `low` | Chamada resolvida apenas por heurística fraca, como nome de método globalmente único. |

Na recuperação padrão, chamadas `low` não são usadas para expandir contexto. Isso reduz falsos positivos em métodos comuns como `consultar`, `salvar`, `validar` e `getId`.

## Recuperação Híbrida

O projeto usa duas estratégias em conjunto.

| Estratégia | Uso |
|---|---|
| Busca vetorial | Encontra documentos e nós de código semanticamente parecidos com a pergunta. |
| Expansão por grafo | Traz código conectado ao nó recuperado, respeitando relação e confiança. |

Em `graph_retrieval.py`, a expansão prioriza `CALLS` com confiança `high` ou `medium`, além de relações estruturais como `CONTAINS`, `IMPORTS`, `EXTENDS` e `IMPLEMENTS` quando não são fracas.

Antes da recuperação, `question_classifier.py` classifica a pergunta com LLM. Essa categoria ajusta a quantidade de nós buscados e aplica pequenos reforços para artefatos relevantes. Por exemplo, perguntas `sql_dados` tendem a favorecer DAOs, SQL, tabelas e colunas; perguntas `erro` favorecem mensagens, validações e exceções.

Cada `CodeNode` enviado ao pipeline multiagente inclui metadados de recuperação:

| Campo | Uso |
|---|---|
| `retrieval_score` | Score normalizado da recuperação do nó. |
| `retrieval_confidence` | Confiança textual: `alta`, `media` ou `baixa`. |
| `question_category` | Categoria estimada para a pergunta. |
| `relation` | Relação usada para incluir o nó, como `seed`, `CALLS` ou `CONTAINS`. |
| `edge_confidence` | Confiança da aresta quando o nó veio por expansão do grafo. |
| `source_reason` | Motivo técnico da inclusão do nó. |

## Suporte A Imagens

O Chainlit permite anexar imagens. Quando o usuário envia uma imagem, `app_chainlit.py` monta uma mensagem multimodal usando `HumanMessage` e envia o conteúdo em base64 para o modelo configurado.

Esse recurso é útil para prints de erro, telas do ERP e evidências visuais enviadas pelo suporte.

## Persistência E Histórico

| Componente | Uso |
|---|---|
| PostgreSQL | Persistência de threads, mensagens e histórico do Chainlit. |
| Redis | Serviço auxiliar configurado no compose. |
| `cleanup_db.py` | Limpeza de conversas com mais de 90 dias. |
| `init_db.py` | Criação e migração das tabelas do Chainlit. |

## Variáveis De Ambiente

Crie um arquivo `.env` local com as variáveis necessárias. Não versione chaves reais.

```env
OPENAI_API_KEY=...
DATABASE_URL=postgresql+asyncpg://vrchat:vrchat@postgres:5432/vrchat
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
CHAINLIT_AUTH_SECRET=...
CHAT_MODEL=gpt-4.1-2025-04-14
QUESTION_CLASSIFIER_MODEL=gpt-4.1-2025-04-14
CODE_ANALYSIS_MODEL=gpt-5.1-codex
CODE_RETRIEVER_K=6
CODE_GRAPH_PATH=./code_graph.gpickle
GITHUB_TOKEN=...
REPO_CONFIG_FILE=./repos.json
REPO_BASE_DIR=./repos_sources
REPO_STATE_FILE=./repos_sources/repos_state.json
CODE_GRAPH_REBUILD_TTL_HOURS=336
CODE_GRAPH_REFRESH_INTERVAL_HOURS=12
CODE_GRAPH_BACKGROUND_REFRESH=true
```

### Variáveis Opcionais Da Pipeline De Código

| Variável | Padrão | Descrição |
|---|---:|---|
| `CODE_BATCH_TOKEN_LIMIT` | `60000` | Limite de tokens por batch de código. |
| `CODE_NODE_CHUNK_TOKEN_LIMIT` | `12000` | Limite por chunk de um nó de código. |
| `CODE_ANALYSIS_MAX_TOKENS` | `2500` | Saída máxima do agente analisador. |
| `CODE_CONSOLIDATION_MAX_TOKENS` | `5000` | Saída máxima do consolidador. |
| `CODE_VERIFICATION_MAX_TOKENS` | `3000` | Saída máxima do verificador. |
| `CODE_VERIFICATION_REPAIR_ATTEMPTS` | `1` | Tentativas de reparo quando o verificador reprova. |
| `QUESTION_CLASSIFIER_MODEL` | valor de `CHAT_MODEL` | Modelo usado para classificar a pergunta antes da recuperação. |
| `QUESTION_CLASSIFIER_MAX_TOKENS` | `300` | Saída máxima do classificador de perguntas. |

## Preparação Local

Instale dependências em ambiente virtual:

```bash
python -m venv venv
./venv/bin/pip install -r requirements.txt
```

Garanta que o arquivo `repos.json` exista com os repositórios de código Java:

```text
repos.json
```

Sincronize os repositórios do GitHub:

```bash
./venv/bin/python sync_repos.py
```

Garanta que a gramática Java do tree-sitter exista em:

```text
tree-sitter-java
```

Se necessário, clone manualmente:

```bash
git clone https://github.com/tree-sitter/tree-sitter-java.git
```

## Geração Dos Índices

Execute os passos abaixo sempre que houver mudança relevante em documentos, código Java ou estrutura do grafo.

### 1. Base Documental

```bash
./venv/bin/python preCarregaDataBase.py
```

Esse comando carrega PDFs e TXTs, divide em chunks e grava embeddings em `arquivos/chat_retrieval_db`.

### 2. Sincronização De Repositórios De Código

```bash
./venv/bin/python sync_repos.py
```

Esse comando sincroniza os repositórios definidos em `repos.json` e grava o estado em `REPO_STATE_FILE`.

### 3. Atualização Orquestrada (Recomendado)

```bash
./venv/bin/python refresh_code_index.py --once
```

Esse comando executa o fluxo completo com regras automáticas:

- roda `sync_repos.py`
- compara commits atuais com a última build registrada
- dispara rebuild/index quando houver mudança de commit, expiração de TTL ou ausência de artefatos
- pula rebuild quando nada mudou

### 4. Grafo De Código

```bash
./venv/bin/python build_graph.py
```

Esse comando parseia os repositórios sincronizados, gera a symbol table e salva o grafo em `code_graph.gpickle` localmente ou em `/app/code_graph_storage/code_graph.gpickle` dentro do container.

### 5. Base Vetorial De Código

```bash
./venv/bin/python preCarregaGrafo.py
```

Esse comando indexa os nós do grafo em `chroma_graph_db`. Ele também remove IDs obsoletos do Chroma quando o grafo muda.

## Execução Com Docker Compose

Suba os serviços:

```bash
docker compose up --build
```

A aplicação Chainlit fica disponível em:

```text
http://localhost:8000
```

O `entrypoint.sh` executa a sequência de inicialização:

```text
Verificar PostgreSQL
Executar init_db.py
Executar refresh_code_index.py --once
Iniciar loop opcional de refresh em background
Indexar documentos se Chroma documental estiver ausente
Executar limpeza de dados antigos
Iniciar Chainlit
```

## Execução Local Sem Docker

Para rodar a interface Chainlit localmente:

```bash
./venv/bin/chainlit run app_chainlit.py --host 0.0.0.0 --port 8000
```

## Como Atualizar O Conhecimento

| Mudança | Comando recomendado |
|---|---|
| Novo PDF ou TXT | `./venv/bin/python preCarregaDataBase.py` |
| Mudança nos repositórios de código | `./venv/bin/python refresh_code_index.py --once` |
| Mudança no builder do grafo | `./venv/bin/python build_graph.py` e depois `./venv/bin/python preCarregaGrafo.py` |
| Mudança nos prompts de multiagentes | Reiniciar aplicação após validar sintaxe. |
| Mudança no prompt final | Reiniciar aplicação após validar comportamento. |

## Validação Recomendada

Antes de subir alterações, valide sintaxe dos arquivos Python principais:

```bash
./venv/bin/python -m py_compile build_graph.py app_chainlit.py code_analysis_pipeline.py preCarregaGrafo.py preCarregaDataBase.py question_classifier.py graph_retrieval.py code_artifacts.py
```

Para rodar os testes unitários:

```bash
./venv/bin/python -m pytest
```

Para iniciar uma base de avaliação manual com perguntas reais, use o formato de exemplo em `eval/questions.example.json` e substitua por casos validados pelo suporte.

Para inspecionar o grafo gerado:

```bash
./venv/bin/python - <<'PY'
import pickle

with open('code_graph.gpickle', 'rb') as f:
    graph = pickle.load(f)

edge_counts = {}
call_confidence = {}

for _, _, data in graph.edges(data=True):
    edge_type = data.get('type')
    edge_counts[edge_type] = edge_counts.get(edge_type, 0) + 1
    if edge_type == 'CALLS':
        confidence = data.get('confidence')
        call_confidence[confidence] = call_confidence.get(confidence, 0) + 1

print('nodes:', graph.number_of_nodes())
print('edges:', graph.number_of_edges())
print('edge types:', edge_counts)
print('call confidence:', call_confidence)
PY
```

## Boas Práticas Para Desenvolvedores

- Não versione `.env`, chaves de API ou dumps sensíveis.
- Reindexe o Chroma de código depois de qualquer mudança que altere IDs do grafo.
- Prefira melhorar a precisão da recuperação antes de alterar o prompt final.
- Preserve incertezas no pipeline de verificação em vez de forçar uma resposta conclusiva.
- Evite usar chamadas de baixa confiança como evidência definitiva.
- Teste perguntas reais do suporte antes de considerar uma mudança aprovada.
- Documente mudanças de arquitetura neste README para facilitar onboarding.

## Resumo Do Fluxo De Manutenção

```text
Alterou documentos?
  Rode preCarregaDataBase.py

Alterou código Java ou build_graph.py?
  Rode build_graph.py
  Rode preCarregaGrafo.py

Alterou app ou prompts?
  Rode py_compile
  Reinicie Chainlit

Respostas ficaram imprecisas?
  Verifique recuperação do grafo
  Verifique confiança das arestas CALLS
  Verifique se o Chroma foi reindexado
```
