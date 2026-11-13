"""AXE-887 : l'API Batch derrière `FournisseurLotsAnthropic`, avec un faux client."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from axelcompta.core.ids import DossierId
from axelcompta.pseudonymize.fournisseur_anthropic import FournisseurLotsAnthropic, RequeteLot
from axelcompta.pseudonymize.llm import JournalPrompts
from axelcompta.pseudonymize.prompt import PseudonymizedPrompt


class FauxBatches:
    def __init__(self, statut: str = "in_progress", resultats: list[Any] | None = None) -> None:
        self.creations: list[dict[str, Any]] = []
        self.statut = statut
        self.resultats = resultats or []

    def create(self, **kwargs: Any) -> Any:
        self.creations.append(kwargs)
        return SimpleNamespace(id="msgbatch_1")

    def retrieve(self, message_batch_id: str) -> Any:
        return SimpleNamespace(processing_status=self.statut)

    def results(self, message_batch_id: str) -> Any:
        return iter(self.resultats)


def _usage() -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=100,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=900,
        output_tokens=50,
    )


def _succes(custom_id: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    message = SimpleNamespace(
        stop_reason=stop_reason,
        usage=_usage(),
        content=[SimpleNamespace(type="text", text='{"propositions": []}')],
    )
    return SimpleNamespace(
        custom_id=custom_id, result=SimpleNamespace(type="succeeded", message=message)
    )


def _fournisseur(batches: FauxBatches, journal: JournalPrompts) -> FournisseurLotsAnthropic:
    return FournisseurLotsAnthropic({"type": "object"}, "CONSIGNES", journal, lots=batches)


def test_chaque_requete_porte_les_consignes_en_cache_et_la_sortie_json_stricte() -> None:
    batches, journal = FauxBatches(), JournalPrompts()
    prompt = PseudonymizedPrompt(DossierId("d1"), "Opérations :\n[]", ())
    batch_id = _fournisseur(batches, journal).soumettre([RequeteLot("lot-1", prompt, 1_120)])
    assert batch_id == "msgbatch_1"
    ((requete,),) = (batches.creations[0]["requests"],)
    params = requete["params"]
    assert requete["custom_id"] == "lot-1"
    assert params["model"] == "claude-fable-5-2" and params["max_tokens"] == 1_120
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert params["output_config"]["effort"] == "low"
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert "fallbacks" not in params  # refusé par l'API Batch
    assert [e.prompt for e in journal.entrees] == ["Opérations :\n[]"]


def test_rien_n_est_releve_tant_que_le_lot_n_est_pas_fini() -> None:
    assert _fournisseur(FauxBatches(), JournalPrompts()).relever("msgbatch_1") is None


def test_succes_refus_et_erreur_sont_distingues() -> None:
    erreur = SimpleNamespace(custom_id="c", result=SimpleNamespace(type="errored"))
    batches = FauxBatches("ended", [_succes("a"), _succes("b", stop_reason="refusal"), erreur])
    resultats = _fournisseur(batches, JournalPrompts()).relever("msgbatch_1")
    assert resultats is not None
    a, b, c = resultats
    assert (a.statut, a.entree, a.sortie, a.cache) == ("termine", 1_000, 50, 900)
    assert a.texte == '{"propositions": []}'
    assert b.statut == "refus" and b.texte == ""
    assert c.statut == "echec"
