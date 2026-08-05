#!/usr/bin/env bash
# start.sh — inicializa o CodexGraph-RAG via Docker Compose
#
# Uso:
#   chmod +x start.sh
#   ./start.sh
#
# O script assume que o .env já foi criado com CG_LLM__API_KEY (ou OPENAI_API_KEY)
# e demais variáveis necessárias.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "CodexGraph-RAG"
echo "=============="

# Verifica dependências mínimas
if ! command -v docker &> /dev/null; then
    echo "ERRO: docker não está instalado."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERRO: daemon do docker não está acessível."
    echo "Inicie o serviço do docker (ex.: sudo systemctl start docker) e tente novamente."
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "ERRO: curl não está instalado."
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "ERRO: git não está instalado."
    exit 1
fi

# Detecta o comando correto do docker-compose (plugin moderno ou binário legado)
if docker compose version &> /dev/null; then
    COMPOSE_CMD=(docker compose)
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD=(docker-compose)
else
    echo "ERRO: docker-compose não está instalado."
    exit 1
fi

# Verifica .env
if [ ! -f .env ]; then
    echo "ERRO: arquivo .env não encontrado."
    echo "Copie .env.example para .env e preencha pelo menos CG_LLM__API_KEY (ou OPENAI_API_KEY)."
    exit 1
fi

# Extrai o valor de uma variável do .env, removendo export, aspas, espaços no
# final e ignorando linhas onde o comentário ocupa a própria linha.
# Retorna string vazia se a chave não existir (não falha sob set -o pipefail).
_env_value() {
    local key="$1"
    grep -E "^[[:space:]]*(export[[:space:]]+)?${key}=" .env 2> /dev/null | tail -n1 | sed -E \
        's/^[[:space:]]*(export[[:space:]]+)?'"${key}"'=[[:space:]]*//; s/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/; s/[[:space:]]+$//' || true
}

# Verifica se a API key está presente e com valor não vazio
CG_KEY="$(_env_value CG_LLM__API_KEY)"
OPENAI_KEY="$(_env_value OPENAI_API_KEY)"
if [ -z "${CG_KEY//[[:space:]]/}" ] && [ -z "${OPENAI_KEY//[[:space:]]/}" ]; then
    echo "ERRO: nenhuma API key configurada no .env."
    echo "Defina CG_LLM__API_KEY ou OPENAI_API_KEY com um valor válido."
    exit 1
fi

# Verifica se o arquivo compose existe
if [ ! -f docker-compose.yml ] && [ ! -f compose.yml ]; then
    echo "ERRO: nenhum arquivo de compose encontrado (docker-compose.yml ou compose.yml)."
    exit 1
fi

# Confirma que estamos dentro de um repositório git
if ! git rev-parse --is-inside-work-tree &> /dev/null; then
    echo "ERRO: o diretório atual não é um repositório git."
    exit 1
fi

# Verifica se a working tree está limpa antes de subir os serviços
if [ -n "$(git status --porcelain)" ]; then
    echo "AVISO: a working tree contém alterações não commitadas."
    echo "Commit, stash ou descarte as mudanças para garantir um deploy reproduzível."
fi

echo "Criando diretórios de dados persistentes..."
mkdir -p ./chroma_graph_db
mkdir -p ./arquivos/chat_retrieval_db

echo "Validando configuração do compose..."
"${COMPOSE_CMD[@]}" config -q

# Configurações de health check (podem ser sobrescritas via .env)
HEALTH_HOST="$(_env_value CHAINLIT_HOST)"
HEALTH_HOST="${HEALTH_HOST:-127.0.0.1}"
HEALTH_PORT="$(_env_value CHAINLIT_PORT)"
HEALTH_PORT="${HEALTH_PORT:-8000}"
HEALTH_SERVICE="$(_env_value COMPOSE_HEALTH_SERVICE)"
HEALTH_SERVICE="${HEALTH_SERVICE:-codexgraph}"

HEALTH_URL="http://${HEALTH_HOST}:${HEALTH_PORT}"

echo "Subindo serviços com ${COMPOSE_CMD[*]}..."
"${COMPOSE_CMD[@]}" up --build -d

echo ""
echo "Aguardando aplicação ficar saudável (${HEALTH_URL})..."
echo "Nota: na primeira inicialização o build do grafo pode levar vários minutos."

# 5 minutos de timeout para cold start; cada curl leva no máximo 5s
for i in {1..150}; do
    if curl -fsSL --max-time 5 "${HEALTH_URL}" &> /dev/null; then
        echo ""
        echo "CodexGraph-RAG está disponível em: ${HEALTH_URL}"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "ERRO: a aplicação não respondeu em ${HEALTH_URL} após 5 minutos."
echo "Verifique os logs: ${COMPOSE_CMD[*]} logs -f ${HEALTH_SERVICE}"
exit 1
