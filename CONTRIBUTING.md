# Contribuindo com o CodexGraph-RAG

Obrigado pelo interesse em contribuir! Este projeto é um Graph-RAG open source para bases de código, com perfis de domínio configuráveis.

## Como contribuir

1. Faça um fork do repositório.
2. Crie uma branch para sua feature ou correção: `git checkout -b feature/nome-da-feature`.
3. Instale o ambiente de desenvolvimento:
   ```bash
   python -m venv venv
   ./venv/bin/pip install -e ".[all]"
   ./venv/bin/pip install -e ".[dev]"
   ```
4. Faça suas alterações e adicione testes quando possível.
5. Execute o lint e os testes:
   ```bash
   ./venv/bin/python -m pytest
   ./venv/bin/python -m py_compile src/codexgraph_rag/*.py
   ```
6. Envie um Pull Request descrevendo o problema e a solução.

## Áreas de contribuição bem-vindas

- Novos perfis de domínio em `profiles/`.
- Novos parsers de linguagem em `src/codexgraph_rag/parsers/`.
- Suporte a novos provedores de LLM/embdeddings em `src/codexgraph_rag/llm/`.
- Melhorias na documentação (`docs/`) e exemplos (`examples/`).
- Traduções de profiles para outros idiomas.

## Código de conduta

Mantenha o ambiente respeitoso e construtivo. Dúvidas técnicas são bem-vindas.
