"""AXE-924 : écrire une semaine de plateforme soldée, ou dire pourquoi pas."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from axelcompta.core.ids import EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.settlements_plateforme import SettlementStocke, fusionner
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.revenus_rollee import delier_revenus
from axelcompta.revenus_semaines import (
    Contexte,
    RienATrancher,
    rapprocher_semaines,
    trancher_semaine,
    virements_libres,
)
from tests.test_revenus_rollee import DOSSIER, JOUR, D

LE = datetime(2026, 11, 20, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 20)
POP = "POP SVCS, DOB , 20261005 - 20261011"


def _contexte(closes: tuple = ()) -> Contexte:  # type: ignore[type-arg]
    return Contexte(DOSSIER, closes, LE)


def _jour(net: int = 848_00, especes: float = 0, compte: str = "acc-uber") -> SettlementStocke:
    jour = replace(
        JOUR,
        gross_earnings_cts=net,
        commission_cts=0,
        net_payout_cts=net,
        raw_payload={"cash_earnings": especes},
    )
    stocke = fusionner(None, compte, jour, LE)
    assert stocke is not None
    return stocke


def _virement(montant: int, contrepartie: str = "471", libelle: str = POP) -> Ecriture:
    return Ecriture(
        id=EcritureId("V1"),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 10, 12),
        libelle=libelle,
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(montant)),
            LigneEcriture(contrepartie, Sens.CREDIT, Money(montant)),
        ),
    )


# La banque est connectée depuis septembre : une opération quelconque.
OUVERTURE = replace(
    _virement(10_00, libelle="VIR SEPA LOYER"), id=EcritureId("V0"), date=date(2026, 9, 1)
)


def _soldes(ecritures: list[Ecriture]) -> dict[str, int]:
    soldes: dict[str, int] = {}
    for e in ecritures:
        for x in e.lignes:
            signe = 1 if x.sens is Sens.DEBIT else -1
            soldes[x.compte] = soldes.get(x.compte, 0) + signe * x.montant.centimes
    return {c: v for c, v in soldes.items() if v}


def test_seuls_les_virements_de_plateforme_sont_pris() -> None:
    autre = replace(_virement(100_00, libelle="VIR SEPA LOYER"), id=EcritureId("V2"))
    assert set(virements_libres([_virement(848_00), autre])) == {"V1"}


def test_une_semaine_soldee_vide_le_471_et_la_creance() -> None:
    virement = _virement(848_00)
    passage = rapprocher_semaines([_jour()], [OUVERTURE, virement], _contexte(), AUJOURD_HUI)
    soldes = _soldes([virement, *passage.ecritures])
    assert "4671" not in soldes and "471" not in soldes
    assert soldes["512"] == 848_00 and -(soldes["706"] + soldes["44571"]) == 848_00
    ((suite,),) = (passage.stockes,)
    assert (suite.etat, suite.ecriture_id) == ("reconcilie", f"{suite.id}:recette-plateforme")


def test_les_especes_vont_en_caisse_et_ne_sont_pas_attendues_en_banque() -> None:
    """100 € gagnés dont 30 € en espèces : la plateforme verse 70 €."""
    virement = _virement(70_00)
    passage = rapprocher_semaines(
        [_jour(100_00, 30.0)], [OUVERTURE, virement], _contexte(), AUJOURD_HUI
    )
    soldes = _soldes([virement, *passage.ecritures])
    assert soldes["530"] == 30_00 and "4671" not in soldes
    assert passage.semaines[0].etat == "solde"


def test_un_virement_classe_ailleurs_par_un_humain_n_est_pas_touche() -> None:
    passage = rapprocher_semaines(
        [_jour()], [OUVERTURE, _virement(848_00, "455")], _contexte(), AUJOURD_HUI
    )
    assert passage.ecritures == []
    assert "virement classé en 455" in (passage.stockes[0].motif or "")


def test_une_semaine_dans_un_exercice_clos_n_ecrit_rien() -> None:
    clos = ((date(2026, 1, 1), date(2026, 10, 31)),)
    passage = rapprocher_semaines(
        [_jour()], [OUVERTURE, _virement(848_00)], _contexte(closes=clos), AUJOURD_HUI
    )
    assert passage.ecritures == [] and passage.stockes[0].etat == "a_verifier"


def test_un_virement_pas_encore_recu_laisse_le_jour_en_attente() -> None:
    passage = rapprocher_semaines([_jour()], [OUVERTURE], _contexte(), date(2026, 10, 15))
    assert passage.ecritures == [] and passage.stockes[0].etat == "en_attente_banque"


def test_retirer_le_lien_contre_passe_toute_la_semaine() -> None:
    """Recette, solde et frais de la semaine sont contre-passés, jamais
    supprimés ; un jour d'un autre compte de la même semaine passe à vérifier."""
    a_lui, autre = _jour(500_00), _jour(348_00, compte="acc-autre")
    autre = replace(
        autre,
        settlement=replace(
            autre.settlement, period_start=date(2026, 10, 6), period_end=date(2026, 10, 6)
        ),
        id="acc-autre:2",
    )
    virement = _virement(848_00)
    passage = rapprocher_semaines([a_lui, autre], [OUVERTURE, virement], _contexte(), AUJOURD_HUI)
    grand_livre = [virement, *passage.ecritures]
    inverses, suites = delier_revenus(
        passage.stockes, frozenset({"acc-uber"}), grand_livre, (), date(2026, 1, 1), LE
    )
    assert len(inverses) == len(passage.ecritures) == 3
    assert _soldes([*grand_livre, *inverses]) == _soldes([virement])
    assert {s.id: s.etat for s in suites} == {a_lui.id: "delie", autre.id: "a_verifier"}


def test_les_semaines_d_avant_l_historique_bancaire_restent_en_attente() -> None:
    """Rollee remonte à janvier, la banque au 12/10 : rien à rapprocher avant."""
    vieux = _jour()
    vieux = replace(
        vieux,
        id="vieux",
        settlement=replace(
            vieux.settlement, period_start=date(2026, 6, 1), period_end=date(2026, 6, 1)
        ),
    )
    passage = rapprocher_semaines(
        [vieux, _jour()], [OUVERTURE, _virement(848_00)], _contexte(), AUJOURD_HUI
    )
    assert [s.id for s in passage.stockes] == [_jour().id]  # le vieux jour n'est pas touché
    assert rapprocher_semaines([_jour()], [], _contexte(), AUJOURD_HUI).stockes == []


def test_seules_les_courses_portent_la_tva() -> None:
    """AXE-926 : 848 € gagnés dont 20 € de pourboires, 18 € de bonus et
    10 € d'autres montants : 48 € sans TVA."""
    jour = _jour()
    hors_course: dict[str, Any] = {"tips": 20.0, "bonus_amount": 18.0, "other_amount": 10.0}
    jour = replace(jour, settlement=replace(jour.settlement, raw_payload=hors_course))
    virement = _virement(848_00)
    passage = rapprocher_semaines([jour], [OUVERTURE, virement], _contexte(), AUJOURD_HUI)
    soldes = _soldes([virement, *passage.ecritures])
    assert (soldes["708"], soldes["44571"]) == (-48_00, -72_73)
    assert "4671" not in soldes


# AXE-912 : chaque motif « à vérifier » a une sortie décidée par l'expert.
SEMAINE_UBER = ("uber", date(2026, 10, 5))


def _a_verifier(grand_livre: list[Ecriture], closes: tuple = ()) -> list[SettlementStocke]:  # type: ignore[type-arg]
    passage = rapprocher_semaines([_jour()], grand_livre, _contexte(closes), AUJOURD_HUI)
    assert passage.stockes[0].etat == "a_verifier"
    return passage.stockes


def test_ecrire_une_semaine_avec_ecart_laisse_l_ecart_sur_la_creance() -> None:
    """848 € gagnés, 800 € versés : la recette est écrite, 48 € restent dus
    par Uber au 4671, visibles."""
    virement = _virement(800_00)
    stockes = _a_verifier([OUVERTURE, virement])
    passage = trancher_semaine(
        stockes, [OUVERTURE, virement], _contexte(), SEMAINE_UBER, "ecrire", "commission Uber"
    )
    soldes = _soldes([virement, *passage.ecritures])
    assert soldes["4671"] == 48_00 and "471" not in soldes
    assert -(soldes["706"] + soldes["44571"]) == 848_00
    ((jour,),) = (passage.stockes,)
    assert jour.etat == "reconcilie" and "commission Uber" in (jour.motif or "")
    # Le passage suivant ne la reprend pas.
    apres = rapprocher_semaines(
        passage.stockes, [OUVERTURE, virement, *passage.ecritures], _contexte(), AUJOURD_HUI
    )
    assert apres.ecritures == [] and apres.stockes == []


def test_ecrire_une_semaine_d_exercice_clos_passe_sur_l_exercice_ouvert() -> None:
    clos = ((date(2026, 1, 1), date(2026, 10, 31)),)
    virement = _virement(848_00)
    stockes = _a_verifier([OUVERTURE, virement], clos)
    passage = trancher_semaine(
        stockes, [OUVERTURE, virement], _contexte(clos), SEMAINE_UBER, "ecrire", "reprise 2026"
    )
    assert passage.ecritures
    assert {e.date for e in passage.ecritures} == {date(2026, 11, 1)}


def test_ecrire_garde_le_classement_d_un_virement_classe_ailleurs() -> None:
    virement = _virement(848_00, "455")
    stockes = _a_verifier([OUVERTURE, virement])
    passage = trancher_semaine(
        stockes, [OUVERTURE, virement], _contexte(), SEMAINE_UBER, "ecrire", "apport associé"
    )
    assert not any(e.id.endswith(":solde-plateforme") for e in passage.ecritures)
    assert _soldes([virement, *passage.ecritures])["4671"] == 848_00


def test_ecarter_sort_les_jours_sans_rien_ecrire() -> None:
    virement = _virement(800_00)
    stockes = _a_verifier([OUVERTURE, virement])
    passage = trancher_semaine(
        stockes, [OUVERTURE, virement], _contexte(), SEMAINE_UBER, "ecarter", "compte de flotte"
    )
    assert passage.ecritures == []
    assert [s.etat for s in passage.stockes] == ["delie"]


def test_un_virement_arrive_apres_coup_solde_l_ecart() -> None:
    """Semaine écrite avec 48 € dus ; le complément arrive : l'expert
    l'écrit, la créance revient à zéro."""
    premier = _virement(800_00)
    stockes = _a_verifier([OUVERTURE, premier])
    ecrit = trancher_semaine(
        stockes, [OUVERTURE, premier], _contexte(), SEMAINE_UBER, "ecrire", "écart à suivre"
    )
    complement = replace(_virement(48_00), id=EcritureId("V3"), date=date(2026, 10, 20))
    grand_livre = [OUVERTURE, premier, *ecrit.ecritures, complement]
    solde = trancher_semaine(
        ecrit.stockes, grand_livre, _contexte(), SEMAINE_UBER, "ecrire", "complément reçu"
    )
    assert "4671" not in _soldes([premier, complement, *ecrit.ecritures, *solde.ecritures])


def test_rien_a_trancher_est_refuse() -> None:
    with pytest.raises(RienATrancher):
        trancher_semaine([], [OUVERTURE], _contexte(), SEMAINE_UBER, "ecrire", "rien")
