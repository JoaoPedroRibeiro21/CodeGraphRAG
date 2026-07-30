#!/usr/bin/env bash
# start.sh — inicializa o CodexGraph-RAG com Spring PetClinic na VPS
#
# Uso:
#   chmod +x start.sh
#   ./start.sh
#
# O script assume que o .env já foi criado com OPENAI_API_KEY e outras variáveis.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "CodexGraph-RAG — Spring PetClinic Portfolio"
echo "============================================"

# Verifica dependências mínimas
if ! command -v docker &> /dev/null; then
    echo "ERRO: docker não está instalado."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERRO: docker-compose não está instalado."
    exit 1
fi

# Verifica .env
if [ ! -f .env ]; then
    echo "ERRO: arquivo .env não encontrado."
    echo "Copie .env.example para .env e preencha pelo menos OPENAI_API_KEY e CG_LLM__API_KEY."
    exit 1
fi

# Verifica se a API key da OpenAI está presente
if ! grep -qE "^(CG_)?(LLM__API_KEY|OPENAI_API_KEY)=" .env; then
    echo "AVISO: nenhuma API key da OpenAI detectada no .env."
fi

echo "Atualizando branch petclinic-poc..."
git fetch origin
git checkout petclinic-poc
git pull origin petclinic-poc

echo "Criando diretórios de dados persistentes..."
mkdir -p ./chroma_graph_db
mkdir -p ./arquivos/chat_retrieval_db

# Decide o comando correto do docker-compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "Subindo serviços com ${COMPOSE_CMD}..."
${COMPOSE_CMD} up --build -d

echo ""
echo "Aguardando aplicação ficar saudável (porta 8000)..."
for i in {1..60}; do
    if curl -fsS http://localhost:8000 &> /dev/null; then
        echo ""
        echo "CodexGraph-RAG está disponível em: http://localhost:8000"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "AVISO: a aplicação não respondeu na porta 8000 após 2 minutos."
echo "Verifique os logs: ${COMPOSE_CMD} logs -f codexgraph"
exit 1
