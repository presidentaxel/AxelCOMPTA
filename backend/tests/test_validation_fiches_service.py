"""AXE-989 : la validation d'une fiche, composée de ses sources, et gardée
seulement quand elle change."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.fiches_import import nouvelle_fiche
from axelcompta.validation_fiches_service import avec_validation, valider_fiche

LE = datetime(2026, 11, 18, 10, tzinfo=UTC)
FICHE = replace(
    nouvelle_fiche("f", TenantId("T"), "Konate", "K", "", "b", LE),
    dossier_id=DossierId("DIGI_95245"),
)
CHAMPS = {"date_creation": "2025-01-10", "cloture": "31/12", "plateformes": "uber"}


def test_sans_banque_ni_rollee_le_chauffeur_n_est_pas_importe() -> None:
    fiche = replace(FICHE, champs={**FICHE.champs, **CHAMPS})
    validation = valider_fiche(fiche, [], [], [], [], LE)
    assert not validation.importe
    assert "Digifactory relié : Aucun compte Digifactory retenu" in validation.manques("banque")[0]
    assert any("Uber à jour sur Rollee" in m for m in validation.manques("plateformes"))


def test_la_validation_n_est_gardee_que_si_elle_change() -> None:
    fiche = replace(FICHE, champs={**FICHE.champs, **CHAMPS})
    validation = valider_fiche(fiche, [], [], [], [], LE)
    gardee = avec_validation(fiche, validation)
    assert gardee is not None
    plus_tard = valider_fiche(gardee, [], [], [], [], LE.replace(hour=11))
    assert avec_validation(gardee, plus_tard) is None
