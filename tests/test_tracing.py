import pytest

from app.core import tracing


def test_diam_total_tanpa_key() -> None:
    assert tracing.aktif() is False or tracing.LANGFUSE_PUBLIC


def test_ukur_mencatat_lama_node() -> None:
    @tracing.ukur("retrieve")
    def node(state: dict[str, object]) -> dict[str, object]:
        return {"hasil": 1}

    keluar = node({})
    assert keluar["hasil"] == 1
    jejak = keluar["trace"]
    assert isinstance(jejak, list) and jejak[0]["node"] == "retrieve"  # type: ignore[index]
    assert jejak[0]["ms"] >= 0  # type: ignore[index]


def test_node_gagal_melempar_error_aslinya() -> None:
    @tracing.ukur("generate")
    def node(state: dict[str, object]) -> dict[str, object]:
        raise ValueError("rusak")

    with pytest.raises(ValueError, match="rusak"):
        node({})


def test_tiap_node_punya_tipe_observasi() -> None:
    from app.agents.graph import bangun

    node_graph = {n for n in bangun().get_graph().nodes if not n.startswith("__")}
    assert node_graph <= set(tracing.TIPE_NODE), (
        f"node tanpa tipe observasi: {node_graph - set(tracing.TIPE_NODE)}"
    )
    assert tracing.TIPE_NODE["retrieve"] == "retriever"
    assert tracing.TIPE_NODE["verify"] == "evaluator"


def test_usage_membaca_token_google_genai() -> None:
    class Palsu:
        prompt_token_count = 5
        candidates_token_count = 9
        total_token_count = 14

    class Resp:
        usage_metadata = Palsu()

    assert tracing.usage(Resp()) == {"input": 5, "output": 9, "total": 14}
    assert tracing.usage(object()) == {}


def test_generation_tidak_meledak_tanpa_langfuse() -> None:
    with tracing.generation("uji", "model-x", {"a": 1}) as g:
        g.update(output="apa pun", usage_details={"input": 1})


def test_permintaan_tidak_meledak_tanpa_langfuse() -> None:
    with tracing.permintaan("pertanyaan") as akar:
        tracing.tutup(akar, "pertanyaan", {"answer": "x", "trace": []})
