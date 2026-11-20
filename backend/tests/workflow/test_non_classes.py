"""AXE-1013 : les entrées et sorties encore au 471 sur l'exercice."""

from __future__ import annotations

from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.ecritures_semaines import id_solde
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.non_classes import non_classes

D = DossierId("D")
DEBUT, FIN = date(2025, 10, 1), date(2026, 9, 30)


def _banque(ident: str, jour: date, cts: int, compte: str = "471") -> Ecriture:
    """Une opération bancaire : `cts` > 0 une entrée, < 0 une sortie."""
    entree = cts > 0
    return Ecriture(
        id=EcritureId(ident),
        dossier_id=D,
        journal=Journal.BQ,
        date=jour,
        libelle=ident,
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT if entree else Sens.CREDIT, Money(abs(cts))),
            LigneEcriture(compte, Sens.CREDIT if entree else Sens.DEBIT, Money(abs(cts))),
        ),
    )


def test_entrees_et_sorties_au_471_sur_l_exercice() -> None:
    ecritures = [
        _banque("uber", date(2026, 5, 11), 104600),
        _banque("total", date(2026, 5, 12), -6000),
        _banque("classee", date(2026, 5, 13), -2500, compte="606"),
        _banque("avant", date(2025, 9, 30), 99900),  # exercice précédent
    ]
    assert non_classes(ecritures, DEBUT, FIN) == (104600, 6000)


def test_un_virement_solde_par_sa_semaine_ou_annule_ne_compte_plus() -> None:
    uber = _banque("uber", date(2026, 5, 11), 104600)
    solde = Ecriture(
        id=id_solde("uber"),
        dossier_id=D,
        journal=Journal.OD,
        date=date(2026, 5, 11),
        libelle="Versement Uber",
        reference_piece=None,
        lignes=(
            LigneEcriture("471", Sens.DEBIT, Money(104600)),
            LigneEcriture("4671", Sens.CREDIT, Money(104600)),
        ),
    )
    erreur = _banque("erreur", date(2026, 6, 1), -5000)
    ecritures = [uber, solde, erreur, contrepasser(erreur)]
    assert non_classes(ecritures, DEBUT, FIN) == (0, 0)
