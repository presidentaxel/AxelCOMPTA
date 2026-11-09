"""Opérations déjà classées (AXE-823) : qui a classé, avec quelle confiance."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.ids import DossierId, EcritureId, TransactionId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.classees import (
    Filtres,
    OperationClassee,
    classer,
    compter,
    tranche_de,
    trier,
)
from axelcompta.workflow.verdicts import VerdictInvalide, VerdictsMemoire, verifier_verdict

D = DossierId("d1")


def _ecriture(identifiant: str, compte: str, montant: int, jour: int = 1) -> Ecriture:
    sens_banque = Sens.DEBIT if montant > 0 else Sens.CREDIT
    autre = Sens.CREDIT if montant > 0 else Sens.DEBIT
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 3, jour),
        libelle=identifiant.upper(),
        reference_piece=None,
        lignes=(
            LigneEcriture("5121", sens_banque, Money(abs(montant))),
            LigneEcriture(compte, autre, Money(abs(montant))),
        ),
    )


def _proposition(identifiant: str, categorie: str, etage: Etage, confiance: float) -> ProposedEntry:
    return ProposedEntry(D, TransactionId(identifiant), categorie, etage, confiance)


def test_classer_dit_qui_a_classe_chaque_operation() -> None:
    total = _ecriture("total", "6061", -60_00)
    uber = _ecriture("uber", "706", 848_00, 2)
    attente = _ecriture("mystere", "471", -12_00, 3)
    decidee = _ecriture("resto", "625", -20_00, 4)
    imputee_source = _ecriture("zara", "471", -68_00, 5)
    imputee = _ecriture("zara:impute-606", "606", -68_00, 5)
    ecritures = [
        total,
        uber,
        attente,
        decidee,
        imputee_source,
        contrepasser(imputee_source),
        imputee,
    ]
    propositions = {
        EcritureId("total"): _proposition("total", "carburant", Etage.REGLE, 0.97),
        EcritureId("uber"): _proposition("uber", "ca_vtc", Etage.ML, 0.5),
        EcritureId("zara"): _proposition("zara", "vetements", Etage.ML, 0.4),
    }
    decisions = {EcritureId("resto"): "repas"}

    par_id = {o.ecriture_id: o for o in classer(ecritures, propositions, decisions, {})}

    assert set(par_id) == {
        "total",
        "uber",
        "resto",
        "zara:impute-606",
    }  # 471 et paire annulée écartés
    assert (par_id[EcritureId("total")].origine, par_id[EcritureId("total")].compte) == (
        "regle",
        "6061",
    )
    assert par_id[EcritureId("uber")].origine == "modele"
    assert par_id[EcritureId("uber")].sens == "entree"
    assert (par_id[EcritureId("resto")].statut, par_id[EcritureId("resto")].categorie) == (
        "chauffeur",
        "repas",
    )
    assert par_id[EcritureId("zara:impute-606")].statut == "expert"
    assert par_id[EcritureId("total")].montant_cts == -60_00


def test_filtres_tri_et_compteurs() -> None:
    ops = [
        OperationClassee(
            D,
            EcritureId("a"),
            date(2026, 3, 1),
            "A",
            -10,
            "6061",
            "carburant",
            "regle",
            0.97,
            "auto",
            "juste",
        ),
        OperationClassee(
            D,
            EcritureId("b"),
            date(2026, 3, 2),
            "B",
            50,
            "706",
            "ca_vtc",
            "modele",
            0.5,
            "auto",
            "faux",
        ),
        OperationClassee(
            D,
            EcritureId("c"),
            date(2026, 3, 3),
            "C",
            -5,
            "625",
            "repas",
            "humain",
            None,
            "chauffeur",
        ),
    ]
    auto_regle = Filtres(statut="auto", origine="regle", categorie="carburant")
    assert [o.ecriture_id for o in ops if auto_regle.garde(o)] == ["a"]
    assert [o.ecriture_id for o in ops if Filtres(tranche="basse").garde(o)] == ["b"]
    assert [o.ecriture_id for o in ops if Filtres(sens="entree").garde(o)] == ["b"]
    assert [o.ecriture_id for o in trier(ops, "confiance")] == ["b", "a", "c"]
    assert [o.ecriture_id for o in trier(ops, "recentes")] == ["c", "b", "a"]
    compteurs = compter(ops)
    assert (compteurs.auto, compteurs.chauffeur, compteurs.justes, compteurs.fausses) == (
        2,
        1,
        1,
        1,
    )


@pytest.mark.parametrize(
    ("confiance", "tranche"),
    [(None, None), (0.5, "basse"), (0.6, "moyenne"), (0.949, "moyenne"), (0.95, "haute")],
)
def test_tranches_de_confiance(confiance: float | None, tranche: str | None) -> None:
    assert tranche_de(confiance) == tranche


def test_le_dernier_verdict_fait_foi() -> None:
    depot = VerdictsMemoire()
    le = datetime(2026, 11, 5, tzinfo=UTC)
    depot.noter(D, EcritureId("a"), "juste", UserId("louis"), le)
    depot.noter(D, EcritureId("a"), "faux", UserId("louis"), le)
    assert depot.derniers(D) == {"a": "faux"}
    assert depot.derniers(DossierId("autre")) == {}
    assert verifier_verdict("juste") == "juste"
    with pytest.raises(VerdictInvalide):
        verifier_verdict("peut-être")
