"""AXE-420 : une décision humaine écrit une OD de reclassement."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.decisions import CATEGORIE_ANNULATION, DecisionHumaine
from axelcompta.workflow.reclassement import (
    annuler_reclassements,
    compte_en_vigueur,
    grand_livre_tranche,
    projeter,
    reclassements_a_reprendre,
    reclasser,
    source_du_reclassement,
)
from axelcompta.workflow.revue import appliquer_decisions

D = DossierId("d1")
COMPTES: tuple[dict[str, str | None], dict[str, str]] = (
    {"usage_personnel": "455"},
    {"carburant": "6061", "repas": "6257", "ca_vtc": "706"},
)


def _source(identifiant: str = "s1", montant: int = 60_00, sortie: bool = True) -> Ecriture:
    banque, attente = (Sens.CREDIT, Sens.DEBIT) if sortie else (Sens.DEBIT, Sens.CREDIT)
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="CB TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture("5121", banque, Money(montant)),
            LigneEcriture("471", attente, Money(montant)),
        ),
    )


def _decision(categorie: str, ecriture_id: str = "s1", minute: int = 0) -> DecisionHumaine:
    return DecisionHumaine(
        dossier_id=D,
        ecriture_id=EcritureId(ecriture_id),
        categorie=categorie,
        etage_origine=Etage.ML,
        confiance_origine=0.5,
        decide_par=UserId("chauffeur"),
        decide_le=datetime(2026, 3, 2, 9, minute, tzinfo=UTC),
    )


def _soldes(ecritures: tuple[Ecriture, ...] | list[Ecriture]) -> Counter[str]:
    soldes: Counter[str] = Counter()
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            signe = 1 if ligne.sens is Sens.DEBIT else -1
            soldes[ligne.compte] += signe * ligne.montant.centimes
    return Counter({compte: solde for compte, solde in soldes.items() if solde})


def _decider(ecritures: list[Ecriture], categorie: str) -> Ecriture | None:
    source = next(e for e in ecritures if e.id == "s1")
    reclassement = reclasser(source, categorie, ecritures, COMPTES)
    if reclassement is not None:
        verifier_equilibre(reclassement)
        ecritures.append(reclassement)
    return reclassement


def test_une_decision_ecrit_un_reclassement_equilibre_qui_ne_touche_pas_la_banque() -> None:
    ecritures = [_source()]
    reclassement = _decider(ecritures, "carburant")

    assert reclassement is not None
    assert reclassement.id == "s1:decision-1"
    assert (reclassement.journal, reclassement.reference_piece) == (Journal.OD, "s1")
    assert {ligne.compte for ligne in reclassement.lignes} == {"6061", "471"}
    assert _soldes(ecritures) == Counter({"6061": 60_00, "5121": -60_00})
    assert source_du_reclassement(reclassement.id) == "s1"


def test_une_correction_puis_une_annulation_deplacent_le_montant() -> None:
    ecritures = [_source()]
    _decider(ecritures, "carburant")
    _decider(ecritures, "repas")
    assert compte_en_vigueur(EcritureId("s1"), ecritures) == "6257"
    assert _soldes(ecritures) == Counter({"6257": 60_00, "5121": -60_00})

    _decider(ecritures, CATEGORIE_ANNULATION)

    assert compte_en_vigueur(EcritureId("s1"), ecritures) == "471"
    assert _soldes(ecritures) == Counter({"471": 60_00, "5121": -60_00})
    assert _decider(ecritures, CATEGORIE_ANNULATION) is None  # déjà en attente


def test_meme_compte_rien_a_ecrire() -> None:
    ecritures = [_source()]
    _decider(ecritures, "carburant")
    assert _decider(ecritures, "carburant") is None


def test_une_recette_se_reclasse_au_credit() -> None:
    ecritures = [_source(sortie=False, montant=848_00)]
    _decider(ecritures, "ca_vtc")
    assert _soldes(ecritures) == Counter({"5121": 848_00, "706": -848_00})


def test_les_soldes_bruts_egalent_ceux_de_l_ancienne_vue_recalculee() -> None:
    """Golden : FEC et liasse lisent le brut ; les montants par compte sont
    exactement ceux que donnait la couche de décisions."""
    decisions = [_decision("carburant", minute=1), _decision("repas", minute=2)]
    ecritures = [_source()]
    for decision in decisions:
        _decider(ecritures, decision.categorie)

    ancienne = appliquer_decisions((_source(),), tuple(decisions), *COMPTES)

    assert _soldes(ecritures) == _soldes(list(ancienne))
    assert _soldes(list(projeter(ecritures))) == _soldes(list(ancienne))


def test_la_projection_replie_les_reclassements_dans_l_operation() -> None:
    ecritures = [_source()]
    _decider(ecritures, "carburant")
    (vue,) = projeter(ecritures)
    assert vue.id == "s1"
    assert {ligne.compte for ligne in vue.lignes} == {"5121", "6061"}


def test_contre_passer_l_operation_contre_passe_ses_reclassements() -> None:
    """Synchro (opération modifiée) ou imputation de l'expert."""
    ecritures = [_source()]
    _decider(ecritures, "carburant")

    ecritures.append(contrepasser(ecritures[0]))
    ecritures.extend(annuler_reclassements(EcritureId("s1"), ecritures))

    assert _soldes(ecritures) == Counter()
    assert compte_en_vigueur(EcritureId("s1"), ecritures) == "471"
    assert annuler_reclassements(EcritureId("s1"), ecritures) == []  # rien de plus


def test_pendant_la_reprise_une_decision_pas_encore_ecrite_reste_appliquee() -> None:
    """Décision d'avant AXE-420 (aucun reclassement) : appliquée par-dessus.
    Dès qu'un reclassement existe, la couche ne l'applique plus (pas de double)."""
    ancienne = (_decision("carburant"),)
    (vue,) = grand_livre_tranche([_source()], ancienne, COMPTES)
    assert "6061" in {ligne.compte for ligne in vue.lignes}

    ecritures = [_source()]
    _decider(ecritures, "repas")
    (vue,) = grand_livre_tranche(ecritures, ancienne, COMPTES)
    assert {ligne.compte for ligne in vue.lignes} == {"5121", "6257"}


def test_la_reprise_rejoue_les_decisions_et_ne_se_repete_pas() -> None:
    decisions = [
        _decision("carburant", minute=1),
        _decision("repas", minute=2),
        _decision("carburant", "s2", minute=3),
    ]
    ecritures = [_source(), _source("s2")]

    reprises = reclassements_a_reprendre(ecritures, decisions, COMPTES)

    assert [r.id for r in reprises] == ["s1:decision-1", "s1:decision-2", "s2:decision-1"]
    ecritures.extend(reprises)
    assert compte_en_vigueur(EcritureId("s1"), ecritures) == "6257"
    assert reclassements_a_reprendre(ecritures, decisions, COMPTES) == []  # idempotent
    ancienne = appliquer_decisions((_source(), _source("s2")), tuple(decisions), *COMPTES)
    assert _soldes(ecritures) == _soldes(list(ancienne))
