# VRChat - Assistente Graph RAG do ERP VRMaster

O VRChat e um assistente interno para suporte, analistas e desenvolvedores consultarem regras de negocio, fluxos funcionais e detalhes tecnicos do ERP VRMaster.

O projeto combina base de conhecimento documental, analise de codigo Java, grafo de dependencias e uma pipeline de multiagentes para entregar respostas com contexto verificado e menor risco de alucinacao.

## Objetivo

O sistema foi criado para responder perguntas como:

- Como funciona determinada regra de negocio no ERP?
- Onde uma rotina e processada no codigo?
- Quais tabelas, colunas ou consultas SQL participam de um fluxo?
- Qual parametro ou configuracao influencia determinado comportamento?
- Por que uma mensagem de erro pode aparecer para o usuario?
- Como orientar o suporte sem expor detalhes tecnicos desnecessarios?
- Como ajudar novos desenvolvedores a entenderem o sistema legado?

## Visao Geral Da Arquitetura

```text
Usuario
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
  |       +--> ChromaDB de codigo
  |       +--> NetworkX code_graph.gpickle
  |       +--> Tree-sitter Java parser
  |
  +--> Pipeline multiagente de analise de codigo
  |       |
  |       +--> Agente analisador por batch
  |       +--> Agente consolidador
  |       +--> Agente verificador
  |
  v
LLM final com contexto documental + analise tecnica verificada
  |
  v
Resposta em linguagem funcional/tecnica conforme a pergunta
```

## Componentes Principais

| Arquivo | Responsabilidade |
|---|---|
| `app_chainlit.py` | Interface principal via Chainlit, autenticacao OAuth, recuperacao de contexto, streaming de resposta e suporte a imagens. |
| `question_classifier.py` | Classifica a pergunta com LLM antes da recuperacao para escolher a estrategia mais adequada. |
| `graph_retrieval.py` | Centraliza recuperacao de codigo, expansao por grafo, score de confianca e montagem dos `CodeNode`. |
| `build_graph.py` | Analisa o codigo Java com tree-sitter e gera o grafo NetworkX `code_graph.gpickle`. |
| `preCarregaGrafo.py` | Indexa os nos do grafo no ChromaDB de codigo. |
| `code_artifacts.py` | Extrai artefatos funcionais do codigo, como SQL, tabelas, mensagens, parametros e permissoes. |
| `code_analysis_pipeline.py` | Pipeline multiagente de analise, consolidacao e verificacao do contexto tecnico. |
| `preCarregaDataBase.py` | Indexa documentos funcionais em PDF/TXT no ChromaDB documental. |
| `loader.py` | Carrega PDFs e TXTs da base de conhecimento. |
| `vector_db.py` | Cria e carrega o banco vetorial documental. |
| `cleanup_db.py` | Remove historico antigo do Chainlit no PostgreSQL. |
| `init_db.py` | Inicializa e migra as tabelas usadas pelo Chainlit. |
| `entrypoint.sh` | Sequencia de inicializacao do container. |
| `docker-compose.yml` | Sobe Redis, PostgreSQL e aplicacao Chainlit. |

## Fontes De Conhecimento

| Fonte | Caminho | Uso |
|---|---|---|
| Documentos PDF | `files/BaseDeConhecimento_PDF` | Regras funcionais, procedimentos e material de suporte. |
| Documentos TXT | `files/BaseDeConhecimento_TXT` | Conhecimento textual complementar, geralmente mais granular. |
| Codigo Java VRMaster | `files/VRMaster` | Implementacao real do ERP, regras tecnicas, SQL, DAOs, services, controllers e telas. |
| Grafo de codigo | `code_graph.gpickle` ou `/app/code_graph_storage/code_graph.gpickle` | Relacoes estruturais e chamadas entre classes/metodos Java. |
| Chroma documental | `arquivos/chat_retrieval_db` | Embeddings da base documental. |
| Chroma de codigo | `chroma_graph_db` | Embeddings dos nos do grafo de codigo. |

## Fluxo De Uma Pergunta

1. O usuario envia uma pergunta pela interface Chainlit.
2. `question_classifier.py` classifica a pergunta, por exemplo como `funcional`, `erro`, `sql_dados`, `parametro`, `tela`, `tecnico` ou `geral`.
3. `app_chainlit.py` busca documentos relevantes no Chroma documental usando MMR.
4. `graph_retrieval.py` busca nos relevantes no Chroma de codigo, usando score vetorial quando disponivel.
5. Os nos recuperados sao expandidos pelo grafo NetworkX com filtros de relacao e confianca.
6. A recuperacao recebe score explicito considerando similaridade vetorial, profundidade, tipo de relacao, confianca da aresta e aderencia a categoria da pergunta.
7. `code_analysis_pipeline.py` analisa o codigo recuperado em batches, usando os metadados de confianca para evitar conclusoes fortes com evidencia fraca.
8. O agente consolidador junta os fatos confirmados dos batches.
9. O agente verificador aprova, rebaixa ou rejeita afirmacoes sem evidencia suficiente.
10. O prompt final recebe documentos, analise tecnica verificada, diagnostico da recuperacao, historico e pergunta atual.
11. O LLM final responde em streaming para o usuario.

## Multiagentes De Codigo

O projeto usa uma pipeline interna de agentes em `code_analysis_pipeline.py` antes da resposta final. Essa etapa existe para reduzir imprecisao tecnica e evitar que o modelo final use codigo fora de contexto.

| Agente | Funcao |
|---|---|
| Analisador por batch | Le partes do codigo recuperado e extrai fatos confirmados, regras, fluxo, SQL, evidencias e incertezas. |
| Consolidador | Une as analises dos batches, remove duplicidades e preserva incertezas. |
| Verificador | Confere se cada afirmacao da consolidacao esta sustentada pelas evidencias dos batches. |
| Agente final | Responde ao usuario combinando documentos, analise tecnica verificada e historico da conversa. |

## Estados Da Analise Tecnica

| Status | Significado |
|---|---|
| `approved` | O verificador aprovou a analise tecnica e ela pode ser usada na resposta final. |
| `failed` | A verificacao nao aprovou a analise; a resposta final deve tratar o codigo como incerto. |
| `revisar` ou `rejeitado` no verificador | O pipeline tenta reparar a analise conforme `CODE_VERIFICATION_REPAIR_ATTEMPTS`. |

## Grafo De Codigo

O grafo e gerado por `build_graph.py` usando `tree-sitter-java` para parsear o codigo Java do VRMaster.

O grafo e salvo em formato `pickle` como `code_graph.gpickle`.

### Tipos De Nos

| Tipo | Descricao |
|---|---|
| `class` | Classe Java identificada por package e nome qualificado. |
| `method` | Metodo Java identificado por classe, nome e tipos dos parametros. |

### Metadados Dos Nos

| Campo | Descricao |
|---|---|
| `type` | Tipo do no, como `class` ou `method`. |
| `name` | Nome legivel do simbolo. |
| `qualified_name` | Identificador qualificado usado no grafo. |
| `package` | Package Java. |
| `class_name` | Nome simples da classe. |
| `class_fqn` | Nome completo da classe para metodos. |
| `method_name` | Nome simples do metodo para nos de metodo. |
| `signature` | Assinatura simplificada do metodo. |
| `file_path` | Caminho do arquivo Java. |
| `code` | Trecho de codigo associado ao no. |
| `line_start` | Linha inicial no arquivo. |
| `line_end` | Linha final no arquivo. |
| `artifacts` | Artefatos funcionais extraidos do codigo, como SQL, tabelas, mensagens, parametros, permissoes e excecoes. |

### Tipos De Arestas

| Tipo | Descricao |
|---|---|
| `CONTAINS` | Classe contem metodo. |
| `CALLS` | Metodo chama outro metodo. |
| `IMPORTS` | Classe importa outra classe do projeto. |
| `EXTENDS` | Classe herda de outra classe. |
| `IMPLEMENTS` | Classe implementa interface. |

### Confianca Das Chamadas

As arestas `CALLS` possuem `confidence` para diferenciar chamadas resolvidas com maior ou menor seguranca.

| Confianca | Exemplo de origem |
|---|---|
| `high` | Chamada resolvida por tipo de campo, parametro, variavel local, `this`, `super` ou `VRInstance.criar(X.class)`. |
| `medium` | Chamada resolvida por contexto parcial, chamada estatica ou overload com ambiguidade controlada. |
| `low` | Chamada resolvida apenas por heuristica fraca, como nome de metodo globalmente unico. |

Na recuperacao padrao, chamadas `low` nao sao usadas para expandir contexto. Isso reduz falsos positivos em metodos comuns como `consultar`, `salvar`, `validar` e `getId`.

## Recuperacao Hibrida

O projeto usa duas estrategias em conjunto.

| Estrategia | Uso |
|---|---|
| Busca vetorial | Encontra documentos e nos de codigo semanticamente parecidos com a pergunta. |
| Expansao por grafo | Traz codigo conectado ao no recuperado, respeitando relacao e confianca. |

Em `graph_retrieval.py`, a expansao prioriza `CALLS` com confianca `high` ou `medium`, alem de relacoes estruturais como `CONTAINS`, `IMPORTS`, `EXTENDS` e `IMPLEMENTS` quando nao sao fracas.

Antes da recuperacao, `question_classifier.py` classifica a pergunta com LLM. Essa categoria ajusta a quantidade de nos buscados e aplica pequenos reforcos para artefatos relevantes. Por exemplo, perguntas `sql_dados` tendem a favorecer DAOs, SQL, tabelas e colunas; perguntas `erro` favorecem mensagens, validacoes e excecoes.

Cada `CodeNode` enviado ao pipeline multiagente inclui metadados de recuperacao:

| Campo | Uso |
|---|---|
| `retrieval_score` | Score normalizado da recuperacao do no. |
| `retrieval_confidence` | Confianca textual: `alta`, `media` ou `baixa`. |
| `question_category` | Categoria estimada para a pergunta. |
| `relation` | Relacao usada para incluir o no, como `seed`, `CALLS` ou `CONTAINS`. |
| `edge_confidence` | Confianca da aresta quando o no veio por expansao do grafo. |
| `source_reason` | Motivo tecnico da inclusao do no. |

## Suporte A Imagens

O Chainlit permite anexar imagens. Quando o usuario envia uma imagem, `app_chainlit.py` monta uma mensagem multimodal usando `HumanMessage` e envia o conteudo em base64 para o modelo configurado.

Esse recurso e util para prints de erro, telas do ERP e evidencias visuais enviadas pelo suporte.

## Persistencia E Historico

| Componente | Uso |
|---|---|
| PostgreSQL | Persistencia de threads, mensagens e historico do Chainlit. |
| Redis | Servico auxiliar configurado no compose. |
| `cleanup_db.py` | Limpeza de conversas com mais de 90 dias. |
| `init_db.py` | Criacao e migracao das tabelas do Chainlit. |

## Variaveis De Ambiente

Crie um arquivo `.env` local com as variaveis necessarias. Nao versione chaves reais.

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
```

### Variaveis Opcionais Da Pipeline De Codigo

| Variavel | Padrao | Descricao |
|---|---:|---|
| `CODE_BATCH_TOKEN_LIMIT` | `60000` | Limite de tokens por batch de codigo. |
| `CODE_NODE_CHUNK_TOKEN_LIMIT` | `12000` | Limite por chunk de um no de codigo. |
| `CODE_ANALYSIS_MAX_TOKENS` | `2500` | Saida maxima do agente analisador. |
| `CODE_CONSOLIDATION_MAX_TOKENS` | `5000` | Saida maxima do consolidador. |
| `CODE_VERIFICATION_MAX_TOKENS` | `3000` | Saida maxima do verificador. |
| `CODE_VERIFICATION_REPAIR_ATTEMPTS` | `1` | Tentativas de reparo quando o verificador reprova. |
| `QUESTION_CLASSIFIER_MODEL` | valor de `CHAT_MODEL` | Modelo usado para classificar a pergunta antes da recuperacao. |
| `QUESTION_CLASSIFIER_MAX_TOKENS` | `300` | Saida maxima do classificador de perguntas. |

## Preparacao Local

Instale dependencias em ambiente virtual:

```bash
python -m venv venv
./venv/bin/pip install -r requirements.txt
```

Garanta que a pasta do codigo Java exista em:

```text
files/VRMaster
```

Garanta que a gramatica Java do tree-sitter exista em:

```text
tree-sitter-java
```

Se necessario, clone manualmente:

```bash
git clone https://github.com/tree-sitter/tree-sitter-java.git
```

## Geracao Dos Indices

Execute os passos abaixo sempre que houver mudanca relevante em documentos, codigo Java ou estrutura do grafo.

### 1. Base Documental

```bash
./venv/bin/python preCarregaDataBase.py
```

Esse comando carrega PDFs e TXTs, divide em chunks e grava embeddings em `arquivos/chat_retrieval_db`.

### 2. Grafo De Codigo

```bash
./venv/bin/python build_graph.py
```

Esse comando parseia `files/VRMaster`, gera a symbol table e salva o grafo em `code_graph.gpickle` localmente ou em `/app/code_graph_storage/code_graph.gpickle` dentro do container.

### 3. Base Vetorial De Codigo

```bash
./venv/bin/python preCarregaGrafo.py
```

Esse comando indexa os nos do grafo em `chroma_graph_db`. Ele tambem remove IDs obsoletos do Chroma quando o grafo muda.

## Execucao Com Docker Compose

Suba os servicos:

```bash
docker compose up --build
```

A aplicacao Chainlit fica disponivel em:

```text
http://localhost:8000
```

O `entrypoint.sh` executa a sequencia de inicializacao:

```text
Verificar PostgreSQL
Executar init_db.py
Gerar grafo se estiver ausente
Indexar codigo se Chroma estiver ausente
Indexar documentos se Chroma documental estiver ausente
Executar limpeza de dados antigos
Iniciar Chainlit
```

## Execucao Local Sem Docker

Para rodar a interface Chainlit localmente:

```bash
./venv/bin/chainlit run app_chainlit.py --host 0.0.0.0 --port 8000
```

## Como Atualizar O Conhecimento

| Mudanca | Comando recomendado |
|---|---|
| Novo PDF ou TXT | `./venv/bin/python preCarregaDataBase.py` |
| Mudanca no codigo Java | `./venv/bin/python build_graph.py` e depois `./venv/bin/python preCarregaGrafo.py` |
| Mudanca no builder do grafo | `./venv/bin/python build_graph.py` e depois `./venv/bin/python preCarregaGrafo.py` |
| Mudanca nos prompts de multiagentes | Reiniciar aplicacao apos validar sintaxe. |
| Mudanca no prompt final | Reiniciar aplicacao apos validar comportamento. |

## Validacao Recomendada

Antes de subir alteracoes, valide sintaxe dos arquivos Python principais:

```bash
./venv/bin/python -m py_compile build_graph.py app_chainlit.py code_analysis_pipeline.py preCarregaGrafo.py preCarregaDataBase.py question_classifier.py graph_retrieval.py code_artifacts.py
```

Para rodar os testes unitarios:

```bash
./venv/bin/python -m pytest
```

Para iniciar uma base de avaliacao manual com perguntas reais, use o formato de exemplo em `eval/questions.example.json` e substitua por casos validados pelo suporte.

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

## Boas Praticas Para Desenvolvedores

- Nao versione `.env`, chaves de API ou dumps sensiveis.
- Reindexe o Chroma de codigo depois de qualquer mudanca que altere IDs do grafo.
- Prefira melhorar a precisao da recuperacao antes de alterar o prompt final.
- Preserve incertezas no pipeline de verificacao em vez de forcar uma resposta conclusiva.
- Evite usar chamadas de baixa confianca como evidencia definitiva.
- Teste perguntas reais do suporte antes de considerar uma mudanca aprovada.
- Documente mudancas de arquitetura neste README para facilitar onboarding.

## Limitacoes Conhecidas

- A resolucao de chamadas Java ainda e heuristica e nao substitui um compilador Java completo, classpath real ou analise de bytecode.
- Encadeamentos como `obj.getX().executar()` ainda podem perder o tipo intermediario quando o retorno de `getX()` nao e inferido com seguranca.
- Overloads sao filtrados principalmente por quantidade de argumentos; quando os tipos dos argumentos nao sao conhecidos, a chamada pode ficar parcialmente ambigua.
- Chamadas polimorficas por interface, heranca, classes abstratas e sobrescrita podem recuperar apenas parte dos destinos possiveis.
- Chamadas dinamicas, reflection, factories complexas e injecao indireta podem nao ser totalmente resolvidas.
- A expansao do grafo evita chamadas `low` por padrao para reduzir falsos positivos, mas isso tambem pode deixar fluxos reais fora do contexto.
- O verificador valida as evidencias recuperadas, mas nao consegue validar codigo que nao foi recuperado.
- Perguntas muito amplas podem recuperar contexto excessivo ou pouco especifico, principalmente quando combinam regra funcional, SQL e fluxo tecnico na mesma pergunta.
- Trechos muito grandes podem ser divididos em batches na pipeline de codigo, o que reduz a visao global de fluxos longos.
- A qualidade da resposta depende da atualizacao dos indices documental e de codigo: `arquivos/chat_retrieval_db`, `chroma_graph_db` e `code_graph.gpickle`.

## Estrategia De Evolucao

Prioridades recomendadas para proximas iteracoes, em ordem de impacto pratico:

### Alta Prioridade

- Classificar a pergunta antes da recuperacao para escolher uma estrategia mais precisa, como regra funcional, erro, SQL/tabela, parametro, tela, fluxo tecnico ou pergunta geral.
- Adicionar score explicito de confianca da recuperacao antes do pipeline multiagente, combinando similaridade vetorial, profundidade no grafo, tipo de relacao, confianca da aresta e quantidade de evidencias.
- Melhorar inferencia de tipos em encadeamentos como `obj.getX().executar()`, usando o tipo de retorno dos metodos ja mapeados na symbol table.
- Criar testes de regressao com perguntas reais do suporte, respostas esperadas e evidencias minimas esperadas no codigo/documentacao.

### Media Prioridade

- Extrair artefatos funcionais do codigo, como mensagens de erro, parametros, SQL, tabelas, colunas, permissoes, menus e telas.
- Enriquecer a indexacao do grafo em `preCarregaGrafo.py` para incluir metadados relevantes no texto indexado, nao apenas o codigo bruto do no.
- Ajustar a expansao do grafo conforme o tipo da pergunta, priorizando DAOs e SQL para perguntas de dados, telas/controllers para perguntas de interface e services para regras de negocio.
- Melhorar a representacao dos nos enviados ao `code_analysis_pipeline.py`, incluindo origem da recuperacao, score, relacao com o seed e confianca da aresta.

### Baixa Prioridade

- Criar um relatorio operacional de saude dos indices, mostrando data de geracao, quantidade de documentos, quantidade de nos, arestas e distribuicao de confianca das chamadas.
- Adicionar metricas de cobertura do grafo, como chamadas resolvidas, chamadas ambiguas, chamadas nao resolvidas e principais metodos com muitos falsos positivos.
- Separar a documentacao em arquivos menores caso o README cresca demais, mantendo no README apenas visao geral, execucao, manutencao e links para detalhes.

### Sugestoes De Implementacao

- Comecar com um classificador simples de perguntas em `app_chainlit.py`, mesmo que inicialmente baseado em palavras-chave e depois evoluido para LLM.
- Usar busca vetorial com score quando possivel para registrar a confianca inicial dos documentos e nos recuperados.
- Calcular uma confianca final da recuperacao antes de chamar a pipeline multiagente e registrar esse valor nos logs.
- Incluir metadados adicionais em `CodeNode`, como `retrieval_score`, `relation`, `edge_confidence` e `source_reason`.
- Indexar artefatos extraidos do codigo junto com os nos do grafo para melhorar perguntas sobre erros, tabelas, parametros e permissoes.

## Resumo Do Fluxo De Manutencao

```text
Alterou documentos?
  Rode preCarregaDataBase.py

Alterou codigo Java ou build_graph.py?
  Rode build_graph.py
  Rode preCarregaGrafo.py

Alterou app ou prompts?
  Rode py_compile
  Reinicie Chainlit

Respostas ficaram imprecisas?
  Verifique recuperacao do grafo
  Verifique confianca das arestas CALLS
  Verifique se o Chroma foi reindexado
```
