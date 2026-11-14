"""AXE-924 : écrire une semaine de plateforme soldée, ou dire pourquoi pas."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from axelcompta.core.ids import EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.settlements_plateforme import SettlementStocke, fusionner
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.revenus_rollee import delier_revenus
from axelcompta.revenus_semaines import Contexte, rapprocher_semaines, virements_libres
from tests.test_revenus_rollee import DOSSIER, JOUR, D

LE = datetime(2026, 11, 20, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 20)
POP = "POP SVCS, DOB , 20261005 - 20261011"


def _contexte(compte_especes: str | None = "455", closes: tuple = ()) -> Contexte:  # type: ignore[type-arg]
    return Contexte(DOSSIER, closes, compte_especes, LE)


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
    assert "467" not in soldes and "471" not in soldes
    assert soldes["512"] == 848_00 and -(soldes["706"] + soldes["44571"]) == 848_00
    ((suite,),) = (passage.stockes,)
    assert (suite.etat, suite.ecriture_id) == ("reconcilie", f"{suite.id}:recette-plateforme")


def test_les_especes_vont_au_compte_de_l_associe_et_ne_sont_pas_attendues_en_banque() -> None:
    """100 € gagnés dont 30 € en espèces : la plateforme verse 70 €."""
    virement = _virement(70_00)
    passage = rapprocher_semaines(
        [_jour(100_00, 30.0)], [OUVERTURE, virement], _contexte(), AUJOURD_HUI
    )
    soldes = _soldes([virement, *passage.ecritures])
    assert soldes["455"] == 30_00 and "467" not in soldes
    assert passage.semaines[0].etat == "solde"


def test_des_especes_sans_compte_de_l_associe_laissent_la_semaine_a_verifier() -> None:
    passage = rapprocher_semaines(
        [_jour(100_00, 30.0)], [OUVERTURE, _virement(70_00)], _contexte(None), AUJOURD_HUI
    )
    assert passage.ecritures == []
    assert passage.stockes[0].etat == "a_verifier"
    assert "espèces sans compte" in (passage.stockes[0].motif or "")


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
    assert (soldes["7068"], soldes["44571"]) == (-48_00, -72_73)
    assert "467" not in soldes
