import logging
import os
import re
from dataclasses import dataclass, field

from code_analysis_pipeline import CodeNode
from codexgraph_rag import settings
from codexgraph_rag.profile_runtime import (
    artifact_hints as _profile_artifact_hints,
    category_artifact_defaults as _profile_category_artifact_defaults,
    category_tuning as _profile_category_tuning,
    stopwords as _profile_stopwords,
)
from graph_retrieval import calculate_retrieval_score, iter_graph_neighbors
from question_classifier import QuestionClassification, normalize_question_text

logger = logging.getLogger(__name__)

ADAPTIVE_MAX_QUERY_VARIANTS = int(os.getenv("ADAPTIVE_MAX_QUERY_VARIANTS", "10"))
ADAPTIVE_MAX_GRAPH_DEPTH = int(os.getenv("ADAPTIVE_MAX_GRAPH_DEPTH", "2"))
ADAPTIVE_MAX_GRAPH_EXPANSIONS = int(os.getenv("ADAPTIVE_MAX_GRAPH_EXPANSIONS", "30"))
ADAPTIVE_MIN_GRAPH_SCORE = float(os.getenv("ADAPTIVE_MIN_GRAPH_SCORE", "0.25"))
ADAPTIVE_MAX_FINAL_NODES = int(os.getenv("ADAPTIVE_MAX_FINAL_NODES", "24"))


def _category_min_graph_score(category: str) -> float:
    tuning = _profile_category_tuning(settings.profile)
    return float(tuning.get(category, {}).get("min_score", 0.35))


def _category_max_final_nodes(category: str) -> int:
    tuning = _profile_category_tuning(settings.profile)
    return int(tuning.get(category, {}).get("max_nodes", 24))


def _category_max_expansions(category: str) -> int:
    tuning = _profile_category_tuning(settings.profile)
    return int(tuning.get(category, {}).get("max_expansions", 12))


def _category_max_depth(category: str) -> int:
    tuning = _profile_category_tuning(settings.profile)
    return int(tuning.get(category, {}).get("max_depth", 2))


_ENTITY_RE = re.compile(r"[A-Za-z0-9_]{3,}")

_ENTITY_STOPWORDS = _profile_stopwords(settings.profile)

_ARTIFACT_HINTS = _profile_artifact_hints(settings.profile)

_CATEGORY_ARTIFACT_DEFAULTS = _profile_category_artifact_defaults(settings.profile)
if not _CATEGORY_ARTIFACT_DEFAULTS:
    _CATEGORY_ARTIFACT_DEFAULTS = {
        "sql_dados": ["sql", "tables"],
        "erro": ["messages", "flow"],
        "parametro": ["parameters", "flow"],
        "tecnico": ["flow"],
        "funcional": ["flow"],
        "tela": ["flow"],
    }


@dataclass
class RetrievalIntent:
    standalone_question: str
    entities: list[str] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    query_terms: list[str] = field(default_factory=list)
    context_snippet: str = ""


@dataclass
class GraphPathEvidence:
    source_node_id: str
    target_node_id: str
    relation: str
    edge_confidence: str
    depth: int
    reason: str


@dataclass
class RetrievalGapReport:
    lacuna_score: float
    missing_repos: list[str]
    missing_artifacts: list[str]
    repo_coverage: float
    artifact_coverage: float
    confidence: float
    needs_deeper_search: bool


@dataclass
class RetrievalSessionState:
    topic_summary: str = ""
    history_entities: list[str] = field(default_factory=list)
    explored_node_ids: list[str] = field(default_factory=list)
    approved_node_ids: list[str] = field(default_factory=list)
    found_repos: list[str] = field(default_factory=list)
    query_lineage: list[str] = field(default_factory=list)
    unresolved_gaps: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict | None):
        payload = payload or {}
        return cls(
            topic_summary=str(payload.get("topic_summary") or ""),
            history_entities=list(payload.get("history_entities") or []),
            explored_node_ids=list(payload.get("explored_node_ids") or []),
            approved_node_ids=list(payload.get("approved_node_ids") or []),
            found_repos=list(payload.get("found_repos") or []),
            query_lineage=list(payload.get("query_lineage") or []),
            unresolved_gaps=list(payload.get("unresolved_gaps") or []),
        )

    def to_dict(self) -> dict:
        return {
            "topic_summary": self.topic_summary,
            "history_entities": self.history_entities,
            "explored_node_ids": self.explored_node_ids,
            "approved_node_ids": self.approved_node_ids,
            "found_repos": self.found_repos,
            "query_lineage": self.query_lineage,
            "unresolved_gaps": self.unresolved_gaps,
        }


@dataclass
class AdaptiveRetrievalResult:
    nodes: list[CodeNode]
    queries_used: list[str]
    gap_report: RetrievalGapReport
    intent: RetrievalIntent
    session_state: RetrievalSessionState
    path_evidences: list[GraphPathEvidence]


def _dedupe_keep_order(items: list[str], limit: int | None = None) -> list[str]:
    seen = set()
    result = []
    for item in items:
        normalized = normalize_question_text(str(item or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(str(item).strip())
        if limit and len(result) >= limit:
            break
    return result


def extract_history_text(chat_history: list[tuple[str, str]], window: int = 8) -> str:
    if not chat_history:
        return ""
    windowed = chat_history[-window:]
    return " ".join(text for _, text in windowed if text)


def extract_user_history_text(chat_history: list[tuple[str, str]], window: int = 6) -> str:
    if not chat_history:
        return ""
    only_user = [text for role, text in chat_history if role == "user" and text]
    if not only_user:
        return ""
    return " ".join(only_user[-window:])


def build_standalone_question(question: str, chat_history: list[tuple[str, str]], window: int = 8) -> str:
    question = (question or "").strip()
    if not question:
        return ""

    history = extract_user_history_text(chat_history, window=min(5, window)).strip()
    if not history:
        return question

    normalized = normalize_question_text(question)
    short_followup = len(normalized.split()) <= 8
    has_ellipsis_context = normalized.startswith(("e ", "isso", "esse", "essa", "nesse", "neste", "quando", "como"))
    if short_followup or has_ellipsis_context:
        return f"{question} contexto anterior: {history[:420]}"
    return question


def extract_entities(text: str, limit: int = 18) -> list[str]:
    raw_tokens = _ENTITY_RE.findall(text or "")
    entities = []
    for token in raw_tokens:
        normalized = normalize_question_text(token)
        if not normalized or normalized in _ENTITY_STOPWORDS:
            continue
        entities.append(token)
    return _dedupe_keep_order(entities, limit=limit)


def infer_expected_artifacts(question: str, category: str) -> list[str]:
    normalized = normalize_question_text(question)
    words = set(normalized.split())
    expected = set(_CATEGORY_ARTIFACT_DEFAULTS.get(category, []))
    for artifact, hints in _ARTIFACT_HINTS.items():
        if words & hints:
            expected.add(artifact)
    return sorted(expected)


def build_retrieval_intent(
    question: str,
    chat_history: list[tuple[str, str]],
    expected_repos: list[str],
    classification: QuestionClassification,
    session_state: RetrievalSessionState,
) -> RetrievalIntent:
    standalone_question = build_standalone_question(question, chat_history)
    history_text = extract_history_text(chat_history, window=6)
    merged_entities = (
        extract_entities(standalone_question)
        + extract_entities(history_text, limit=8)
        + session_state.history_entities[:8]
        + expected_repos
    )
    entities = _dedupe_keep_order(merged_entities, limit=24)
    expected_artifacts = infer_expected_artifacts(standalone_question, classification.category)
    query_terms = entities[:10]
    context_snippet = history_text[:240]
    return RetrievalIntent(
        standalone_question=standalone_question,
        entities=entities,
        expected_artifacts=expected_artifacts,
        query_terms=query_terms,
        context_snippet=context_snippet,
    )


def generate_adaptive_queries(
    *,
    base_question: str,
    intent: RetrievalIntent,
    expected_repos: list[str],
    missing_repos: list[str],
    missing_artifacts: list[str],
    session_state: RetrievalSessionState,
    max_variants: int = ADAPTIVE_MAX_QUERY_VARIANTS,
) -> list[str]:
    queries = [base_question.strip()]
    if intent.context_snippet:
        queries.append(f"{base_question} contexto: {intent.context_snippet}")
    if intent.query_terms:
        queries.append(f"{base_question} entidades: {' '.join(intent.query_terms[:6])}")
    if expected_repos:
        queries.append(f"{base_question} repos: {' '.join(expected_repos)}")
    for repo in missing_repos:
        queries.append(f"{base_question} foco repo {repo} classes metodos fluxo")
    for artifact in missing_artifacts:
        queries.append(f"{base_question} foco evidencia {artifact}")
    for gap in session_state.unresolved_gaps[:3]:
        queries.append(f"{base_question} lacuna anterior: {gap}")

    deduped = _dedupe_keep_order(queries)
    return deduped[:max_variants]


def _artifact_flags(node: CodeNode) -> set[str]:
    text = normalize_question_text(getattr(node, "code", "") or "")
    flags = set()
    if any(token in text for token in ("select", "insert", "update", "delete", " join ", " from ")):
        flags.add("sql")
    if any(token in text for token in (" table", "tabela", "coluna", "campo", " from ", " join ")):
        flags.add("tables")
    if any(token in text for token in ("erro", "falha", "exception", "throw", "mensagem")):
        flags.add("messages")
    if any(token in text for token in ("param", "config", "flag", "propriedade")):
        flags.add("parameters")
    if any(token in text for token in ("permiss", "acesso", "autoriz")):
        flags.add("permissions")
    if any(token in text for token in ("process", "fluxo", "integr", "call", "execut")):
        flags.add("flow")
    return flags


def _average_score(nodes: list[CodeNode]) -> float:
    if not nodes:
        return 0.0
    return round(sum(float(getattr(node, "retrieval_score", 0.0) or 0.0) for node in nodes) / len(nodes), 4)


def assess_gap_report(
    *,
    expected_repos: list[str],
    expected_artifacts: list[str],
    nodes: list[CodeNode],
    deep_threshold: float,
) -> tuple[RetrievalGapReport, list[str]]:
    found_repos = sorted({str(getattr(node, "source_repo", "") or "") for node in nodes if getattr(node, "source_repo", "")})
    missing_repos = sorted(set(expected_repos) - set(found_repos))

    covered_artifacts = set()
    for node in nodes:
        covered_artifacts.update(_artifact_flags(node))
    missing_artifacts = sorted(set(expected_artifacts) - covered_artifacts)

    repo_coverage = 1.0 if not expected_repos else (len(set(expected_repos) & set(found_repos)) / len(set(expected_repos)))
    artifact_coverage = 1.0 if not expected_artifacts else (len(set(expected_artifacts) & covered_artifacts) / len(set(expected_artifacts)))
    confidence = max(0.0, min(1.0, _average_score(nodes)))
    lacuna = 1.0 - ((repo_coverage * 0.45) + (confidence * 0.35) + (artifact_coverage * 0.20))
    lacuna = round(max(0.0, min(1.0, lacuna)), 4)
    needs_deeper = lacuna >= deep_threshold or bool(missing_repos) or bool(missing_artifacts)
    report = RetrievalGapReport(
        lacuna_score=lacuna,
        missing_repos=missing_repos,
        missing_artifacts=missing_artifacts,
        repo_coverage=round(repo_coverage, 4),
        artifact_coverage=round(artifact_coverage, 4),
        confidence=round(confidence, 4),
        needs_deeper_search=needs_deeper,
    )
    found_artifacts = sorted(covered_artifacts)
    return report, found_artifacts


def _build_node_from_graph(
    code_graph,
    node_id: str,
    *,
    depth: int,
    is_seed: bool,
    retrieval_score: float,
    relation: str,
    edge_confidence: str,
    source_reason: str,
) -> CodeNode:
    nd = code_graph.nodes[node_id]
    return CodeNode(
        node_id=node_id,
        file_path=nd.get("file_path", "N/A"),
        type=nd.get("type", "N/A"),
        name=nd.get("name", "N/A"),
        code=nd.get("code", ""),
        depth=depth,
        is_seed=is_seed,
        retrieval_score=round(max(0.0, min(1.0, retrieval_score)), 4),
        retrieval_confidence="alta" if retrieval_score >= 0.72 else ("media" if retrieval_score >= 0.45 else "baixa"),
        question_category="geral",
        relation=relation,
        edge_confidence=edge_confidence,
        source_reason=source_reason,
        source_repo=nd.get("source_repo", "unknown"),
        source_commit=nd.get("source_commit", "unknown"),
        relative_file_path=nd.get("relative_file_path", ""),
        line_start=nd.get("line_start", 0),
        line_end=nd.get("line_end", 0),
    )


def merge_code_nodes(existing: dict[str, CodeNode], incoming: list[CodeNode]) -> None:
    for node in incoming or []:
        previous = existing.get(node.node_id)
        prev_score = getattr(previous, "retrieval_score", 0.0) if previous else -1.0
        current_score = getattr(node, "retrieval_score", 0.0)
        if previous is None or current_score >= prev_score:
            existing[node.node_id] = node


def rerank_nodes(
    nodes: list[CodeNode],
    expected_repos: list[str],
    max_nodes: int = ADAPTIVE_MAX_FINAL_NODES,
    min_score: float = ADAPTIVE_MIN_GRAPH_SCORE,
) -> list[CodeNode]:
    if not nodes:
        return []

    expected = set(expected_repos)
    file_counts: dict[str, int] = {}
    scored = []
    for node in nodes:
        file_path = str(getattr(node, "file_path", "") or "")
        file_count = file_counts.get(file_path, 0)
        file_counts[file_path] = file_count + 1

        score = float(getattr(node, "retrieval_score", 0.0) or 0.0)
        if getattr(node, "is_seed", False):
            score += 0.10
        if str(getattr(node, "source_repo", "") or "") in expected:
            score += 0.06
        score -= min(0.12, file_count * 0.04)
        scored.append((round(score, 4), node))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = []
    selected_ids = set()

    if expected:
        for repo in sorted(expected):
            for _, node in scored:
                if node.node_id in selected_ids:
                    continue
                if str(getattr(node, "source_repo", "") or "") == repo:
                    selected.append(node)
                    selected_ids.add(node.node_id)
                    break

    for node_score, node in scored:
        if node.node_id in selected_ids:
            continue
        if node_score < min_score and str(getattr(node, "source_repo", "") or "") not in expected:
            continue
        selected.append(node)
        selected_ids.add(node.node_id)
        if len(selected) >= max_nodes:
            break
    return selected[:max_nodes]


def expand_nodes_with_graph(
    *,
    code_graph,
    nodes: list[CodeNode],
    classification: QuestionClassification,
    expected_repos: list[str],
    intent: RetrievalIntent,
    session_state: RetrievalSessionState,
    max_depth: int = ADAPTIVE_MAX_GRAPH_DEPTH,
    max_expansions: int = ADAPTIVE_MAX_GRAPH_EXPANSIONS,
    min_score: float = ADAPTIVE_MIN_GRAPH_SCORE,
) -> tuple[list[CodeNode], list[GraphPathEvidence]]:
    if not code_graph or not nodes:
        return nodes, []

    node_map = {node.node_id: node for node in nodes}
    visited = set(node_map.keys()) | set(session_state.explored_node_ids)
    expected_set = set(expected_repos)
    path_evidences: list[GraphPathEvidence] = []

    frontier: list[tuple[float, str, int, float]] = []
    for node in nodes:
        base_score = float(getattr(node, "retrieval_score", 0.0) or 0.0)
        frontier.append((-base_score, node.node_id, int(getattr(node, "depth", 0) or 0), base_score))
    frontier.sort(key=lambda item: item[0])

    expansions = 0
    while frontier and expansions < max_expansions:
        _, node_id, depth, parent_score = frontier.pop(0)
        if depth >= max_depth:
            continue

        for neighbor_id, relation, edge_confidence, reason in iter_graph_neighbors(code_graph, node_id):
            if neighbor_id in visited or not code_graph.has_node(neighbor_id):
                continue

            node_data = code_graph.nodes[neighbor_id]
            searchable = normalize_question_text(
                " ".join(
                    [
                        str(node_data.get("name", "")),
                        str(node_data.get("class_name", "")),
                        str(node_data.get("method_name", "")),
                        str(node_data.get("file_path", "")),
                    ]
                )
            )
            entity_boost = 0.04 if any(normalize_question_text(entity) in searchable for entity in intent.entities[:8]) else 0.0
            repo_boost = 0.05 if str(node_data.get("source_repo", "") or "") in expected_set else 0.0
            category_boost = entity_boost + repo_boost
            candidate_score = calculate_retrieval_score(parent_score, depth + 1, relation, edge_confidence, category_boost)
            if candidate_score < min_score:
                continue

            candidate = _build_node_from_graph(
                code_graph,
                neighbor_id,
                depth=depth + 1,
                is_seed=False,
                retrieval_score=candidate_score,
                relation=relation,
                edge_confidence=edge_confidence,
                source_reason=f"graph_walk:{reason}",
            )
            candidate.question_category = classification.category
            node_map[neighbor_id] = candidate
            visited.add(neighbor_id)
            frontier.append((-candidate_score, neighbor_id, depth + 1, candidate_score))
            frontier.sort(key=lambda item: item[0])
            path_evidences.append(
                GraphPathEvidence(
                    source_node_id=node_id,
                    target_node_id=neighbor_id,
                    relation=relation,
                    edge_confidence=edge_confidence,
                    depth=depth + 1,
                    reason=reason,
                )
            )
            expansions += 1
            if expansions >= max_expansions:
                break

    return list(node_map.values()), path_evidences


def update_session_state(
    *,
    session_state: RetrievalSessionState,
    question: str,
    intent: RetrievalIntent,
    nodes: list[CodeNode],
    queries_used: list[str],
    gap_report: RetrievalGapReport,
) -> RetrievalSessionState:
    found_repos = sorted({str(getattr(node, "source_repo", "") or "") for node in nodes if getattr(node, "source_repo", "")})
    ranked_nodes = sorted(nodes, key=lambda node: float(getattr(node, "retrieval_score", 0.0) or 0.0), reverse=True)

    session_state.topic_summary = (intent.standalone_question or question or "")[:240]
    session_state.history_entities = _dedupe_keep_order(session_state.history_entities + intent.entities, limit=60)
    session_state.explored_node_ids = _dedupe_keep_order(session_state.explored_node_ids + [node.node_id for node in nodes], limit=600)
    session_state.approved_node_ids = _dedupe_keep_order(
        session_state.approved_node_ids + [node.node_id for node in ranked_nodes[:40]],
        limit=160,
    )
    session_state.found_repos = _dedupe_keep_order(session_state.found_repos + found_repos, limit=40)
    session_state.query_lineage = _dedupe_keep_order(session_state.query_lineage + queries_used, limit=120)
    unresolved = [f"repo:{repo}" for repo in gap_report.missing_repos] + [f"artifact:{artifact}" for artifact in gap_report.missing_artifacts]
    session_state.unresolved_gaps = _dedupe_keep_order(unresolved, limit=80)
    return session_state


async def run_adaptive_code_retrieval(
    *,
    question: str,
    chat_history: list[tuple[str, str]],
    classification: QuestionClassification,
    expected_repos: list[str],
    retrieve_code_fn,
    session_state: dict | RetrievalSessionState | None,
    code_graph=None,
    max_rounds: int = 2,
    deep_threshold: float = 0.35,
    query_hint_prefix: str = "adaptive",
) -> AdaptiveRetrievalResult:
    state = session_state if isinstance(session_state, RetrievalSessionState) else RetrievalSessionState.from_dict(session_state)
    intent = build_retrieval_intent(question, chat_history, expected_repos, classification, state)
    merged_nodes: dict[str, CodeNode] = {}
    queries_used: list[str] = []
    path_evidences: list[GraphPathEvidence] = []
    gap_report, _ = assess_gap_report(
        expected_repos=expected_repos,
        expected_artifacts=intent.expected_artifacts,
        nodes=[],
        deep_threshold=deep_threshold,
    )

    max_variants = max(1, max(max_rounds, ADAPTIVE_MAX_QUERY_VARIANTS))
    category = classification.category
    base_min_score = _category_min_graph_score(category)
    if len(set(expected_repos)) >= 3:
        base_min_score = max(0.22, base_min_score - 0.02)
    effective_min_score = float(os.getenv("ADAPTIVE_MIN_GRAPH_SCORE", str(base_min_score)))
    effective_max_nodes = int(os.getenv("ADAPTIVE_MAX_FINAL_NODES", str(_category_max_final_nodes(category))))
    base_expansions = _category_max_expansions(category)
    if max_rounds >= 3:
        base_expansions = int(base_expansions * 1.25)
    effective_max_expansions = int(os.getenv("ADAPTIVE_MAX_GRAPH_EXPANSIONS", str(base_expansions)))
    base_depth = _category_max_depth(category)
    if max_rounds >= 3:
        base_depth = max(base_depth, 2)
    effective_depth = int(os.getenv("ADAPTIVE_MAX_GRAPH_DEPTH", str(base_depth)))

    variants = generate_adaptive_queries(
        base_question=intent.standalone_question or question,
        intent=intent,
        expected_repos=expected_repos,
        missing_repos=gap_report.missing_repos,
        missing_artifacts=gap_report.missing_artifacts,
        session_state=state,
        max_variants=max_variants,
    )

    for round_index in range(max_rounds):
        query = variants[round_index] if round_index < len(variants) else variants[-1]
        queries_used.append(query)
        code_nodes, _ = await retrieve_code_fn(
            query,
            classification,
            preferred_repos=expected_repos,
            required_repos=expected_repos,
            query_hint=f"{query_hint_prefix}_round_{round_index + 1}",
        )
        merge_code_nodes(merged_nodes, code_nodes)

        current_nodes = list(merged_nodes.values())
        expanded_nodes, new_paths = expand_nodes_with_graph(
            code_graph=code_graph,
            nodes=current_nodes,
            classification=classification,
            expected_repos=expected_repos,
            intent=intent,
            session_state=state,
            max_depth=effective_depth,
            max_expansions=effective_max_expansions,
            min_score=effective_min_score,
        )
        merge_code_nodes(merged_nodes, expanded_nodes)
        path_evidences.extend(new_paths)

        ranked_nodes = rerank_nodes(
            list(merged_nodes.values()),
            expected_repos=expected_repos,
            max_nodes=effective_max_nodes,
            min_score=effective_min_score,
        )
        gap_report, _ = assess_gap_report(
            expected_repos=expected_repos,
            expected_artifacts=intent.expected_artifacts,
            nodes=ranked_nodes,
            deep_threshold=deep_threshold,
        )

        logger.info(
            "Adaptive retrieval round=%s/%s query=%s nodes=%s repos_missing=%s artifacts_missing=%s lacuna=%.4f",
            round_index + 1,
            max_rounds,
            query,
            len(ranked_nodes),
            gap_report.missing_repos,
            gap_report.missing_artifacts,
            gap_report.lacuna_score,
        )

        if not gap_report.needs_deeper_search:
            break

        if round_index + 1 < max_rounds:
            variants = generate_adaptive_queries(
                base_question=intent.standalone_question or question,
                intent=intent,
                expected_repos=expected_repos,
                missing_repos=gap_report.missing_repos,
                missing_artifacts=gap_report.missing_artifacts,
                session_state=state,
                max_variants=max_variants,
            )

    final_nodes = rerank_nodes(
        list(merged_nodes.values()),
        expected_repos=expected_repos,
        max_nodes=effective_max_nodes,
        min_score=effective_min_score,
    )
    gap_report, _ = assess_gap_report(
        expected_repos=expected_repos,
        expected_artifacts=intent.expected_artifacts,
        nodes=final_nodes,
        deep_threshold=deep_threshold,
    )
    state = update_session_state(
        session_state=state,
        question=question,
        intent=intent,
        nodes=final_nodes,
        queries_used=queries_used,
        gap_report=gap_report,
    )

    return AdaptiveRetrievalResult(
        nodes=final_nodes,
        queries_used=queries_used,
        gap_report=gap_report,
        intent=intent,
        session_state=state,
        path_evidences=path_evidences,
    )
