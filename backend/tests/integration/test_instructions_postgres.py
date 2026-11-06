"""Qualifications d'anomalies en Postgres (AXE-814) : elles survivent à un
nouveau dépôt (redémarrage), et ne se modifient pas."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from axelcompta.anomaly.instruction import TransitionRefusee
from axelcompta.anomaly.instruction_postgres import PostgresInstructions
from axelcompta.core.ids import DossierId

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 5, 9, tzinfo=UTC)
BACKEND = Path(__file__).resolve().parent.parent.parent


def test_une_qualification_survit_a_un_redemarrage(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    dossier = DossierId(id_unique)
    PostgresInstructions(engine).instruire(
        dossier, "personnel:e1", "en_instruction", "arthur", "", LE
    )
    PostgresInstructions(engine).instruire(
        dossier, "personnel:e1", "justifiee", "louis", " ok ", LE
    )

    relu = PostgresInstructions(engine)  # nouveau dépôt, comme après un redémarrage

    assert relu.etats(dossier) == {"personnel:e1": "justifiee"}
    assert [
        (e.etat, e.acteur, e.commentaire) for e in relu.historique(dossier, "personnel:e1")
    ] == [
        ("en_instruction", "arthur", ""),
        ("justifiee", "louis", "ok"),
    ]
    with pytest.raises(TransitionRefusee):
        relu.instruire(dossier, "personnel:e1", "faux_positif", "louis", "", LE)
    assert relu.etats(DossierId("autre")) == {}


def test_une_qualification_ne_se_modifie_pas(engine: Engine, id_unique: str) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    with engine.begin() as connexion:
        connexion.execute(text("INSERT INTO tenants (id, nom) VALUES (:t, 'T')"), {"t": id_unique})
        connexion.execute(
            text(
                "INSERT INTO dossiers (id, tenant_id, forme_juridique, regime_imposition, "
                "regime_tva, nom, tva_recettes_regime, exercice_debut, plateformes, "
                "mode_acces_bancaire) VALUES (:d, :d, 'SASU', 'IS', 'franchise', 'X', "
                "'franchise', '2026-01-01', '[]', 'gestionnaire')"
            ),
            {"d": id_unique},
        )
    PostgresInstructions(engine).instruire(
        DossierId(id_unique), "a1", "en_instruction", "louis", "", LE
    )
    with engine.begin() as connexion, pytest.raises(DBAPIError):
        connexion.execute(text("UPDATE qualifications_anomalie SET etat = 'ouverte'"))
