from __future__ import annotations

import dataclasses

import pytest

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.controles_tdfc import LiasseIncoherente, controler_liasse
from axelcompta.closing.models import LiassePivot
from axelcompta.demo_chauffeurs_type import construire_ledger, parametres_cloture
from axelcompta.ingestion.providers.chauffeurs_demo import PROFIL_KARIM


def _liasse() -> LiassePivot:
    ledger, _ = construire_ledger(PROFIL_KARIM)
    return ClotureSimplifieeService(ledger).cloturer(
        PROFIL_KARIM.dossier_id, "2025", parametres_cloture(PROFIL_KARIM)
    )


def test_la_liasse_de_karim_passe_les_controles() -> None:
    controler_liasse(_liasse())


def test_un_passif_faux_arrete_le_controle() -> None:
    liasse = _liasse()
    cassee = dataclasses.replace(liasse, cases={**liasse.cases, "2033A.180": 0})
    with pytest.raises(LiasseIncoherente, match="actif net"):
        controler_liasse(cassee)


def test_la_tva_due_cadre_avec_le_tableau_de_bord() -> None:
    cases = _liasse().cases
    assert cases["CA3.DUE"] == cases["CA3.COLLECTEE"] - cases["CA3.DEDUCTIBLE"]
    assert cases["CA3.DUE"] == cases["TVA_A_PAYER"]
