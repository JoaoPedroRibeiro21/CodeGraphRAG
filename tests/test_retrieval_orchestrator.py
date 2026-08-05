import asyncio

from code_analysis_pipeline import CodeNode
from question_classifier import QuestionClassification, QuestionStrategy
from retrieval_orchestrator import infer_expected_repos, orchestrate_retrieval


def _strategy() -> QuestionStrategy:
    classification = QuestionClassification("tecnico", 0.9, "teste")
    return QuestionStrategy(
        classification=classification,
        fast_response=None,
        use_pdf_retrieval=True,
        use_code_retrieval=True,
        use_code_analysis=True,
        use_light_prompt=False,
        retrieval_effort="medio",
    )


def test_infer_expected_repos_detects_authorization_flow():
    from retrieval_orchestrator import DomainCard

    cards = [
        DomainCard(repo="pdv", aliases=("pdv", "venda", "caixa", "fechamento", "tef", "pix"), responsibilities=()),
        DomainCard(repo="autorizador", aliases=("autorizador", "autorizacao", "autorizar"), responsibilities=()),
        DomainCard(repo="core", aliases=("core", "erp", "parametro", "parametros", "configuracao"), responsibilities=()),
    ]
    question = "Falha de autorizacao no TEF/Pix no fechamento do PDV"
    repos = infer_expected_repos(question, [], cards)

    assert "pdv" in repos
    assert "autorizador" in repos


def test_orchestrator_escalates_to_deep_when_lacuna_is_high(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_DEEP_LACUNA_THRESHOLD", "0.35")
    monkeypatch.setenv("ORCHESTRATOR_MAX_ROUNDS_MEDIUM", "2")
    monkeypatch.setenv("ORCHESTRATOR_MAX_ROUNDS_DEEP", "3")

    calls = {"count": 0}

    async def fake_pdf(query, classification):
        return (f"contexto para {query}", [query])

    async def fake_code(query, classification, preferred_repos, required_repos, query_hint):
        calls["count"] += 1
        if calls["count"] == 1:
            return (
                [
                    CodeNode(
                        node_id="pdv::Venda#autorizar()",
                        file_path="pdv/Venda.java",
                        type="method",
                        name="autorizar()",
                        code="void autorizar() {}",
                        depth=0,
                        is_seed=True,
                        retrieval_score=0.35,
                        source_repo="pdv",
                    )
                ],
                None,
            )
        return (
            [
                CodeNode(
                    node_id="autorizador::Autorizador#processar()",
                    file_path="autorizador/Autorizador.java",
                    type="method",
                    name="processar()",
                    code="void processar() {}",
                    depth=0,
                    is_seed=True,
                    retrieval_score=0.8,
                    source_repo="autorizador",
                ),
                CodeNode(
                    node_id="core::Parametro#consultar()",
                    file_path="core/Parametro.java",
                    type="method",
                    name="consultar()",
                    code="select * from parametro",
                    depth=1,
                    is_seed=False,
                    retrieval_score=0.78,
                    source_repo="core",
                ),
            ],
            None,
        )

    result = asyncio.run(
        orchestrate_retrieval(
            question="Falha de autorizacao no pagamento TEF/Pix no PDV",
            chat_history=[("user", "quero analise tecnica")],
            strategy=_strategy(),
            retrieve_pdf_fn=fake_pdf,
            retrieve_code_fn=fake_code,
        )
    )

    assert result.escalated_to_deep is True
    assert result.rounds_executed >= 2
    assert "pdv" in result.found_repos
    assert "autorizador" in result.found_repos
    assert "core" in result.found_repos
    assert result.lacuna_score < 0.35
