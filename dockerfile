# Usa uma imagem oficial do Python
FROM python:3.10-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia os arquivos da aplicação para o container
COPY . /app

# Instala dependências do sistema 
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
RUN pip install --upgrade pip

# Se você tiver um requirements.txt, use esta linha:
RUN pip install -r requirements.txt

# Expõe a porta 5000
EXPOSE 5000

# Define a variável de ambiente
ENV PYTHONUNBUFFERED=1

RUN python preCarregaDataBase.py

# Comando para iniciar o app Flask
CMD ["python", "app.py"]
