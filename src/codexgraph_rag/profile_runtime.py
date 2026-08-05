"""Runtime helpers that bridge domain profiles to legacy dict-based code.

This module centralizes the conversion from a DomainProfile into the exact
sets/dicts used by question_classifier, adaptive_retrieval, graph_retrieval and
retrieval_orchestrator. As those modules are refactored further, this helper
will shrink and eventually disappear.
"""

from __future__ import annotations

from codexgraph_rag.profile import DomainProfile


def category_names(profile: DomainProfile | None) -> set[str]:
    if profile is None or not profile.categories:
        return {"geral"}
    return {c.name for c in profile.categories}


def category_keywords(profile: DomainProfile | None) -> dict[str, set[str]]:
    """Return LOCAL_CATEGORY_KEYWORDS-like structure."""
    result: dict[str, set[str]] = {}
    if profile is None:
        return result
    for cat in profile.categories:
        result[cat.name] = set(cat.keywords)
    return result


def domain_intent_keywords(profile: DomainProfile | None) -> set[str]:
    """Return a broad set of domain keywords across all categories + artifacts."""
    if profile is None:
        return set()
    result: set[str] = set()
    for cat in profile.categories:
        result.update(cat.keywords)
    for key, values in profile.artifact_hints.model_dump().items():
        result.update(values)
    result.update(profile.deep_analysis_keywords)
    result.update(profile.explicit_deep_analysis_keywords)
    return result


def technical_signal_keywords(profile: DomainProfile | None) -> set[str]:
    if profile is None:
        return set()
    result = set(profile.deep_analysis_keywords)
    result.update(profile.explicit_deep_analysis_keywords)
    for key, values in profile.artifact_hints.model_dump().items():
        result.update(values)
    return result


def stopwords(profile: DomainProfile | None) -> set[str]:
    if profile is None:
        return set()
    return set(profile.stopwords)


def artifact_hints(profile: DomainProfile | None) -> dict[str, set[str]]:
    if profile is None:
        return {}
    return {k: set(v) for k, v in profile.artifact_hints.model_dump().items() if v}


def category_tuning(profile: DomainProfile | None) -> dict[str, dict[str, float | int]]:
    """Return per-category tunables for adaptive/graph retrieval."""
    result: dict[str, dict[str, float | int]] = {}
    if profile is None:
        return result
    for cat in profile.categories:
        result[cat.name] = {
            "min_score": cat.min_score if cat.min_score is not None else 0.35,
            "max_nodes": cat.max_nodes if cat.max_nodes is not None else 24,
            "max_expansions": cat.max_expansions if cat.max_expansions is not None else 12,
            "max_depth": cat.max_depth if cat.max_depth is not None else 2,
            "multiplier": cat.multiplier,
        }
    return result


def category_artifact_defaults(profile: DomainProfile | None) -> dict[str, list[str]]:
    if profile is None:
        return {}
    return {cat.name: list(cat.artifact_defaults) for cat in profile.categories}


def domain_cards(profile: DomainProfile | None) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    """Return DomainCard-compatible tuples (repo, aliases, responsibilities)."""
    if profile is None:
        return []
    return [
        (card.repo, tuple(card.aliases), tuple(card.responsibilities))
        for card in profile.domain_cards
    ]


def simple_conversation_responses(profile: DomainProfile | None, product_name: str) -> dict[str, str]:
    """Generate neutral small-talk responses using the configured product name."""
    name = (profile.product_name if profile and profile.product_name else product_name) or "sistema"
    return {
        "bom dia": f"Bom dia! Como posso ajudar com o {name} hoje?",
        "boa tarde": f"Boa tarde! Como posso ajudar com o {name} hoje?",
        "boa noite": f"Boa noite! Como posso ajudar com o {name} hoje?",
        "oi": f"Olá! Como posso ajudar com o {name} hoje?",
        "ola": f"Olá! Como posso ajudar com o {name} hoje?",
        "tudo bem": f"Tudo bem por aqui. Como posso ajudar com o {name} hoje?",
        "obrigado": f"Disponha! Se precisar de algo no {name}, é só me chamar.",
        "obrigada": f"Disponha! Se precisar de algo no {name}, é só me chamar.",
        "valeu": f"Disponha! Se precisar de algo no {name}, é só me chamar.",
    }
