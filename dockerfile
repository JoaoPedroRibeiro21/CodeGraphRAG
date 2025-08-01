# Usa imagem base com Python 3.11
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CHROMA_TELEMETRY=False

COPY . /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    poppler-utils \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Expõe a porta da aplicação
EXPOSE 8000

# Roda o preCarregaDataBase.py antes de iniciar o servidor
CMD ["sh", "-c", "python preCarregaDataBase.py && gunicorn app:app --bind 0.0.0.0:8000 --workers 4"]
