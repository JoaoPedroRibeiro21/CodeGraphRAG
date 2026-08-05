#!/usr/bin/env python3
"""Interactive setup wizard for CodexGraph-RAG.

Run before the first use to configure LLM/embedding providers and API keys.
"""

from codexgraph_rag.wizard import run_wizard

if __name__ == "__main__":
    run_wizard()
