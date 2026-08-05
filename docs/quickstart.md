# Quickstart

## 1. Instalar

```bash
python -m venv venv
./venv/bin/pip install -e ".[all]"
```

## 2. Configurar

```bash
cp config.yaml config.local.yaml
cp .env.example .env
./venv/bin/python setup_config.py
```

Edite `.env` com as chaves do provider escolhido.

## 3. Apontar repositórios

```bash
cp repos.example.json repos.json
# edite repos.json com as URLs dos seus repositórios
```

## 4. Gerar o grafo

```bash
./venv/bin/python sync_repos.py
./venv/bin/python build_graph.py
./venv/bin/python preCarregaGrafo.py
```

Ou use o orquestrador:

```bash
./venv/bin/python refresh_code_index.py --once
```

## 5. Indexar documentos (opcional)

Coloque PDFs/TXTs em `files/documents/` e rode:

```bash
./venv/bin/python preCarregaDataBase.py
```

## 6. Rodar

```bash
./venv/bin/chainlit run app_chainlit.py --host 0.0.0.0 --port 8000
```

Acesse: http://localhost:8000
