#!/usr/bin/env bash
# start.sh — inicializa o CodexGraph-RAG com Spring PetClinic na VPS
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

echo "CodexGraph-RAG — Spring PetClinic Portfolio"
echo "============================================"

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

# Verifica se a API key está presente e com valor não vazio
if ! grep -qE '^(OPENAI_API_KEY|CG_LLM__API_KEY)=[^[:space:]]' .env; then
    echo "ERRO: nenhuma API key configurada no .env."
    echo "Defina CG_LLM__API_KEY ou OPENAI_API_KEY com um valor válido."
    exit 1
fi

echo "Atualizando branch petclinic-poc..."
git fetch origin
git checkout petclinic-poc
git pull --ff-only origin petclinic-poc

echo "Criando diretórios de dados persistentes..."
mkdir -p ./chroma_graph_db
mkdir -p ./arquivos/chat_retrieval_db

echo "Subindo serviços com ${COMPOSE_CMD[*]}..."
"${COMPOSE_CMD[@]}" up --build -d

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
echo "Verifique os logs: ${COMPOSE_CMD[*]} logs -f codexgraph"
exit 1
