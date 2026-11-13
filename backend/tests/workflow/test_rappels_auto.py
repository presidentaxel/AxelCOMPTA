"""Règles de rappel automatiques (AXE-808), dont « reliez vos plateformes » (AXE-890)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.rappels_auto import Regle, rappels_a_creer

JOUR = date(2026, 11, 12)
DOSSIER = Dossier(
    id=DossierId("d1"),
    tenant_id=TenantId("t"),
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="MK DRIVING",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
)


def _regle(declencheur: str, jours: int | None = 7, actif: bool = True) -> Regle:
    return Regle("r1", "Reliez vos plateformes", ("mail",), "tous", (), declencheur, jours, actif)


def _deja(*jours: date) -> dict[tuple[str, str], list[datetime]]:
    return {("r1", "d1"): [datetime(j.year, j.month, j.day, 9, tzinfo=UTC) for j in jours]}


def test_sans_plateforme_reliee_le_rappel_part() -> None:
    (rappel,) = rappels_a_creer(
        [_regle("plateformes_non_reliees")], [DOSSIER], {}, {}, JOUR, frozenset({DOSSIER.id})
    )
    assert (rappel.dossier_id, rappel.message) == (DOSSIER.id, "Reliez vos plateformes")


def test_une_plateforme_reliee_arrete_les_rappels() -> None:
    assert rappels_a_creer([_regle("plateformes_non_reliees")], [DOSSIER], {}, {}, JOUR) == []


def test_au_plus_une_fois_tous_les_n_jours() -> None:
    regle, sans = [_regle("plateformes_non_reliees")], frozenset({DOSSIER.id})
    assert rappels_a_creer(regle, [DOSSIER], _deja(date(2026, 11, 8)), {}, JOUR, sans) == []
    assert len(rappels_a_creer(regle, [DOSSIER], _deja(date(2026, 11, 4)), {}, JOUR, sans)) == 1


def test_une_regle_inactive_ou_sans_jours_ne_part_pas() -> None:
    sans = frozenset({DOSSIER.id})
    assert (
        rappels_a_creer(
            [_regle("plateformes_non_reliees", actif=False)], [DOSSIER], {}, {}, JOUR, sans
        )
        == []
    )
    assert (
        rappels_a_creer(
            [_regle("plateformes_non_reliees", jours=None)], [DOSSIER], {}, {}, JOUR, sans
        )
        == []
    )


def test_les_operations_en_attente_relancent_apres_n_jours() -> None:
    regle = [_regle("a_traiter")]
    assert rappels_a_creer(regle, [DOSSIER], {}, {DOSSIER.id: date(2026, 11, 1)}, JOUR)
    assert rappels_a_creer(regle, [DOSSIER], {}, {DOSSIER.id: date(2026, 11, 10)}, JOUR) == []


def test_avant_cloture_dans_la_fenetre_seulement() -> None:
    assert rappels_a_creer([_regle("avant_cloture", jours=60)], [DOSSIER], {}, {}, JOUR)
    assert rappels_a_creer([_regle("avant_cloture", jours=10)], [DOSSIER], {}, {}, JOUR) == []
