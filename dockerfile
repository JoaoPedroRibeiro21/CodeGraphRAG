# dockerfile (Chainlit — CodexGraph-RAG)

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./pyproject.toml /app/pyproject.toml
COPY ./requirements.txt /app/requirements.txt

# Instala o pacote em modo editable junto com as extras padrão
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e ".[all]"

# Copia o resto da aplicação
COPY . /app

# Chaves e configurações devem vir do .env em runtime, não do build.
# Não defina OPENAI_API_KEY aqui.

# Clona gramáticas tree-sitter conforme linguagens configuradas em config.yaml
# (por padrão apenas Java; outras linguagens podem ser adicionadas depois)
RUN rm -rf tree-sitter-java && \
    git clone --depth 1 https://github.com/tree-sitter/tree-sitter-java.git

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
