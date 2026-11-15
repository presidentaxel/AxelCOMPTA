"""La vue expert d'une semaine montre le jour Rollee et le virement bancaire."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from axelcompta.core.ids import EcritureId
from axelcompta.explication_semaines import expliquer_semaines
from axelcompta.ingestion.ecritures_semaines import SUFFIXE_SOLDE
from axelcompta.ingestion.settlements_plateforme import MOTIF_DOUBLON
from axelcompta.ledger.models import Journal
from tests.test_revenus_semaines import AUJOURD_HUI, OUVERTURE, POP, _jour, _virement


def test_une_semaine_deja_soldee_montre_le_jour_et_le_virement() -> None:
    stocke = _jour()
    detail = replace(
        stocke,
        etat="reconcilie",
        settlement=replace(
            stocke.settlement,
            gross_earnings_cts=100_000,
            commission_cts=15_200,
            net_payout_cts=84_800,
        ),
    )
    virement = _virement(84_800)
    solde = replace(virement, id=EcritureId(f"V1{SUFFIXE_SOLDE}"), journal=Journal.OD)
    (vue,) = expliquer_semaines([detail], [OUVERTURE, virement, solde], AUJOURD_HUI)
    assert vue.etat == "solde"
    assert (vue.du_cts, vue.paye_cts, vue.frais_cts, vue.ecart_cts) == (84_800, 84_800, 0, 0)
    assert (vue.jours[0].brut_cts, vue.jours[0].commission_cts, vue.jours[0].du_cts) == (
        100_000,
        15_200,
        84_800,
    )
    assert vue.virements[0].libelle == POP
    assert (vue.virements[0].montant_cts, vue.virements[0].nature, vue.virements[0].compte) == (
        84_800,
        "hebdomadaire",
        "471",
    )


def test_les_especes_ne_sont_pas_attendues_du_virement() -> None:
    (vue,) = expliquer_semaines([_jour(100_00, 30)], [OUVERTURE, _virement(70_00)], AUJOURD_HUI)
    assert vue.jours[0].especes_cts == 30_00
    assert vue.jours[0].du_cts == 70_00
    assert (vue.etat, vue.paye_cts) == ("solde", 70_00)


def test_un_retrait_instantane_affiche_ses_frais() -> None:
    virement = replace(
        _virement(84_800 - 99, libelle="Stichting Custodian Uber Payments"),
        date=date(2026, 10, 8),
    )
    (vue,) = expliquer_semaines([_jour()], [OUVERTURE, virement], AUJOURD_HUI)
    assert vue.etat == "solde"
    assert vue.frais_cts == 99
    assert vue.virements[0].nature == "instantane"


def test_un_ecart_est_chiffre_et_le_virement_reste_visible() -> None:
    (vue,) = expliquer_semaines([_jour()], [OUVERTURE, _virement(800_00)], AUJOURD_HUI)
    assert vue.etat == "a_verifier"
    assert vue.ecart_cts == 4_800
    assert vue.motif == "48,00 € encore dus par Uber"
    assert vue.virements[0].montant_cts == 800_00


def test_un_virement_classe_ailleurs_garde_son_motif() -> None:
    stocke = replace(_jour(), etat="a_verifier", motif="virement classé en 455")
    (vue,) = expliquer_semaines([stocke], [OUVERTURE, _virement(84_800, "455")], AUJOURD_HUI)
    assert vue.etat == "a_verifier"
    assert vue.motif == "virement classé en 455"
    assert vue.du_cts == vue.paye_cts
    assert vue.virements[0].compte == "455"


def test_une_copie_rollee_ne_double_pas_le_du() -> None:
    original = _jour()
    copie = replace(original, id=f"{original.id}:copie", etat="a_verifier", motif=MOTIF_DOUBLON)
    (vue,) = expliquer_semaines([original, copie], [OUVERTURE, _virement(84_800)], AUJOURD_HUI)
    assert vue.du_cts == 84_800
    assert len(vue.jours) == 1


def test_avant_le_premier_releve_bancaire_la_semaine_reste_en_attente() -> None:
    ouverture = replace(OUVERTURE, date=date(2026, 11, 1))
    (vue,) = expliquer_semaines([_jour()], [ouverture], AUJOURD_HUI)
    assert vue.etat == "en_attente"
    assert vue.motif == "Aucun relevé bancaire sur cette période."
    assert vue.virements == ()
    assert len(vue.jours) == 1
