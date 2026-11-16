"""AXE-940 : un admin peut être lui-même l'expert-comptable du portefeuille."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.workflow.expert_comptable import (
    ROLE_EXPERT,
    TEXTE_ENGAGEMENT,
    VERSION_ENGAGEMENT,
    Engagement,
    ExpertNonHabilite,
    Habilitation,
    expert_actif,
    role_de_l_expert,
)

LE = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
HABILITATION = Habilitation(
    tenant_id=TenantId("T"),
    email="moi@cabinet.fr",
    nom="Expert",
    cabinet="Cabinet",
    numero_ordre="13-000001",
    lettre_mission="LM-1",
    date_lettre=date(2026, 1, 1),
    dossiers=(DossierId("D1"),),
    accordee_par=UserId("admin"),
    accordee_le=LE,
)
ENGAGEMENT = Engagement(
    tenant_id=TenantId("T"),
    email="moi@cabinet.fr",
    version=VERSION_ENGAGEMENT,
    texte=TEXTE_ENGAGEMENT,
    adresse="test",
    acteur=UserId("moi"),
    accepte_le=LE,
)


def test_un_admin_declare_expert_garde_son_role() -> None:
    assert role_de_l_expert("admin") is None
    assert role_de_l_expert("membre") == ROLE_EXPERT
    assert role_de_l_expert("lecture") == ROLE_EXPERT
    assert role_de_l_expert(None) == ROLE_EXPERT


def test_le_mode_expert_s_ouvre_a_l_admin_habilite_et_engage() -> None:
    actif = expert_actif("admin", HABILITATION, ENGAGEMENT)
    assert actif.couvre(DossierId("D1"))
    with pytest.raises(ExpertNonHabilite, match="habilitation"):
        expert_actif("admin", None, None)
    with pytest.raises(ExpertNonHabilite, match="engagement"):
        expert_actif("admin", HABILITATION, None)


def test_un_membre_ou_un_lecteur_n_est_pas_expert_sans_le_role() -> None:
    for role in ("membre", "lecture", None):
        with pytest.raises(ExpertNonHabilite, match="Réservé"):
            expert_actif(role, HABILITATION, ENGAGEMENT)
