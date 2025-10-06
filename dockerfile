# dockerfile (Versão Final e Estável)

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

# Instala as dependências Python com a versão fixada do tree-sitter
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o resto da aplicação
COPY . /app

# --- ETAPA DE PRÉ-PROCESSAMENTO COMPLETA ---
# Clona a gramática Java (necessária para o build_graph.py)
RUN git clone https://github.com/tree-sitter/tree-sitter-java.git

# Executa todos os scripts de indexação em ordem
RUN python3 preCarregaDataBase.py
RUN python3 build_graph.py
RUN python3 preCarregaGrafo.py

EXPOSE 8000

CMD ["gunicorn", "-k", "gevent", "-w", "1", "-b", "0.0.0.0:8000", "app:app"]