# 🧠 Assistente RAG com PDFs e Flask

Este projeto é uma API baseada em Flask com LangChain, ChromaDB e vetorização usando o modelo `nomic-embed-text` via Ollama.

Ele carrega arquivos PDF de uma base de conhecimento, cria um banco vetorial e permite responder perguntas via API com base nesses documentos.

---

## 📁 Estrutura

```
.
├── preCarregaDataBase.py        # Script para gerar o banco vetorial (RAG)
├── app.py             # API Flask principal
├── loader.py                    # Carregamento e limpeza de PDFs
├── vector_db.py                 # Chunking e banco vetorial (Chroma)
├── requirements.txt             # Dependências
├── files/
│   └── BaseDeConhecimento_PDF/ # PDFs da base de conhecimento
└── arquivos/chat_retrieval_db/ # Banco vetorial persistido (gerado)
```

---

## ✅ Pré-requisitos

- Python 3.10+
- [Ollama instalado](https://ollama.com/)
- Docker (opcional, para deploy)
- API Key da OpenAI (para validação ou fallback, se quiser usar OpenAIEmbeddings)

---

## ⚙️ Setup Local

### 1. Instale as dependências
```bash
pip install -r requirements.txt
```

### 2. Adicione seus PDFs
Coloque seus arquivos PDF dentro de:
```
files/BaseDeConhecimento_PDF/
```

### 3. Rode o pré-processador
```bash
python preCarregaDataBase.py
```
Esse comando:
- Lê os PDFs
- Faz chunking
- Cria o banco vetorial com ChromaDB

### 4. Inicie a API Flask
```bash
python app.py
```

Acesse:
- `http://localhost:5000/status` → status da API
- `http://localhost:5000/perguntar` (POST) → envia perguntas

---

## 📡 Exemplo de uso via `curl`
```bash
curl -X POST http://localhost:5000/perguntar \
     -H "Content-Type: application/json" \
     -d '{"pergunta": "Qual é o processo de faturamento?"}'
```

---

## 🐳 Docker

### Build e run:
```bash
docker build -t flask-rag .
docker run -p 5000:5000 flask-rag
```

### Deploy no Azure (opcional)
Use o Azure App Service para subir como container ou como app Python puro.

---

## 📂 Variáveis de Ambiente
Crie um arquivo `.env` com:
```env
OPENAI_API_KEY=your_key_here  # se desejar usar modelos OpenAI alternativos
```