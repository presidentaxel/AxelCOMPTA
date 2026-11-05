"""Affectation du résultat après la clôture, sur les dossiers de démo :
Karim (SASU, bénéfice) et Yanis (SASU, perte)."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

import pytest

from axelcompta import demo_seed
from axelcompta.affectations import AffectationImpossible, decider, proposer
from axelcompta.closing.cloture_fiscale import soldes
from axelcompta.core.ids import DossierId
from axelcompta.exercices import executer_passage, preparer_passage
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.tenants.affectations import InMemoryAffectationRepository
from axelcompta.tenants.exercices import InMemoryExerciceRepository
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository
from axelcompta.workflow.propositions import InMemoryPropositionRepository

AUJOURD_HUI = date(2026, 9, 26)
MAINTENANT = datetime(2026, 9, 26, 12, 0)
KARIM, YANIS = DossierId("DEMO_karim"), DossierId("DEMO_yanis")


class Demo:
    def __init__(self) -> None:
        self.dossiers = InMemoryDossierRepository()
        self.ledger = InMemoryLedgerService()
        self.exercices = InMemoryExerciceRepository()
        self.affectations = InMemoryAffectationRepository()
        demo_seed.amorcer_demo(self.dossiers, self.ledger, InMemoryPropositionRepository())

    def dossier(self, dossier_id: DossierId) -> Dossier:
        dossier = self.dossiers.obtenir(dossier_id)
        assert dossier is not None
        return dossier

    def clore(self, dossier_id: DossierId) -> None:
        dossier, decisions = self.dossier(dossier_id), InMemoryDecisionRepository()
        passage = preparer_passage(dossier, self.ledger, decisions, (), AUJOURD_HUI)
        executer_passage(passage, self.ledger, self.dossiers, self.exercices, MAINTENANT, "t")

    def proposer(self, dossier_id: DossierId):  # type: ignore[no-untyped-def]
        return proposer(
            self.dossier(dossier_id), self.ledger, self.exercices, self.affectations, AUJOURD_HUI
        )


def test_rien_a_affecter_tant_que_l_exercice_n_est_pas_clos() -> None:
    with pytest.raises(AffectationImpossible, match="Clôturez d'abord"):
        Demo().proposer(KARIM)


def test_karim_voit_son_benefice_2025_et_des_scenarios_bornes() -> None:
    demo = Demo()
    demo.clore(KARIM)

    proposition = demo.proposer(KARIM)

    assert proposition.annee_exercice == 2025
    assert proposition.situation.resultat > 0
    assert proposition.situation.annee_versement == 2026
    plafond = proposition.scenarios[-1].dividendes
    assert 0 < plafond <= proposition.situation.tresorerie - proposition.situation.dettes
    assert [s.dividendes for s in proposition.scenarios] == sorted(
        s.dividendes for s in proposition.scenarios
    )


def test_la_decision_solde_le_resultat_et_ne_se_prend_qu_une_fois() -> None:
    demo = Demo()
    demo.clore(KARIM)
    proposition = demo.proposer(KARIM)
    maximum = proposition.scenarios[-1]

    decider(
        proposition,
        demo.dossier(KARIM),
        maximum.cle,
        maximum.dividendes,
        demo.ledger,
        demo.affectations,
        MAINTENANT,
        "user-karim",
    )

    balance = soldes(demo.ledger.grand_livre(KARIM))
    assert balance.get("120", 0) == 0
    assert -balance["457"] == maximum.dividendes
    decision = demo.affectations.obtenir(KARIM, 2025)
    assert decision is not None and decision.decide_par == "user-karim"
    with pytest.raises(AffectationImpossible, match="déjà affecté"):
        demo.proposer(KARIM)


def test_une_perte_n_offre_que_le_report_a_nouveau() -> None:
    demo = Demo()
    demo.clore(YANIS)

    proposition = demo.proposer(YANIS)

    assert proposition.situation.resultat < 0
    assert {s.dividendes for s in proposition.scenarios} == {0}


def test_a_l_ir_pas_de_dividendes_a_decider() -> None:
    demo = Demo()
    a_l_ir = dataclasses.replace(
        demo.dossier(KARIM), forme_juridique="EURL", regime_imposition="IR"
    )
    demo.dossiers.ouvrir_exercice(a_l_ir)
    with pytest.raises(AffectationImpossible, match="impôt sur le revenu"):
        demo.proposer(KARIM)
