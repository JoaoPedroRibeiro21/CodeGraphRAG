import asyncio

import networkx as nx

from adaptive_retrieval import (
    RetrievalSessionState,
    build_retrieval_intent,
    run_adaptive_code_retrieval,
)
from code_analysis_pipeline import CodeNode
from question_classifier import QuestionClassification


def test_build_retrieval_intent_uses_history_for_followup_question():
    classification = QuestionClassification("tecnico", 0.9, "teste")
    state = RetrievalSessionState(history_entities=["Autorizador"])
    intent = build_retrieval_intent(
        question="E quando falha?",
        chat_history=[("user", "Como funciona autorizacao no PDV?")],
        expected_repos=["VRPdv", "VRAutorizador"],
        classification=classification,
        session_state=state,
    )

    assert "contexto anterior" in intent.standalone_question.lower()
    assert any(entity.lower() == "autorizador" for entity in intent.entities)
    assert "flow" in intent.expected_artifacts


def test_run_adaptive_code_retrieval_expands_graph_neighbors():
    graph = nx.DiGraph()
    graph.add_node("A", type="method", name="A", code="void a(){ b(); }", file_path="A.java", source_repo="VRPdv")
    graph.add_node("B", type="method", name="B", code="void b(){ c(); }", file_path="B.java", source_repo="VRAutorizador")
    graph.add_node("C", type="method", name="C", code="select * from venda", file_path="C.java", source_repo="VRMaster")
    graph.add_edge("A", "B", type="CALLS", confidence="high", reason="typed_variable_or_field")
    graph.add_edge("B", "C", type="CALLS", confidence="medium", reason="contextual")

    async def fake_retrieve_code_fn(query, classification, preferred_repos, required_repos, query_hint):
        nodes = [
            CodeNode(
                node_id="A",
                file_path="A.java",
                type="method",
                name="A",
                code="void a(){ b(); }",
                depth=0,
                is_seed=True,
                retrieval_score=0.9,
                source_repo="VRPdv",
            )
        ]
        return nodes, None

    result = asyncio.run(
        run_adaptive_code_retrieval(
            question="Fluxo de autorizacao no PDV",
            chat_history=[("user", "Fluxo de autorizacao")],
            classification=QuestionClassification("tecnico", 0.9, "teste"),
            expected_repos=["VRPdv", "VRAutorizador"],
            retrieve_code_fn=fake_retrieve_code_fn,
            session_state=None,
            code_graph=graph,
            max_rounds=2,
            deep_threshold=0.35,
        )
    )

    node_ids = {node.node_id for node in result.nodes}
    assert "A" in node_ids
    assert "B" in node_ids
    assert len(result.path_evidences) >= 1


def test_run_adaptive_code_retrieval_updates_session_state():
    async def fake_retrieve_code_fn(query, classification, preferred_repos, required_repos, query_hint):
        nodes = [
            CodeNode(
                node_id="VRPdv::Venda#fechar()",
                file_path="VRPdv/Venda.java",
                type="method",
                name="fechar()",
                code="void fechar(){}",
                depth=0,
                is_seed=True,
                retrieval_score=0.7,
                source_repo="VRPdv",
            )
        ]
        return nodes, None

    state = RetrievalSessionState(history_entities=["PDV"]).to_dict()
    result = asyncio.run(
        run_adaptive_code_retrieval(
            question="Fechamento do PDV",
            chat_history=[("user", "Preciso do fluxo")],
            classification=QuestionClassification("funcional", 0.9, "teste"),
            expected_repos=["VRPdv"],
            retrieve_code_fn=fake_retrieve_code_fn,
            session_state=state,
            code_graph=None,
            max_rounds=1,
            deep_threshold=0.35,
        )
    )

    snapshot = result.session_state.to_dict()
    assert snapshot["query_lineage"]
    assert "VRPdv::Venda#fechar()" in snapshot["approved_node_ids"]
    assert "VRPdv" in snapshot["found_repos"]
