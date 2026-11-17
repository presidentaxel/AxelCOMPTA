"""`.env.dev` l'emporte sur `.env`. Une variable déjà posée reste."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from axelcompta.environnement import charger_environnement


def test_env_dev_emporte_sur_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    (tmp_path / ".env").write_text("ENV=production\nSENTRY_DSN=secret\n", encoding="utf-8")
    (tmp_path / ".env.dev").write_text("ENV=dev\n", encoding="utf-8")
    charger_environnement(tmp_path)
    assert os.environ["ENV"] == "dev"
    assert os.environ["SENTRY_DSN"] == "secret"


def test_une_variable_deja_posee_n_est_pas_ecrasee_par_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEJA", "reste")
    (tmp_path / ".env").write_text("DEJA=ecrase\n", encoding="utf-8")
    charger_environnement(tmp_path)
    assert os.environ["DEJA"] == "reste"
