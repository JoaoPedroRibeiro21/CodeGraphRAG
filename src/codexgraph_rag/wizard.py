"""Interactive setup wizard for CodexGraph-RAG.

Guides the user through selecting an LLM/embedding provider and providing the
API key. Writes the choices to `.env` and optionally updates `config.yaml`.
"""

from __future__ import annotations

import os
from pathlib import Path

from codexgraph_rag.config import load_config, save_config_example


def _ask(prompt: str, default: str = "") -> str:
    if default:
        full = f"{prompt} [{default}]: "
    else:
        full = f"{prompt}: "
    answer = input(full).strip()
    return answer if answer else default


def _ask_choice(prompt: str, options: list[str], default: str) -> str:
    print(prompt)
    for i, option in enumerate(options, start=1):
        marker = " (default)" if option == default else ""
        print(f"  {i}. {option}{marker}")
    while True:
        answer = input("Escolha (número ou nome): ").strip()
        if answer.isdigit():
            idx = int(answer) - 1
            if 0 <= idx < len(options):
                return options[idx]
        if answer in options:
            return answer
        if not answer:
            return default
        print("Opção inválida. Tente novamente.")


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


def _provider_env_var(provider: str, kind: str = "api_key") -> str:
    if provider == "openai":
        return "OPENAI_API_KEY"
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider == "google":
        return "GOOGLE_API_KEY"
    if provider == "ollama":
        return "OLLAMA_BASE_URL"
    return f"{provider.upper()}_{kind.upper()}"


def _default_llm_model(provider: str) -> str:
    return {
        "openai": "gpt-4o",
        "anthropic": "claude-3-5-sonnet-20241022",
        "google": "gemini-1.5-pro",
        "ollama": "llama3.1",
    }.get(provider, "gpt-4o")


def _default_embedding_model(provider: str) -> str:
    return {
        "openai": "text-embedding-3-small",
        "google": "models/text-embedding-004",
        "ollama": "nomic-embed-text",
    }.get(provider, "text-embedding-3-small")


def run_wizard(config_path: str = "config.yaml", env_path: str = ".env") -> None:
    """Run the interactive setup wizard."""
    print("=" * 60)
    print("  CodexGraph-RAG — Configuração Inicial")
    print("=" * 60)

    providers = ["openai", "anthropic", "google", "ollama"]
    llm_provider = _ask_choice(
        "Escolha o provedor de LLM:",
        providers,
        default="openai",
    )

    # Anthropic has no embeddings; ask separately for embeddings provider.
    if llm_provider == "anthropic":
        embed_providers = ["openai", "google", "ollama"]
        print("\nAnthropic não fornece modelos de embeddings.")
        embedding_provider = _ask_choice(
            "Escolha o provedor de embeddings:",
            embed_providers,
            default="openai",
        )
    else:
        embedding_provider = llm_provider

    llm_model = _ask("Modelo de LLM", _default_llm_model(llm_provider))
    embedding_model = _ask(
        "Modelo de embeddings", _default_embedding_model(embedding_provider)
    )

    env_var = _provider_env_var(llm_provider)
    if llm_provider == "ollama":
        base_url = _ask("URL do Ollama", "http://localhost:11434")
        api_key = "not-needed"
    else:
        api_key = _ask(f"API key ({env_var})")
        base_url = ""

    product_name = _ask("Nome do produto/sistema", "CodexGraph")
    profile = _ask_choice(
        "Perfil de domínio:",
        ["profiles/generic.yaml", "profiles/erp-fiscal.example.yaml", "profiles/empty.yaml"],
        default="profiles/generic.yaml",
    )

    # Update config.yaml
    config_file = Path(config_path)
    if not config_file.exists():
        save_config_example(config_path)

    cfg = load_config(config_path)
    cfg.product_name = product_name
    cfg.profile = profile
    cfg.llm.provider = llm_provider
    cfg.llm.model = llm_model
    if base_url:
        cfg.llm.base_url = base_url
    cfg.embeddings.provider = embedding_provider
    cfg.embeddings.model = embedding_model
    if base_url:
        cfg.embeddings.base_url = base_url

    with open(config_path, "w", encoding="utf-8") as f:
        import yaml
        yaml.safe_dump(cfg.model_dump(exclude_none=True), f, sort_keys=False, allow_unicode=True)

    # Update .env
    env_file = Path(env_path)
    env_lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    env_keys = {
        "CG_LLM__PROVIDER": llm_provider,
        "CG_LLM__MODEL": llm_model,
        "CG_CLASSIFIER__PROVIDER": llm_provider,
        "CG_CLASSIFIER__MODEL": "gpt-4o-mini" if llm_provider == "openai" else llm_model,
        "CG_CODE_ANALYSIS__PROVIDER": llm_provider,
        "CG_CODE_ANALYSIS__MODEL": llm_model,
        "CG_CODE_VERIFICATION__PROVIDER": llm_provider,
        "CG_CODE_VERIFICATION__MODEL": llm_model,
        "CG_EMBEDDINGS__PROVIDER": embedding_provider,
        "CG_EMBEDDINGS__MODEL": embedding_model,
    }
    if base_url:
        env_keys["CG_LLM__BASE_URL"] = base_url
        env_keys["CG_EMBEDDINGS__BASE_URL"] = base_url
    if api_key and api_key != "not-needed":
        env_keys[env_var] = api_key

    existing = {line.split("=", 1)[0].strip() for line in env_lines if "=" in line and not line.strip().startswith("#")}
    for key, value in env_keys.items():
        if key not in existing:
            env_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    print("\n" + "=" * 60)
    print("Configuração salva com sucesso!")
    print(f"  Config:  {config_path}")
    print(f"  Secrets: {env_path}")
    print(f"  LLM:     {llm_provider} / {llm_model}")
    print(f"  Embeddings: {embedding_provider} / {embedding_model}")
    if api_key and api_key != "not-needed":
        print(f"  API key: {_mask_key(api_key)}")
    print("=" * 60)


if __name__ == "__main__":
    run_wizard()
