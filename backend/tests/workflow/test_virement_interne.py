"""AXE-930 : reprendre en virement interne les jambes d'un mouvement entre
enveloppes, sans toucher l'opération bancaire."""

from __future__ import annotations

import dataclasses
from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.reclassement import projeter
from axelcompta.workflow.ventilation_bancaire import ecriture_de_ventilation
from axelcompta.workflow.virement_interne import (
    ecriture_virement_interne,
    reprises,
    source_du_virement_interne,
    sous_comptes_ventiles,
)

D = DossierId("d")


def _operation(
    id_: str, montant: int, compte: str = "645", libelle: str = "cotisation URSSAF"
) -> Ecriture:
    banque, autre = (Sens.DEBIT, Sens.CREDIT) if montant > 0 else (Sens.CREDIT, Sens.DEBIT)
    return Ecriture(
        id=EcritureId(id_),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 8, 7),
        libelle=f"{libelle} (charges_sociales_impots)",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", banque, Money(abs(montant))),
            LigneEcriture(compte, autre, Money(abs(montant))),
        ),
    )


def _soldes(ecritures: list[Ecriture]) -> dict[str, int]:
    soldes: dict[str, int] = {}
    for e in ecritures:
        for x in e.lignes:
            signe = 1 if x.sens is Sens.DEBIT else -1
            soldes[x.compte] = soldes.get(x.compte, 0) + signe * x.montant.centimes
    return {c: v for c, v in soldes.items() if v}


def test_une_paire_du_meme_compte_passe_en_580_et_le_645_se_vide() -> None:
    """MK DRIVING, 07/08 : « cotisation URSSAF » −20 € puis +20 €."""
    sortie, entree = _operation("s", -20_00), _operation("e", 20_00)
    reprise = reprises([sortie, entree])
    assert (reprise.paires, len(reprise.ecritures), reprise.avec_tva) == (1, 2, 0)
    grand_livre = [sortie, entree, *reprise.ecritures]
    assert "645" not in _soldes(grand_livre)
    assert _soldes(grand_livre).get("512", 0) == 0
    vues = {e.id: e for e in projeter(grand_livre)}
    assert set(vues) == {"s", "e"}  # les OD sont repliées dans l'opération
    assert {x.compte for x in vues[EcritureId("s")].lignes} == {"512", "580"}


def test_rejouer_n_ecrit_rien_de_plus() -> None:
    sortie, entree = _operation("s", -20_00), _operation("e", 20_00)
    premiere = reprises([sortie, entree])
    assert reprises(projeter([sortie, entree, *premiere.ecritures])).ecritures == ()


def test_une_jambe_avec_tva_laisse_la_paire() -> None:
    sortie = _operation("s", -12_00, "6061", "carburant")
    sortie = dataclasses.replace(
        sortie,
        lignes=(
            LigneEcriture("512", Sens.CREDIT, Money(12_00)),
            LigneEcriture("6061", Sens.DEBIT, Money(10_00)),
            LigneEcriture("44566", Sens.DEBIT, Money(2_00)),
        ),
    )
    reprise = reprises([sortie, _operation("e", 12_00, "471", "carburant")])
    assert (reprise.paires, reprise.ecritures, reprise.avec_tva) == (0, (), 1)


def test_deux_libelles_differents_sur_le_meme_compte_ne_sont_pas_une_paire() -> None:
    reprise = reprises([_operation("s", -50_00, libelle="loyer"), _operation("e", 50_00)])
    assert reprise.ecritures == ()


def test_une_od_contre_passee_ne_compte_plus() -> None:
    sortie = _operation("s", -20_00)
    od = ecriture_virement_interne(sortie)
    assert od is not None and source_du_virement_interne(od.id) == "s"
    annulee = contrepasser(od, (), None)
    vue = projeter([sortie, od, annulee])
    assert [x.compte for x in vue[0].lignes] == ["512", "645"]


def test_deux_jambes_arrivees_a_deux_synchros_passent_en_580() -> None:
    """AXE-968 : « trésorerie » −50 € écrite le 13/11, +50 € le 16/11. Le
    passage horaire voit tout le grand livre, pas seulement le dernier lot."""
    premiere = _operation("s", -50_00, compte="471", libelle="trésorerie")
    seconde = _operation("e", 50_00, compte="471", libelle="trésorerie")
    reprise = reprises([premiere, seconde], seulement_en_attente=True)
    assert reprise.paires == 1
    assert "471" not in _soldes([premiere, seconde, *reprise.ecritures])


def test_deux_comptes_du_dossier_se_reconnaissent_malgre_des_libelles_differents() -> None:
    """AXE-968 : « trésorerie » −20 € sur un compte, « cotisation TVA » +20 €
    sur un autre. Écrites au 512 avant les sous-comptes, leurs reclassements
    AXE-832 disent de quel compte elles viennent."""
    sortie = _operation("s", -20_00, compte="471", libelle="trésorerie")
    entree = _operation("e", 20_00, compte="471", libelle="cotisation impôts, TVA")
    assert reprises([sortie, entree]).paires == 0  # sans les comptes : rien
    ventilations = [
        v
        for e, compte in ((sortie, "5121"), (entree, "5123"))
        if (v := ecriture_de_ventilation(e, compte)) is not None
    ]
    grand_livre = [sortie, entree, *ventilations]
    assert sous_comptes_ventiles(grand_livre) == {"s": "5121", "e": "5123"}
    reprise = reprises([sortie, entree], sous_comptes=sous_comptes_ventiles(grand_livre))
    assert reprise.paires == 1


def test_le_passage_horaire_ne_deplace_pas_une_operation_classee() -> None:
    """Une jambe classée par un humain (645) reste où elle est : le passage
    automatique ne regarde que le 471. La reprise manuelle, elle, la prend."""
    classee = _operation("s", -20_00, compte="645")
    attente = _operation("e", 20_00, compte="471", libelle="cotisation URSSAF")
    assert reprises([classee, attente], seulement_en_attente=True).paires == 0
    assert reprises([classee, attente]).paires == 1
