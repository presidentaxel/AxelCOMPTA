"""AXE-801 : le CA d'un mois sans Rollee, depuis le récapitulatif de la plateforme."""

from __future__ import annotations

import re
from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.recettes_recaps import Recap, ecritures_du_mois, recap_depuis
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

D = DossierId("D")
REGIMES = {"uber": (re.compile(r"(?i)\buber\b"), "france_20")}
# Récapitulatif Uber de novembre 2025 (lu en prod le 18/11).
NOVEMBRE = Recap("uber", "2025-11", 508568, 18756, 159879, 367445)


def _virement(
    ident: str, jour: date, cts: int, libelle: str = "STICHTING CUSTODIAN UBER"
) -> Ecriture:
    return Ecriture(
        id=EcritureId(ident),
        dossier_id=D,
        journal=Journal.BQ,
        date=jour,
        libelle=libelle,
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(cts)),
            LigneEcriture("471", Sens.CREDIT, Money(cts)),
        ),
    )


def _solde(ecritures: list[Ecriture], compte: str) -> int:
    return sum(
        lg.montant.centimes if lg.sens is Sens.DEBIT else -lg.montant.centimes
        for e in ecritures
        for lg in e.lignes
        if lg.compte == compte
    )


def test_la_recette_du_mois_et_les_virements_soldent_la_creance() -> None:
    virements = [
        _virement("v1", date(2025, 11, 10), 200000),
        _virement("v2", date(2025, 11, 24), 167445),
        _virement("decembre", date(2025, 12, 1), 99999),  # un autre mois
        _virement("total", date(2025, 11, 12), 5000, "CB TOTAL"),  # pas Uber
    ]
    ods = ecritures_du_mois(D, NOVEMBRE, virements, REGIMES, set(), "assujetti_taux_reduit")
    recette, *soldes = ods
    assert sum(lg.montant.centimes for lg in recette.lignes if lg.sens is Sens.DEBIT) == sum(
        lg.montant.centimes for lg in recette.lignes if lg.sens is Sens.CREDIT
    )
    assert _solde([recette], "4671") == 367445  # la créance porte le net
    assert -_solde([recette], "708") == 18756  # autres revenus, sans TVA
    assert -(_solde([recette], "706") + _solde([recette], "44571")) == 508568
    assert [s.id for s in soldes] == ["v1:solde-plateforme", "v2:solde-plateforme"]
    assert _solde(ods, "4671") == 0  # le mois est soldé
    # Rejouer n'écrit rien.
    assert (
        ecritures_du_mois(D, NOVEMBRE, [*virements, *ods], REGIMES, set(), "assujetti_taux_reduit")
        == []
    )


def test_un_mois_couvert_par_rollee_ou_un_recap_faux_n_est_pas_ecrit() -> None:
    virements = [_virement("v1", date(2025, 11, 10), 200000)]
    assert (
        ecritures_du_mois(
            D, NOVEMBRE, virements, REGIMES, {("uber", "2025-11")}, "assujetti_taux_reduit"
        )
        == []
    )
    faux = {
        "type": "recap_plateforme",
        "plateforme": "uber",
        "mois": "2025-11",
        "courses_cts": 1,
        "autres_cts": 0,
        "frais_cts": 0,
        "net_cts": 2,
    }
    assert recap_depuis(faux) is None
    juste = {**faux, "net_cts": 1}
    assert recap_depuis(juste) == Recap("uber", "2025-11", 1, 0, 0, 1)
