import logging
import os
from dataclasses import dataclass, field

from adaptive_retrieval import RetrievalSessionState, assess_gap_report, run_adaptive_code_retrieval
from codexgraph_rag import settings
from codexgraph_rag.profile_runtime import domain_cards as _profile_domain_cards
from graph_retrieval import RetrievalSummary, confidence_label
from question_classifier import QuestionClassification, QuestionStrategy, normalize_question_text

logger = logging.getLogger(__name__)


EFFORT_ROUND_LIMITS = {
    "leve": 1,
    "medio": 2,
    "profundo": 3,
}


def _round_limits() -> dict[str, int]:
    return {
        "leve": int(os.getenv("ORCHESTRATOR_MAX_ROUNDS_LIGHT", str(EFFORT_ROUND_LIMITS["leve"]))),
        "medio": int(os.getenv("ORCHESTRATOR_MAX_ROUNDS_MEDIUM", str(EFFORT_ROUND_LIMITS["medio"]))),
        "profundo": int(os.getenv("ORCHESTRATOR_MAX_ROUNDS_DEEP", str(EFFORT_ROUND_LIMITS["profundo"]))),
    }


@dataclass(frozen=True)
class DomainCard:
    repo: str
    aliases: tuple[str, ...]
    responsibilities: tuple[str, ...]


@dataclass
class OrchestrationResult:
    pdf_context: str
    pdf_docs: list
    pdf_validation: object | None
    code_nodes: list
    retrieval_summary: RetrievalSummary | None
    expected_repos: list[str]
    found_repos: list[str]
    missing_repos: list[str]
    queries_used: list[str]
    rounds_executed: int
    lacuna_score: float
    escalated_to_deep: bool
    effort_used: str
    expected_artifacts: list[str] = field(default_factory=list)
    found_artifacts: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    standalone_question: str = ""
    path_evidence_count: int = 0
    session_state: dict | None = None


def build_domain_cards() -> list[DomainCard]:
    """Build domain cards from the active domain profile, or return an empty list."""
    cards = _profile_domain_cards(settings.profile)
    return [DomainCard(repo=repo, aliases=aliases, responsibilities=responsibilities) for repo, aliases, responsibilities in cards]


def _extract_history_text(chat_history: list[tuple[str, str]], window: int) -> str:
    if not chat_history:
        return ""
    windowed = chat_history[-window:]
    return " ".join(text for _, text in windowed if text)


def infer_expected_repos(question: str, chat_history: list[tuple[str, str]], cards: list[DomainCard]) -> list[str]:
    normalized = normalize_question_text(f"{question} {_extract_history_text(chat_history, 8)}")
    expected = set()

    for card in cards:
        if any(alias in normalized for alias in card.aliases):
            expected.add(card.repo)

    # Domain-specific co-occurrence rules can be added later via profile `extra` config.
    return sorted(expected)


def generate_query_variants(question: str, history_text: str, expected_repos: list[str]) -> list[str]:
    queries: list[str] = []
    base = question.strip()
    if base:
        queries.append(base)

    if history_text.strip():
        queries.append(f"{base} contexto: {history_text[:800]}")

    queries.append(f"{base} fluxo tecnico classes metodos evidencias")
    queries.append(f"{base} tabelas colunas sql parametros mensagens de erro")

    for repo in expected_repos:
        queries.append(f"{base} {repo}")

    deduped = []
    seen = set()
    for item in queries:
        normalized = normalize_question_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped


def _repo_from_node(node) -> str | None:
    source_repo = getattr(node, "source_repo", None)
    if source_repo:
        return source_repo

    node_id = getattr(node, "node_id", "")
    if "::" in node_id:
        return node_id.split("::", 1)[0]
    return None


def _assess_lacuna(
    question: str,
    expected_repos: list[str],
    found_repos: set[str],
    code_nodes: list,
    average_score: float,
) -> float:
    expected_count = len(expected_repos)
    if expected_count == 0:
        repo_coverage = 1.0
    else:
        repo_coverage = len(found_repos & set(expected_repos)) / expected_count

    normalized = normalize_question_text(question)
    needs_sql_evidence = any(term in normalized for term in ("sql", "tabela", "coluna"))
    needs_flow_evidence = any(term in normalized for term in ("fluxo", "integracao", "autorizacao", "autorizador"))

    evidence_coverage = 1.0
    if needs_sql_evidence:
        has_sql = any(
            "select" in (getattr(node, "code", "") or "").lower()
            or "insert" in (getattr(node, "code", "") or "").lower()
            or "update" in (getattr(node, "code", "") or "").lower()
            or "delete" in (getattr(node, "code", "") or "").lower()
            for node in code_nodes
        )
        evidence_coverage = min(evidence_coverage, 1.0 if has_sql else 0.0)
    if needs_flow_evidence:
        has_flow = len(code_nodes) >= 4
        evidence_coverage = min(evidence_coverage, 1.0 if has_flow else 0.4)

    confidence = max(0.0, min(1.0, average_score))
    lacuna = 1.0 - ((repo_coverage * 0.45) + (confidence * 0.30) + (evidence_coverage * 0.25))
    return round(max(0.0, min(1.0, lacuna)), 4)


def _merge_code_nodes(existing: dict, incoming: list) -> None:
    for node in incoming or []:
        previous = existing.get(node.node_id)
        prev_score = getattr(previous, "retrieval_score", 0.0) if previous else -1.0
        current_score = getattr(node, "retrieval_score", 0.0)
        if previous is None or current_score >= prev_score:
            existing[node.node_id] = node


def _build_summary(
    classification: QuestionClassification,
    nodes: list,
    expected_repos: list[str],
    found_repos: list[str],
    missing_repos: list[str],
) -> RetrievalSummary:
    average_score = round(sum(getattr(node, "retrieval_score", 0.0) for node in nodes) / len(nodes), 4) if nodes else 0.0
    seed_count = sum(1 for node in nodes if getattr(node, "is_seed", False))
    return RetrievalSummary(
        category=classification.category,
        category_confidence=classification.confidence,
        overall_confidence=confidence_label(average_score),
        average_score=average_score,
        seed_count=seed_count,
        neighbor_count=max(0, len(nodes) - seed_count),
        total_nodes=len(nodes),
        expected_repos=expected_repos,
        found_repos=found_repos,
        missing_repos=missing_repos,
        query_hint="orchestrated",
    )


async def orchestrate_retrieval(
    *,
    question: str,
    chat_history: list[tuple[str, str]],
    strategy: QuestionStrategy,
    retrieve_pdf_fn,
    retrieve_code_fn,
    forced_expected_repos: list[str] | None = None,
    session_state: dict | None = None,
    code_graph=None,
) -> OrchestrationResult:
    default_effort = os.getenv("ORCHESTRATOR_DEFAULT_EFFORT", "medio").strip().lower() or "medio"
    deep_threshold = float(os.getenv("ORCHESTRATOR_DEEP_LACUNA_THRESHOLD", "0.35"))
    history_window = int(os.getenv("ORCHESTRATOR_HISTORY_WINDOW", "8"))

    round_limits = _round_limits()
    effort = (strategy.retrieval_effort or default_effort).lower()
    effort = effort if effort in round_limits else default_effort

    cards = build_domain_cards()
    history_text = _extract_history_text(chat_history, history_window)
    expected_repos = sorted(set(forced_expected_repos or infer_expected_repos(question, chat_history, cards)))

    max_rounds = round_limits.get(effort, 2)
    merged_pdf_context = "A recuperacao em documentos nao foi executada para esta pergunta."
    merged_pdf_docs = []
    merged_pdf_validation = None

    merged_code_nodes: list[object] = []
    queries_used: list[str] = []
    escalated_to_deep = False
    lacuna_score = 1.0
    expected_artifacts: list[str] = []
    found_artifacts: list[str] = []
    missing_artifacts: list[str] = []
    standalone_question = question
    path_evidence_count = 0
    adaptive_state = RetrievalSessionState.from_dict(session_state)

    if strategy.use_code_retrieval:
        adaptive_result = await run_adaptive_code_retrieval(
            question=question,
            chat_history=chat_history,
            classification=strategy.classification,
            expected_repos=expected_repos,
            retrieve_code_fn=retrieve_code_fn,
            session_state=adaptive_state,
            code_graph=code_graph,
            max_rounds=max_rounds,
            deep_threshold=deep_threshold,
            query_hint_prefix="orchestrated_adaptive",
        )
        merged_code_nodes = adaptive_result.nodes
        queries_used.extend(adaptive_result.queries_used)
        lacuna_score = adaptive_result.gap_report.lacuna_score
        expected_artifacts = adaptive_result.intent.expected_artifacts
        missing_artifacts = adaptive_result.gap_report.missing_artifacts
        standalone_question = adaptive_result.intent.standalone_question
        path_evidence_count = len(adaptive_result.path_evidences)
        adaptive_state = adaptive_result.session_state

        found_artifacts = sorted(set(expected_artifacts) - set(missing_artifacts))
        if effort != "profundo" and adaptive_result.gap_report.needs_deeper_search:
            escalated_to_deep = True
            effort = "profundo"
            deep_result = await run_adaptive_code_retrieval(
                question=question,
                chat_history=chat_history,
                classification=strategy.classification,
                expected_repos=expected_repos,
                retrieve_code_fn=retrieve_code_fn,
                session_state=adaptive_state,
                code_graph=code_graph,
                max_rounds=round_limits["profundo"],
                deep_threshold=deep_threshold,
                query_hint_prefix="orchestrated_deep",
            )
            merged_map = {node.node_id: node for node in merged_code_nodes}
            for node in deep_result.nodes:
                previous = merged_map.get(node.node_id)
                previous_score = float(getattr(previous, "retrieval_score", 0.0) or 0.0) if previous else -1.0
                current_score = float(getattr(node, "retrieval_score", 0.0) or 0.0)
                if previous is None or current_score >= previous_score:
                    merged_map[node.node_id] = node
            merged_code_nodes = list(merged_map.values())
            queries_used.extend(deep_result.queries_used)
            expected_artifacts = deep_result.intent.expected_artifacts
            standalone_question = deep_result.intent.standalone_question
            path_evidence_count += len(deep_result.path_evidences)
            adaptive_state = deep_result.session_state
            merged_gap, _ = assess_gap_report(
                expected_repos=expected_repos,
                expected_artifacts=expected_artifacts,
                nodes=merged_code_nodes,
                deep_threshold=deep_threshold,
            )
            lacuna_score = merged_gap.lacuna_score
            missing_artifacts = merged_gap.missing_artifacts
            found_artifacts = sorted(set(expected_artifacts) - set(missing_artifacts))

    if strategy.use_pdf_retrieval:
        pdf_query = standalone_question if standalone_question.strip() else (queries_used[0] if queries_used else question)
        pdf_result = await retrieve_pdf_fn(pdf_query, strategy.classification)
        pdf_context = ""
        pdf_docs = []
        pdf_validation = None
        if isinstance(pdf_result, tuple):
            if len(pdf_result) >= 2:
                pdf_context, pdf_docs = pdf_result[0], pdf_result[1]
            if len(pdf_result) >= 3:
                pdf_validation = pdf_result[2]
        elif isinstance(pdf_result, list) and len(pdf_result) >= 2:
            pdf_context, pdf_docs = pdf_result[0], pdf_result[1]
        elif isinstance(pdf_result, str):
            pdf_context = pdf_result

        if pdf_docs:
            merged_pdf_context = pdf_context
            merged_pdf_docs = pdf_docs
            merged_pdf_validation = pdf_validation

    found_repos = sorted({repo for repo in (_repo_from_node(node) for node in merged_code_nodes) if repo})
    missing_repos = sorted(set(expected_repos) - set(found_repos))
    if not queries_used:
        query_variants = generate_query_variants(question, history_text, expected_repos)
        queries_used = query_variants[:1]
    summary = (
        _build_summary(strategy.classification, merged_code_nodes, expected_repos, found_repos, missing_repos)
        if merged_code_nodes
        else None
    )

    return OrchestrationResult(
        pdf_context=merged_pdf_context,
        pdf_docs=merged_pdf_docs,
        pdf_validation=merged_pdf_validation,
        code_nodes=merged_code_nodes,
        retrieval_summary=summary,
        expected_repos=expected_repos,
        found_repos=found_repos,
        missing_repos=missing_repos,
        queries_used=queries_used,
        rounds_executed=len(queries_used),
        lacuna_score=lacuna_score,
        escalated_to_deep=escalated_to_deep,
        effort_used=effort,
        expected_artifacts=expected_artifacts,
        found_artifacts=found_artifacts,
        missing_artifacts=missing_artifacts,
        standalone_question=standalone_question,
        path_evidence_count=path_evidence_count,
        session_state=adaptive_state.to_dict(),
    )
