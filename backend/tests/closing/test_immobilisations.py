"""AXE-802 : registre des immobilisations et amortissement linéaire."""

from __future__ import annotations

import dataclasses
from collections import Counter
from datetime import date
from typing import Any

import pytest

from axelcompta.closing.immobilisations import (
    Cession,
    Immobilisation,
    ImmobilisationInvalide,
    cumul,
    dotation,
    ecritures_immobilisations,
    jours_360,
    plus_ou_moins_value,
    valeur_nette,
    valider,
)
from axelcompta.core.ids import DossierId
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.models import Sens

D = DossierId("d1")
VEHICULE = Immobilisation(
    id="v1",
    designation="Toyota Corolla",
    compte="2182",
    mise_en_service=date(2026, 4, 1),
    base_cts=30_000_00,
    duree_mois=60,
)


def _exercice(annee: int) -> tuple[date, date]:
    return date(annee, 1, 1), date(annee, 12, 31)


def test_neuf_mois_la_premiere_annee() -> None:
    """Critère : 30 000 € HT au 1er avril sur 5 ans → 4 500 € en 2026."""
    assert dotation(VEHICULE, *_exercice(2026)) == 4_500_00
    assert dotation(VEHICULE, *_exercice(2027)) == 6_000_00


def test_la_somme_des_dotations_vaut_la_base() -> None:
    total = sum(dotation(VEHICULE, *_exercice(a)) for a in range(2026, 2033))
    assert total == VEHICULE.base_cts
    assert dotation(VEHICULE, *_exercice(2032)) == 0


@pytest.mark.parametrize("base", [1, 99_99, 12_345_67, 30_000_01])
@pytest.mark.parametrize("duree", [12, 36, 60, 84])
@pytest.mark.parametrize("mise", [date(2026, 1, 1), date(2026, 2, 28), date(2026, 7, 31)])
def test_la_somme_vaut_la_base_quel_que_soit_l_arrondi(base: int, duree: int, mise: date) -> None:
    immo = Immobilisation("x", "x", "2183", mise, base, duree)
    assert sum(dotation(immo, *_exercice(a)) for a in range(2026, 2035)) == base


def test_les_jours_comptent_trente_par_mois() -> None:
    assert jours_360(date(2026, 4, 1), date(2026, 12, 31)) == 270
    assert jours_360(date(2026, 2, 1), date(2026, 2, 28)) == 28
    assert jours_360(date(2026, 5, 1), date(2026, 4, 30)) == 0


def test_l_ecriture_de_dotation_est_passee_au_dernier_jour() -> None:
    (ecriture,) = ecritures_immobilisations(D, (VEHICULE,), *_exercice(2026))
    verifier_equilibre(ecriture)
    assert ecriture.date == date(2026, 12, 31)
    assert ecriture.id == "d1:cloture-immo-2026-dotation-v1"
    assert [(x.compte, x.sens, x.montant.centimes) for x in ecriture.lignes] == [
        ("6811", Sens.DEBIT, 4_500_00),
        ("28182", Sens.CREDIT, 4_500_00),
    ]


def test_une_cession_en_annee_trois_sort_l_actif() -> None:
    cede = dataclasses.replace(VEHICULE, cession=Cession(date(2028, 6, 30), 18_000_00))
    # 2026 : 4 500 ; 2027 : 6 000 ; 2028 : 6 mois = 3 000 ; cumul 13 500.
    assert dotation(cede, *_exercice(2028)) == 3_000_00
    assert cumul(cede, date(2030, 1, 1)) == 13_500_00
    assert valeur_nette(cede, date(2028, 6, 30)) == 16_500_00
    assert plus_ou_moins_value(cede) == 1_500_00
    dot, sortie = ecritures_immobilisations(D, (cede,), *_exercice(2028))
    verifier_equilibre(sortie)
    assert sortie.date == date(2028, 6, 30)
    soldes: Counter[str] = Counter()
    for e in (dot, sortie):
        for x in e.lignes:
            soldes[x.compte] += (1 if x.sens is Sens.DEBIT else -1) * x.montant.centimes
    assert soldes == Counter(
        {"6811": 3_000_00, "28182": 10_500_00, "675": 16_500_00, "2182": -30_000_00}
    )
    assert ecritures_immobilisations(D, (cede,), *_exercice(2029)) == ()


@pytest.mark.parametrize(
    "champ, valeur",
    [
        ("compte", "28182"),
        ("compte", "6061"),
        ("base_cts", 0),
        ("duree_mois", 6),
        ("designation", " "),
    ],
)
def test_une_fiche_inutilisable_est_refusee(champ: str, valeur: Any) -> None:
    with pytest.raises(ImmobilisationInvalide):
        valider(dataclasses.replace(VEHICULE, **{champ: valeur}))
