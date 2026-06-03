import os
import re
from dataclasses import dataclass
from typing import Any

from question_classifier import normalize_question_text

PDF_VALIDATION_MIN_SCORE = float(os.getenv("PDF_VALIDATION_MIN_SCORE", "0.52"))
PDF_VALIDATION_MIN_LEXICAL = float(os.getenv("PDF_VALIDATION_MIN_LEXICAL", "0.18"))
PDF_VALIDATION_HIGH_VECTOR_OVERRIDE = float(os.getenv("PDF_VALIDATION_HIGH_VECTOR_OVERRIDE", "0.78"))
PDF_VALIDATION_MAX_EXCERPT_CHARS = int(os.getenv("PDF_VALIDATION_MAX_EXCERPT_CHARS", "700"))

STOPWORDS_PT = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "que",
    "se",
    "sem",
    "ser",
    "sua",
    "suas",
    "seu",
    "seus",
    "um",
    "uma",
    "uns",
    "umas",
}


@dataclass
class ValidatedEvidence:
    doc: Any
    validation_score: float
    vector_score: float
    lexical_score: float
    matched_terms: tuple[str, ...]
    source_label: str
    page_label: str | None
    excerpt: str


@dataclass
class ValidationResult:
    approved: list[ValidatedEvidence]
    rejected_count: int
    total_candidates: int


def _normalize_vector_score(score: float | None) -> float:
    if score is None:
        return 0.5
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0.5
    if 0.0 <= value <= 1.0:
        return value
    if value > 1.0:
        return 1.0 / (1.0 + value)
    return 0.0


def _keyword_tokens(text: str) -> set[str]:
    normalized = normalize_question_text(text)
    words = [w for w in normalized.split() if len(w) >= 3 and w not in STOPWORDS_PT]
    return set(words)


def _lexical_score(question_terms: set[str], content_terms: set[str]) -> tuple[float, tuple[str, ...]]:
    if not question_terms:
        return 0.0, ()
    matched = tuple(sorted(question_terms & content_terms))
    score = len(matched) / max(1, len(question_terms))
    return round(score, 4), matched


def _composite_score(vector_score: float, lexical_score: float, matched_terms: tuple[str, ...]) -> float:
    phrase_boost = 0.08 if len(matched_terms) >= 3 else 0.0
    return round(min(1.0, (0.62 * vector_score) + (0.30 * lexical_score) + phrase_boost), 4)


def _passes_thresholds(vector_score: float, lexical_score: float, composite_score: float) -> bool:
    if vector_score >= PDF_VALIDATION_HIGH_VECTOR_OVERRIDE and lexical_score >= 0.10:
        return True
    return composite_score >= PDF_VALIDATION_MIN_SCORE and lexical_score >= PDF_VALIDATION_MIN_LEXICAL


def _source_label(metadata: dict[str, Any]) -> str:
    return (
        str(metadata.get("arquivo_fonte") or "").strip()
        or str(metadata.get("fonte") or "").strip()
        or str(metadata.get("source") or "").split("/")[-1].strip()
        or "fonte_desconhecida"
    )


def _page_label(metadata: dict[str, Any]) -> str | None:
    if "page_label" in metadata and str(metadata.get("page_label")).strip():
        return str(metadata.get("page_label")).strip()
    if "page" in metadata:
        page = metadata.get("page")
        if isinstance(page, int):
            return str(page + 1)
        if str(page).strip():
            return str(page).strip()
    return None


def _excerpt(text: str) -> str:
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if len(clean) <= PDF_VALIDATION_MAX_EXCERPT_CHARS:
        return clean
    return clean[: PDF_VALIDATION_MAX_EXCERPT_CHARS - 3].rstrip() + "..."


def validate_pdf_evidence(
    question: str,
    docs_and_scores: list[tuple[Any, float | None]],
    max_results: int = 5,
) -> ValidationResult:
    question_terms = _keyword_tokens(question)
    approved: list[ValidatedEvidence] = []
    rejected = 0

    for doc, raw_score in docs_and_scores:
        content = getattr(doc, "page_content", "") or ""
        metadata = getattr(doc, "metadata", {}) or {}
        content_terms = _keyword_tokens(content)
        lexical_score, matched_terms = _lexical_score(question_terms, content_terms)
        vector_score = _normalize_vector_score(raw_score)
        composite_score = _composite_score(vector_score, lexical_score, matched_terms)
        if not _passes_thresholds(vector_score, lexical_score, composite_score):
            rejected += 1
            continue

        approved.append(
            ValidatedEvidence(
                doc=doc,
                validation_score=composite_score,
                vector_score=round(vector_score, 4),
                lexical_score=lexical_score,
                matched_terms=matched_terms,
                source_label=_source_label(metadata),
                page_label=_page_label(metadata),
                excerpt=_excerpt(content),
            )
        )

    approved.sort(key=lambda item: (item.validation_score, item.vector_score, item.lexical_score), reverse=True)
    if max_results > 0:
        approved = approved[:max_results]

    return ValidationResult(
        approved=approved,
        rejected_count=rejected,
        total_candidates=len(docs_and_scores),
    )


def build_validated_pdf_context(approved: list[ValidatedEvidence]) -> str:
    if not approved:
        return "Nao ha evidencia documental validada suficiente para responder com seguranca."

    lines = []
    for index, evidence in enumerate(approved, start=1):
        page_text = f" | pagina: {evidence.page_label}" if evidence.page_label else ""
        terms_text = ", ".join(evidence.matched_terms[:8]) if evidence.matched_terms else "sem_termos_em_comum"
        lines.append(
            f"[EVIDENCIA {index}] fonte: {evidence.source_label}{page_text} | score_validacao: {evidence.validation_score:.4f} | termos: {terms_text}\n"
            f"Trecho: {evidence.excerpt}"
        )
    return "\n\n".join(lines)
