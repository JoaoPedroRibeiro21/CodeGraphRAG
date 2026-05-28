# dockerfile (Chainlit — VRChat)

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

# Instala as dependências Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o resto da aplicação
COPY . /app

# Falha cedo se o build recebeu ponteiros Git LFS em vez dos arquivos reais.
RUN python -c "import os,sys; prefix='version https://git-lfs.github.com/spec/v1'; paths=['app_chainlit.py','init_db.py','cleanup_db.py','preCarregaDataBase.py','preCarregaGrafo.py','files']; bad=[]; walk=lambda p: ([p] if os.path.isfile(p) else [os.path.join(r,n) for r,_,fs in os.walk(p) for n in fs] if os.path.isdir(p) else []); [bad.append(f) for p in paths for f in walk(p) if open(f,'rb').readline(200).decode('utf-8','ignore').strip()==prefix]; print('Validacao Git LFS OK' if not bad else 'ERRO: arquivos Git LFS como ponteiros:\n'+'\n'.join(bad[:50])); sys.exit(1 if bad else 0)"

# --- ETAPA DE PRÉ-PROCESSAMENTO COMPLETA ---
# A chave OpenAI é necessária durante o build para gerar embeddings
ARG OPENAI_API_KEY
ENV OPENAI_API_KEY=${OPENAI_API_KEY}

# Clona a gramática Java (necessária para o build_graph.py)
# Remove se já existir (pode vir do COPY .)
RUN rm -rf tree-sitter-java && git clone https://github.com/tree-sitter/tree-sitter-java.git

# A indexação (preCarregaDataBase, build_graph, preCarregaGrafo)
# Agora será feita separadamente fora do processo de build do contêiner web.

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Executa o script de entrada
ENTRYPOINT ["/app/entrypoint.sh"]
