"""La commande `python -m axelcompta.agregats_portefeuille` contre Postgres."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine

from axelcompta.agregats_portefeuille import main
from axelcompta.demo_seed import TENANT_DEMO, amorcer_demo
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def portefeuille(engine: Engine) -> Engine:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    amorcer_demo(
        PostgresDossierRepository(engine),
        PostgresLedgerService(engine),
        PostgresPropositionRepository(engine),
    )
    return engine


def _lancer(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> int:
    monkeypatch.setattr(
        sys, "argv", ["agregats_portefeuille", "--tenant", str(TENANT_DEMO), *arguments]
    )
    return main()


def test_recalculer_puis_verifier_ne_trouve_aucun_ecart(
    portefeuille: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _lancer(monkeypatch, "--recalculer") == 0
    assert "3 dossier(s) recalculé(s)" in capsys.readouterr().out

    assert _lancer(monkeypatch, "--verifier") == 0
    assert "3 à jour, 0 périmé(s)" in capsys.readouterr().out

    assert _lancer(monkeypatch, "--recalculer") == 0
    assert "0 dossier(s) recalculé(s)" in capsys.readouterr().out


def test_verifier_trouve_un_agregat_modifie_a_la_main(
    portefeuille: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un agrégat « à jour » qui ne dit plus la vérité, sans écriture pour le périmer."""
    _lancer(monkeypatch, "--recalculer")
    capsys.readouterr()
    with portefeuille.begin() as connexion:
        connexion.execute(
            text("UPDATE agregats_dossier SET ca_ht_cts = ca_ht_cts + 100 WHERE dossier_id = :d"),
            {"d": "DEMO_sophie"},
        )

    assert _lancer(monkeypatch, "--verifier") == 1
    sortie = capsys.readouterr().out
    assert "1 écart(s)" in sortie
    assert "ÉCART DEMO_sophie" in sortie


def test_recalculer_tout_remet_juste_un_agregat_modifie_a_la_main(
    portefeuille: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _lancer(monkeypatch, "--recalculer")
    with portefeuille.begin() as connexion:
        connexion.execute(text("UPDATE agregats_dossier SET ca_ht_cts = ca_ht_cts + 100"))

    assert _lancer(monkeypatch, "--recalculer", "--tout") == 0
    capsys.readouterr()
    assert _lancer(monkeypatch, "--verifier") == 0


def test_un_seul_dossier(
    portefeuille: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _lancer(monkeypatch, "--recalculer", "--dossier", "DEMO_karim") == 0
    assert "1 dossier(s) recalculé(s)" in capsys.readouterr().out
