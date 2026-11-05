from __future__ import annotations

from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.comptes_bancaires import CompteBancaireMemoire
from axelcompta.ingestion.journal import InMemoryJournalIngestion
from axelcompta.ledger.banque import est_reclassement_bancaire
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.ventilation_bancaire import (
    ecriture_de_ventilation,
    id_ventilation,
    ventilation_du_dossier,
    ventiler,
)

DOSSIER = DossierId("DIGI_22755")


def _ecriture(tx: str, montant: int, banque: str = "512") -> Ecriture:
    sens = Sens.DEBIT if montant > 0 else Sens.CREDIT
    autre = Sens.CREDIT if sens is Sens.DEBIT else Sens.DEBIT
    return Ecriture(
        id=EcritureId(f"{DOSSIER}:digifactory-{tx}"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 6, 3),
        libelle="TOTAL (carburant)",
        reference_piece=None,
        lignes=(
            LigneEcriture(banque, sens, Money(abs(montant))),
            LigneEcriture("6061", autre, Money(abs(montant))),
        ),
    )


def _solde(ecritures: list[Ecriture], compte: str) -> int:
    return sum(
        (1 if ligne.sens is Sens.DEBIT else -1) * ligne.montant.centimes
        for e in ecritures
        for ligne in e.lignes
        if ligne.compte == compte
    )


def test_le_reclassement_solde_le_512_et_porte_le_sous_compte() -> None:
    depense = _ecriture("t1", -6_000)
    reclassement = ecriture_de_ventilation(depense, "5121")
    assert reclassement is not None
    verifier_equilibre(reclassement)
    assert reclassement.id == id_ventilation(depense.id)
    assert reclassement.journal is Journal.OD
    assert reclassement.date == depense.date
    assert reclassement.reference_piece == depense.id
    assert est_reclassement_bancaire(reclassement)
    assert _solde([depense, reclassement], "512") == 0
    assert _solde([depense, reclassement], "5121") == -6_000


def test_rien_a_reclasser_sans_512_ou_vers_512() -> None:
    assert ecriture_de_ventilation(_ecriture("t1", 100, banque="5122"), "5121") is None
    assert ecriture_de_ventilation(_ecriture("t1", 100), "512") is None
    assert ecriture_de_ventilation(_ecriture("t1", 100), "6061") is None


def test_ventiler_est_rejouable_et_ignore_les_paires_contre_passees() -> None:
    a, b = _ecriture("t1", -6_000), _ecriture("t2", 10_000)
    annulee = _ecriture("t3", -1_000)
    ecritures = [a, b, annulee, contrepasser(annulee)]

    premieres = ventiler(ecritures, lambda e: "5121")
    secondes = ventiler(ecritures + premieres, lambda e: "5121")

    assert {e.reference_piece for e in premieres} == {a.id, b.id}
    assert secondes == []


def test_le_dossier_se_ventile_depuis_l_archive_brute() -> None:
    journal = InMemoryJournalIngestion()
    for tx, compte in (("t1", "pro"), ("t2", "fiscal"), ("t3", None)):
        payload: dict[str, object] = {"id": tx}
        if compte is not None:
            payload["account_id"] = compte
        journal.archiver(DOSSIER, "digifactory", tx, None, payload)
    comptes = CompteBancaireMemoire()
    autre_source = Ecriture(
        id=EcritureId(f"{DOSSIER}:fichier-x"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 6, 3),
        libelle="import",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(1)),
            LigneEcriture("471", Sens.CREDIT, Money(1)),
        ),
    )
    ecritures = [
        _ecriture("t1", -6_000),
        _ecriture("t2", 10_000),
        _ecriture("t3", -5),
        autre_source,
    ]

    reclassements = ventilation_du_dossier(DOSSIER, ecritures, journal, comptes, "digifactory")

    par_origine = {r.reference_piece: r.lignes[0].compte for r in reclassements}
    assert par_origine == {
        f"{DOSSIER}:digifactory-t1": "5121",
        f"{DOSSIER}:digifactory-t2": "5122",
    }
    tout = ecritures + reclassements
    assert _solde(tout, "5121") == -6_000
    assert _solde(tout, "5122") == 10_000
    assert _solde(tout, "512") == -5 + 1  # t3 et l'autre source restent au 512


def test_le_journal_garde_le_compte_le_plus_recent_par_transaction() -> None:
    journal = InMemoryJournalIngestion()
    journal.archiver(DOSSIER, "digifactory", "t1", "1", {"id": "t1", "account_id": "ancien"})
    journal.archiver(DOSSIER, "digifactory", "t1", "2", {"id": "t1", "account_id": " nouveau "})
    journal.archiver(DossierId("autre"), "digifactory", "t9", "1", {"id": "t9", "account_id": "x"})
    assert journal.comptes_des_transactions(DOSSIER, "digifactory") == {"t1": "nouveau"}
    assert journal.comptes_des_transactions(DOSSIER, "fichier") == {}
