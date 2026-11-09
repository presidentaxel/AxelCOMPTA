"""AXE-836 : la migration reprend le moyen de paiement depuis l'archive brute,
et la synchro le garde avec la proposition."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def test_la_migration_reprend_le_moyen_de_paiement(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    # Juste avant cette migration. Partir de e9c2a7f14b63 referait la
    # numérotation (AXE-807), qui recrée compteurs_ecritures déjà posée
    # par create_all dans creer_dossier.
    command.upgrade(cfg, "c8d4e2f7a915")
    creer_dossier("d1")
    with engine.begin() as connexion:
        for transaction_id, type_operation, recu in (
            ("t1", "card", "2026-03-01"),
            ("t1", "transfer", "2026-03-02"),  # la dernière version l'emporte
            ("t2", "unknown", "2026-03-01"),
        ):
            connexion.execute(
                text(
                    "INSERT INTO ingestion_brut (id, dossier_id, source, transaction_id, "
                    "updated_at, payload, recu_le) VALUES (:id, 'd1', 'digifactory', :t, NULL, "
                    ":p, :r)"
                ),
                {
                    "id": f"{transaction_id}-{recu}",
                    "t": transaction_id,
                    "p": json.dumps({"id": transaction_id, "operation_type": type_operation}),
                    "r": recu,
                },
            )
        for transaction_id in ("t1", "t2"):
            connexion.execute(
                text(
                    "INSERT INTO propositions_categorisation (ecriture_id, dossier_id, categorie, "
                    "etage, confiance) VALUES (:e, 'd1', 'carburant', 'REGLE', 0.95)"
                ),
                {"e": f"d1:digifactory-{transaction_id}"},
            )

    # Jusqu'à cette migration seulement : les suivantes recréeraient des
    # tables déjà posées par create_all (journal_portefeuille, AXE-812).
    command.upgrade(cfg, "d1e7a3c9f264")

    with engine.connect() as connexion:
        lignes = connexion.execute(
            text("SELECT ecriture_id, moyen_paiement FROM propositions_categorisation")
        ).all()
    moyens = {str(ecriture): moyen for ecriture, moyen in lignes}
    assert moyens == {"d1:digifactory-t1": "transfer", "d1:digifactory-t2": None}
