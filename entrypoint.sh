#!/bin/bash
# entrypoint.sh

echo "Starting launch sequence..."

# Show environment for debugging (safely)
echo "DATABASE_URL is set."

max_retries=30
count=0

echo "Checking if database is reachable at ${DATABASE_URL}..."

# Use a simpler python check that prints errors
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
python -c "import os,sys; prefix='version https://git-lfs.github.com/spec/v1'; paths=['app_chainlit.py','init_db.py','cleanup_db.py','preCarregaDataBase.py','preCarregaGrafo.py','files']; bad=[]; walk=lambda p: ([p] if os.path.isfile(p) else [os.path.join(r,n) for r,_,fs in os.walk(p) for n in fs] if os.path.isdir(p) else []); [bad.append(f) for p in paths for f in walk(p) if open(f,'rb').readline(200).decode('utf-8','ignore').strip()==prefix]; print('Validacao Git LFS OK' if not bad else 'ERRO: arquivos Git LFS como ponteiros:\n'+'\n'.join(bad[:50])); sys.exit(1 if bad else 0)" || exit 1
python init_db.py || echo "Warning: init_db.py failed, but continuing..."

# RAG Generation Sequence
mkdir -p /app/code_graph_storage
if [ ! -s "/app/code_graph_storage/code_graph.gpickle" ]; then
    echo "RAG: code_graph.gpickle missing or empty. Running build_graph.py..."
    python build_graph.py || echo "Warning: build_graph.py failed."
fi

if [ ! -d "chroma_graph_db" ] || [ -z "$(ls -A chroma_graph_db 2>/dev/null)" ]; then
    echo "RAG: chroma_graph_db missing or empty. Running preCarregaGrafo.py..."
    python preCarregaGrafo.py || echo "Warning: preCarregaGrafo.py failed."
fi

if [ ! -d "arquivos/chat_retrieval_db" ] || [ -z "$(ls -A arquivos/chat_retrieval_db 2>/dev/null)" ]; then
    echo "RAG: chat_retrieval_db missing or empty. Running preCarregaDataBase.py..."
    python preCarregaDataBase.py || echo "Warning: preCarregaDataBase.py failed."
fi

echo "Running data retention cleanup (cleanup_db.py)..."
python cleanup_db.py || echo "Warning: cleanup_db.py failed, but continuing..."

echo "Starting Chainlit VRCHAT..."
# Note: Added -h 0.0.0.0 and -p 8000 explicitly
exec chainlit run app_chainlit.py --host 0.0.0.0 --port 8000
