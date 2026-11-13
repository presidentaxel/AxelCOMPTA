from __future__ import annotations

from datetime import datetime

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.workflow.decisions import AnnotationDev, DecisionHumaine
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository

DOSSIER = DossierId("d1")
ECRITURE = EcritureId("e1")
GESTIONNAIRE = UserId("u_sophie_gestionnaire")


def _decision(categorie: str, decide_le: datetime) -> DecisionHumaine:
    return DecisionHumaine(
        dossier_id=DOSSIER,
        ecriture_id=ECRITURE,
        categorie=categorie,
        etage_origine=Etage.REVUE_HUMAINE,
        confiance_origine=0.0,
        decide_par=GESTIONNAIRE,
        decide_le=decide_le,
    )


def test_decision_courante_absente_tant_que_rien_nest_enregistre() -> None:
    repo = InMemoryDecisionRepository()
    assert repo.decision_courante(DOSSIER, ECRITURE) is None


def test_une_decision_enregistree_devient_la_decision_courante() -> None:
    repo = InMemoryDecisionRepository()
    decision = _decision("usage_personnel", datetime(2026, 9, 7, 10, 0))
    repo.enregistrer_decision(decision)
    assert repo.decision_courante(DOSSIER, ECRITURE) == decision


def test_une_nouvelle_decision_devient_courante_sans_effacer_lhistorique() -> None:
    """Immutabilité (doc 17 §9 bloc A) : corriger, c'est ajouter, jamais muter."""
    repo = InMemoryDecisionRepository()
    premiere = _decision("usage_personnel", datetime(2026, 9, 7, 10, 0))
    seconde = _decision("fournitures_administratives", datetime(2026, 9, 7, 11, 0))
    repo.enregistrer_decision(premiere)
    repo.enregistrer_decision(seconde)

    assert repo.decision_courante(DOSSIER, ECRITURE) == seconde
    assert repo.lister_decisions(DOSSIER) == (premiere, seconde)


def test_lister_decisions_est_isole_par_dossier() -> None:
    repo = InMemoryDecisionRepository()
    autre_dossier = DossierId("d2")
    ici = _decision("usage_personnel", datetime(2026, 9, 7, 10, 0))
    ailleurs = DecisionHumaine(
        dossier_id=autre_dossier,
        ecriture_id=ECRITURE,
        categorie="carburant",
        etage_origine=Etage.REVUE_HUMAINE,
        confiance_origine=0.0,
        decide_par=GESTIONNAIRE,
        decide_le=datetime(2026, 9, 7, 10, 0),
    )
    repo.enregistrer_decision(ici)
    repo.enregistrer_decision(ailleurs)

    assert repo.lister_decisions(DOSSIER) == (ici,)
    assert repo.lister_decisions(autre_dossier) == (ailleurs,)


def test_une_annotation_dev_ne_change_pas_la_decision_courante() -> None:
    """doc 05 §5 : l'annotation dev est un jugement séparé, jamais une
    réécriture de la décision humaine."""
    repo = InMemoryDecisionRepository()
    decision = _decision("usage_personnel", datetime(2026, 9, 7, 10, 0))
    repo.enregistrer_decision(decision)

    annotation = AnnotationDev(
        dossier_id=DOSSIER,
        ecriture_id=ECRITURE,
        juste=False,
        note="Devrait être fournitures_administratives, pas usage_personnel",
        annote_par=UserId("u_dev_claude"),
        annote_le=datetime(2026, 9, 8, 9, 0),
    )
    repo.enregistrer_annotation(annotation)

    assert repo.decision_courante(DOSSIER, ECRITURE) == decision
    assert repo.lister_annotations(DOSSIER) == (annotation,)


def test_la_nature_dit_si_l_humain_a_suivi_la_proposition() -> None:
    """AXE-871."""
    from axelcompta.workflow.decisions import (
        NATURE_CONFIRMEE,
        NATURE_CORRIGEE,
        NATURE_SANS_PROPOSITION,
        nature_decision,
    )

    assert nature_decision("carburant", "carburant") == NATURE_CONFIRMEE
    assert nature_decision("peage_stationnement", "carburant") == NATURE_CORRIGEE
    assert nature_decision("non_categorise_a_verifier", "carburant") == NATURE_SANS_PROPOSITION
    assert nature_decision(None, "carburant") == NATURE_SANS_PROPOSITION


def test_le_contexte_se_relit_a_l_identique() -> None:
    from axelcompta.workflow.decisions import ContexteDecision

    contexte = ContexteDecision("CB TOTAL", -6000, "card", "carburant", "REGLE", 0.95, "confirmee")
    assert ContexteDecision.depuis_dict(contexte.en_dict()) == contexte
