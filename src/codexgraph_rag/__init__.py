"""CodexGraph-RAG: open-source Graph-RAG for codebases.

Provides multi-language code graph construction, domain profiles,
and pluggable LLM/embedding providers.
"""

from codexgraph_rag.config import Config, load_config
from codexgraph_rag.profile import DomainProfile, load_profile

__version__ = "0.1.0"
__all__ = ["Config", "load_config", "DomainProfile", "load_profile"]
