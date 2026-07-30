#!/bin/bash
# entrypoint.sh — CodexGraph-RAG

set -e

echo "Starting launch sequence..."
echo "DATABASE_URL is set."

APP_NAME="${APP_NAME:-codexgraph}"
CHAINLIT_HOST="${CHAINLIT_HOST:-0.0.0.0}"
CHAINLIT_PORT="${CHAINLIT_PORT:-8000}"

max_retries=30
count=0

echo "Checking if database is reachable at ${DATABASE_URL}..."

until python -c "
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
async def check():
    try:
        engine = create_async_engine(os.getenv('DATABASE_URL'))
        async with engine.begin() as conn:
            from sqlalchemy import text
            await conn.execute(text('SELECT 1'))
        return True
    except Exception as e:
        print(f'Connection attempt failed: {e}')
        return False
if not asyncio.run(check()):
    exit(1)
" ; do
  count=$((count + 1))
  if [ $count -ge $max_retries ]; then
    echo "Could not connect to database after $max_retries attempts. Proceeding anyway..."
    break
  fi
  echo "Database not ready yet... (attempt $count/$max_retries)"
  sleep 2
done

echo "Running database initialization (init_db.py)..."
python init_db.py || echo "Warning: init_db.py failed, but continuing..."

# RAG Generation Sequence
mkdir -p /app/code_graph_storage /app/repos_sources
echo "RAG: running code index refresh orchestrator (single cycle)..."
python refresh_code_index.py --once || { echo "ERROR: refresh_code_index.py failed. The graph could not be built."; exit 1; }

GRAPH_FILE="${CODE_GRAPH_PATH:-/app/code_graph_storage/code_graph.gpickle}"
if [ ! -s "$GRAPH_FILE" ]; then
  echo "ERROR: graph file not found or empty at $GRAPH_FILE after refresh."
  exit 1
fi
echo "RAG: graph ready at $GRAPH_FILE"

if [ "${CODE_GRAPH_BACKGROUND_REFRESH:-true}" = "true" ]; then
  echo "RAG: starting background refresh loop..."
  python refresh_code_index.py --loop &
fi

if [ ! -d "arquivos/chat_retrieval_db" ] || [ -z "$(ls -A arquivos/chat_retrieval_db 2>/dev/null)" ]; then
    echo "RAG: chat_retrieval_db missing or empty. Running preCarregaDataBase.py..."
    python preCarregaDataBase.py || echo "Warning: preCarregaDataBase.py failed."
fi

echo "Running data retention cleanup (cleanup_db.py)..."
python cleanup_db.py || echo "Warning: cleanup_db.py failed, but continuing..."

echo "Starting Chainlit ${APP_NAME} on ${CHAINLIT_HOST}:${CHAINLIT_PORT}..."
exec chainlit run app_chainlit.py --host "${CHAINLIT_HOST}" --port "${CHAINLIT_PORT}"
