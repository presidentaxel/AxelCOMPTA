"""Suite d'AXE-983 : le choix Pro/Perso de la fiche, porté au dossier."""

from __future__ import annotations

import json

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.tenants.fiches_import_comptes import (
    a_appliquer,
    choix_de_la_fiche,
    en_desaccord,
)

D = DossierId("DIGI_24951")


def _champs(*lignes: dict[str, str]) -> dict[str, str]:
    return {"comptes_bancaires": json.dumps(list(lignes))}


def test_seuls_les_comptes_a_decider_recoivent_le_choix_de_la_fiche() -> None:
    champs = _champs(
        {"id": "1", "nom": "Bred", "usage": "pro"},
        {"id": "2", "nom": "Binta", "usage": "perso"},
        {"id": "3", "nom": "Kerfala", "usage": "perso"},
        {"id": "4", "nom": "Saidu", "usage": ""},
    )
    comptes = [
        CompteBancaire(D, "1", "5121", "Bred", retenu=True),
        CompteBancaire(D, "2", "5123", "Binta", retenu=None),
        CompteBancaire(D, "3", "5122", "Kerfala", retenu=True),
        CompteBancaire(D, "4", "5124", "Saidu", retenu=None),
    ]
    choix = choix_de_la_fiche(champs)
    assert a_appliquer(comptes, choix) == (("5123", False),)
    assert en_desaccord(comptes, choix) == ("5122",)


def test_les_anciennes_lignes_se_reconnaissent_par_le_nom() -> None:
    champs = {"comptes_bancaires": "Bred (retenu)\nLivret (écarté)\nAutre (à choisir)"}
    comptes = [CompteBancaire(D, "9", "5122", "Livret", retenu=None)]
    assert a_appliquer(comptes, choix_de_la_fiche(champs)) == (("5122", False),)


def test_une_fiche_vide_ne_decide_rien() -> None:
    assert choix_de_la_fiche({}) == ()
