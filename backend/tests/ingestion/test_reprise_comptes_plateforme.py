"""AXE-931 : les semaines déjà écrites passent sur les comptes de l'expert."""

from __future__ import annotations

from datetime import date

from axelcompta.core.ids import EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.reprise_comptes_plateforme import id_reprise, reprises
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.revenus_rollee import SUFFIXES_SEMAINE
from tests.test_revenus_rollee import D

LE = date(2026, 10, 12)
PIECE = "uber:2026-10-05"


def _od(ident: str, *lignes: tuple[str, Sens, int], piece: str = PIECE) -> Ecriture:
    return Ecriture(
        id=EcritureId(ident),
        dossier_id=D,
        journal=Journal.OD,
        date=LE,
        libelle="Recette Uber du 05/10/2026",
        reference_piece=piece,
        lignes=tuple(LigneEcriture(c, s, Money(m)) for c, s, m in lignes),
    )


# Écrites avant AXE-931 : 110 € gagnés dont 30 € en espèces et 10 € de
# pourboire, une commission à 0 ; versement de 80 € moins 0,99 € de frais.
RECETTE = _od(
    "j1:recette-plateforme",
    ("467", Sens.DEBIT, 80_00),
    ("455", Sens.DEBIT, 30_00),
    ("622", Sens.DEBIT, 0),
    ("706", Sens.CREDIT, 90_91),
    ("44571", Sens.CREDIT, 9_09),
    ("7068", Sens.CREDIT, 10_00),
)
SOLDE = _od("V1:solde-plateforme", ("471", Sens.DEBIT, 79_01), ("467", Sens.CREDIT, 79_01))
FRAIS = _od(
    "D1:uber:2026-10-05:frais-plateforme", ("627", Sens.DEBIT, 99), ("467", Sens.CREDIT, 99)
)


def _soldes(ecritures: list[Ecriture]) -> dict[str, int]:
    soldes: dict[str, int] = {}
    for e in ecritures:
        for x in e.lignes:
            signe = 1 if x.sens is Sens.DEBIT else -1
            soldes[x.compte] = soldes.get(x.compte, 0) + signe * x.montant.centimes
    return {c: v for c, v in soldes.items() if v}


def test_les_montants_passent_sur_les_comptes_de_l_expert() -> None:
    avant = [RECETTE, SOLDE, FRAIS]
    ods = reprises(avant)
    assert [od.id for od in ods] == [id_reprise(e.id) for e in avant]
    assert all(od.reference_piece == PIECE for od in ods)
    soldes = _soldes([*avant, *ods])
    assert soldes == {
        "530": 30_00,
        "706": -90_91,
        "44571": -9_09,
        "708": -10_00,
        "471": 79_01,
        "627": 99,
    }


def test_rejouer_ne_cree_rien_et_une_semaine_annulee_n_est_pas_reprise() -> None:
    deja = [RECETTE, *reprises([RECETTE])]
    assert reprises(deja) == []
    annulee = [RECETTE, contrepasser(RECETTE, (), date(2026, 1, 1))]
    assert reprises(annulee) == []


def test_une_plateforme_sans_compte_propre_garde_le_467() -> None:
    heetch = _od(
        "V2:solde-plateforme",
        ("471", Sens.DEBIT, 10_00),
        ("467", Sens.CREDIT, 10_00),
        piece="heetch:2026-10-05",
    )
    assert reprises([heetch]) == []


def test_retirer_le_lien_contre_passe_aussi_la_reprise() -> None:
    (od,) = reprises([SOLDE])
    assert od.id.endswith(SUFFIXES_SEMAINE)
