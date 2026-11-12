"""AXE-872 : la migration `b8d4e1f7a2c6` reprend le SMTP et le SMS déjà
branchés comme branchements par défaut, sans rien perdre, et le downgrade
les remet en place."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def test_le_smtp_existant_devient_le_branchement_par_defaut_et_revient(engine: Engine) -> None:
    cfg = _config()
    command.upgrade(cfg, "e6b2d9f4a371")
    le = datetime(2026, 11, 9, tzinfo=UTC)
    with engine.begin() as connexion:
        connexion.execute(text("INSERT INTO tenants (id, nom) VALUES ('t', 'T')"))
        connexion.execute(
            text(
                "INSERT INTO integrations_envoi VALUES "
                "('t', 'mail', 'smtp', 'chiffre-mail', 'louis', :le), "
                "('t', 'sms', 'http', 'chiffre-sms', 'louis', :le)"
            ),
            {"le": le},
        )

    command.upgrade(cfg, "b8d4e1f7a2c6")
    with engine.connect() as connexion:
        repris = connexion.execute(
            text(
                "SELECT type, nom, parametres_chiffres, par_defaut, actif "
                "FROM branchements ORDER BY type"
            )
        ).all()
    assert [tuple(r) for r in repris] == [
        ("mail", "E-mail", "chiffre-mail", True, True),
        ("sms", "SMS", "chiffre-sms", True, True),
    ]

    command.downgrade(cfg, "e6b2d9f4a371")
    with engine.connect() as connexion:
        remis = connexion.execute(
            text("SELECT canal, parametres_chiffres FROM integrations_envoi ORDER BY canal")
        ).all()
    assert [tuple(r) for r in remis] == [("mail", "chiffre-mail"), ("sms", "chiffre-sms")]
    command.upgrade(cfg, "head")  # le nettoyage du test attend le schéma de tête
