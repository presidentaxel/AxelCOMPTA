"""AXE-901 : l'avis de chaque étage, gardé avec la décision humaine."""

from __future__ import annotations

from datetime import UTC, datetime

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.rules_and_ml import CATEGORIE_PAR_DEFAUT
from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.workflow.avis_etages import avis_etages, proposition_affichee
from axelcompta.workflow.decisions import ContexteDecision
from axelcompta.workflow.propositions_ia import PropositionIa

D = DossierId("d")


def _synchro(categorie: str, etage: Etage, confiance: float = 0.9) -> ProposedEntry:
    return ProposedEntry(D, TransactionId("t"), categorie, etage, confiance)


def _ia(categorie: str) -> PropositionIa:
    return PropositionIa(
        D,
        "cle",
        "v1",
        categorie,
        0.8,
        "café",
        "claude-fable-5-2",
        datetime(2026, 11, 12, tzinfo=UTC),
    )


def test_une_regle_passe_avant_l_ia() -> None:
    affichee = proposition_affichee(_synchro("carburant", Etage.REGLE), _ia("repas_et_receptions"))
    assert affichee == ("carburant", "REGLE", 0.9)


def test_l_ia_passe_avant_le_modele() -> None:
    affichee = proposition_affichee(_synchro("peage_stationnement", Etage.ML), _ia("repas"))
    assert affichee == ("repas", "LLM", 0.8)


def test_une_ia_qui_ne_sait_pas_laisse_la_synchro() -> None:
    affichee = proposition_affichee(
        _synchro(CATEGORIE_PAR_DEFAUT, Etage.ML, 0.1), _ia("non_categorise_a_verifier")
    )
    assert affichee == (CATEGORIE_PAR_DEFAUT, "ML", 0.1)


def test_chaque_avis_est_garde_meme_non_affiche() -> None:
    avis = avis_etages(_synchro("carburant", Etage.REGLE), _ia("repas"))
    assert avis["synchro"]["categorie"] == "carburant"
    assert avis["ia"] == {
        "categorie": "repas",
        "confiance": 0.8,
        "justification": "café",
        "modele": "claude-fable-5-2",
        "version": "v1",
    }
    assert "ia" not in avis_etages(_synchro("carburant", Etage.REGLE), None)


def test_le_contexte_relit_ses_avis_et_les_anciens_sans_avis() -> None:
    contexte = ContexteDecision("x", -100, None, "a", "REGLE", 0.9, "confirmee", {"ia": {"c": 1}})
    assert ContexteDecision.depuis_dict(contexte.en_dict()) == contexte
    ancien = {k: v for k, v in contexte.en_dict().items() if k != "avis"}
    assert ContexteDecision.depuis_dict(ancien).avis == {}
