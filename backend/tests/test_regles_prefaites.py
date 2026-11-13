"""Les règles préfaites se posent une fois, même si la page est rouverte."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

import axelcompta.api.routes as demo_api
from axelcompta.core.ids import TenantId
from axelcompta.tenants.orm import regles_rappel


def test_cent_ouvertures_ne_creent_que_trois_regles(monkeypatch: pytest.MonkeyPatch) -> None:
    moteur = create_engine("sqlite://", poolclass=StaticPool)
    regles_rappel.create(moteur)
    monkeypatch.setattr(demo_api, "appliquer_rls", lambda connexion: None)
    monkeypatch.setattr(demo_api, "_engine", lambda: moteur)

    tenant = TenantId("tenant-demo")
    for _ in range(100):
        demo_api._assurer_regles_prefaites(tenant)

    with moteur.connect() as connexion:
        nombre = connexion.execute(
            select(func.count())
            .select_from(regles_rappel)
            .where(regles_rappel.c.tenant_id == str(tenant))
        ).scalar()
    assert nombre == len(demo_api.REGLES_PREFAITES)
