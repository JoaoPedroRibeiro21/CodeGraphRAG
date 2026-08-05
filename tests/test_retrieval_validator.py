from retrieval_validator import build_validated_pdf_context, validate_pdf_evidence


class FakeDoc:
    def __init__(self, content: str, metadata: dict):
        self.page_content = content
        self.metadata = metadata


def test_validate_pdf_evidence_approves_relevant_and_rejects_unrelated():
    question = "como configurar contingencia SAT NFCe no PDV"
    relevant_doc = FakeDoc(
        "Para configurar contingencia SAT e NFCe no PDV, acesse parametros fiscais e habilite contingencia.",
        {"arquivo_fonte": "contingencia_sat_nfce.txt", "page": 0},
    )
    unrelated_doc = FakeDoc(
        "Esse material fala sobre carta de cobranca e personalizacao de layout financeiro.",
        {"arquivo_fonte": "carta_cobranca.txt", "page": 2},
    )

    result = validate_pdf_evidence(
        question=question,
        docs_and_scores=[(relevant_doc, 0.81), (unrelated_doc, 0.79)],
        max_results=5,
    )

    assert len(result.approved) == 1
    assert result.approved[0].source_label == "contingencia_sat_nfce.txt"
    assert result.rejected_count == 1


def test_validate_pdf_evidence_returns_empty_when_no_chunk_is_confident():
    question = "como emitir cupom fiscal no PDV"
    weak_doc = FakeDoc(
        "Conteudo institucional sem instrucoes operacionais do processo citado.",
        {"arquivo_fonte": "institucional.txt"},
    )

    result = validate_pdf_evidence(question=question, docs_and_scores=[(weak_doc, 0.42)], max_results=3)

    assert result.approved == []
    assert result.rejected_count == 1


def test_build_validated_pdf_context_includes_source_page_and_excerpt():
    doc = FakeDoc(
        "A rotina de fechamento de caixa deve ser executada ao final do expediente no menu de fechamento.",
        {"arquivo_fonte": "fechamento_pdv.txt", "page": 4},
    )
    result = validate_pdf_evidence(
        question="como fazer fechamento de caixa no pdv",
        docs_and_scores=[(doc, 0.87)],
        max_results=3,
    )

    context = build_validated_pdf_context(result.approved)

    assert "fonte: fechamento_pdv.txt" in context
    assert "pagina: 5" in context
    assert "Trecho:" in context
