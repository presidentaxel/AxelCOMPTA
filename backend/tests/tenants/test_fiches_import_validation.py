"""AXE-989 : les catégories et le statut lisent la validation gardée."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import TenantId
from axelcompta.tenants.fiches_import import nouvelle_fiche
from axelcompta.tenants.fiches_import_etat import etat_sections
from axelcompta.tenants.fiches_import_validation import (
    CHAMP_VALIDATION,
    PAS_ENCORE,
    manques_de_section,
    manques_gardes,
)

FICHE = nouvelle_fiche(
    "f", TenantId("T"), "Konate", "K", "", "b", datetime(2026, 11, 18, tzinfo=UTC)
)


def test_une_fiche_jamais_validee_attend_le_passage() -> None:
    assert manques_gardes({}, "banque") is None
    assert manques_de_section({}, "banque") == [PAS_ENCORE]
    assert manques_de_section({}, "entreprise") == []


def test_les_manques_gardes_rendent_la_categorie_incomplete() -> None:
    gardee = {"le": "2026-11-18T10:00", "banque": ["Digifactory relié"], "plateformes": []}
    fiche = replace(FICHE, champs={**FICHE.champs, CHAMP_VALIDATION: json.dumps(gardee)})
    etats = {e.cle: e for e in etat_sections(fiche, [], date(2026, 11, 18))}
    assert "Digifactory relié" in etats["banque"].manquants
    assert PAS_ENCORE not in etats["plateformes"].manquants
