"""AXE-424 : résoudre une entrée de quarantaine d'ingestion."""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.journal import EntreeQuarantaine
from axelcompta.ingestion.providers.digifactory import normaliser_payload
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.quarantaine import (
    MODIFIEE,
    PERIODE_CLOSE,
    SUPPRIMEE,
    ResolutionRefusee,
    ecritures_de_resolution,
)
from axelcompta.workflow.reclassement import annuler_reclassements, reclasser

D = DossierId("d1")
ORIGINE = EcritureId("d1:digifactory-t1")
CLOS_2025 = ((date(2025, 1, 1), date(2025, 12, 31)),)


def _payload(montant: float, jour: str = "2026-03-01") -> dict[str, object]:
    return {
        "id": "t1",
        "provider_description": "CB TOTAL",
        "amount": montant,
        "date": jour,
        "updated_at": f"{jour} 10:00:00",
    }


def _entree(motif: str, montant: float = -75.0, jour: str = "2026-03-01") -> EntreeQuarantaine:
    return EntreeQuarantaine(D, "digifactory", motif, "t1", _payload(montant, jour), "q1")


def _origine_contre_passee_avec_decision() -> list[Ecriture]:
    """La synchro a passé -60 €, le chauffeur a choisi carburant, puis la
    banque a changé le montant : la synchro a tout contre-passé."""
    origine = Ecriture(
        id=ORIGINE,
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="CB TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture("5121", Sens.CREDIT, Money(60_00)),
            LigneEcriture("471", Sens.DEBIT, Money(60_00)),
        ),
    )
    ecritures = [origine]
    decision = reclasser(origine, "carburant", ecritures, ({}, {"carburant": "6061"}))
    assert decision is not None
    ecritures.append(decision)
    ecritures.append(contrepasser(origine))
    ecritures.extend(annuler_reclassements(ORIGINE, ecritures))
    return ecritures


def _resoudre(
    entree: EntreeQuarantaine,
    ecritures: list[Ecriture],
    periodes_closes: tuple[tuple[date, date], ...] = (),
) -> list[Ecriture]:
    return ecritures_de_resolution(
        entree, "accepter", ORIGINE, ecritures, normaliser_payload, periodes_closes
    )


def _soldes(ecritures: list[Ecriture]) -> Counter[str]:
    soldes: Counter[str] = Counter()
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            soldes[ligne.compte] += (1 if ligne.sens is Sens.DEBIT else -1) * ligne.montant.centimes
    return Counter({c: s for c, s in soldes.items() if s})


def test_accepter_un_montant_modifie_le_passe_sur_la_categorie_choisie() -> None:
    ecritures = _origine_contre_passee_avec_decision()

    a_ecrire = _resoudre(_entree(MODIFIEE), ecritures)

    assert [e.id for e in a_ecrire] == [
        "d1:digifactory-t1:corrige-1",
        "d1:digifactory-t1:corrige-1:decision-1",
    ]
    assert _soldes(ecritures + a_ecrire) == Counter({"6061": 75_00, "5121": -75_00})


def test_une_seconde_modification_contre_passe_la_premiere_correction() -> None:
    ecritures = _origine_contre_passee_avec_decision()
    ecritures += _resoudre(_entree(MODIFIEE), ecritures)

    a_ecrire = _resoudre(_entree(MODIFIEE, -80.0), ecritures)

    assert a_ecrire[0].id == "d1:digifactory-t1:corrige-1:contrepassation"
    assert a_ecrire[-1].id == "d1:digifactory-t1:corrige-2:decision-1"
    assert _soldes(ecritures + a_ecrire) == Counter({"6061": 80_00, "5121": -80_00})


def test_sans_decision_le_nouveau_montant_reste_a_trancher() -> None:
    origine = _origine_contre_passee_avec_decision()[0]
    ecritures = [origine, contrepasser(origine)]
    a_ecrire = _resoudre(_entree(MODIFIEE), ecritures)
    assert _soldes(ecritures + a_ecrire) == Counter({"471": 75_00, "5121": -75_00})


def test_une_operation_d_un_exercice_clos_est_passee_au_premier_jour_ouvert() -> None:
    (nouvelle,) = _resoudre(
        _entree(PERIODE_CLOSE, -12.0, "2025-12-28"), [], periodes_closes=CLOS_2025
    )
    assert nouvelle.date == date(2026, 1, 1)
    assert nouvelle.lignes[0].compte == "512"


def test_supprimee_ou_ignoree_n_ecrit_rien_et_illisible_ne_s_accepte_pas() -> None:
    ecritures = _origine_contre_passee_avec_decision()
    assert _resoudre(_entree(SUPPRIMEE), ecritures) == []
    assert (
        ecritures_de_resolution(
            _entree(MODIFIEE), "ignorer", ORIGINE, ecritures, normaliser_payload
        )
        == []
    )
    with pytest.raises(ResolutionRefusee):
        _resoudre(_entree("ligne_illisible : date manquante"), ecritures)
