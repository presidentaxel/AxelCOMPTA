"""Prévenir les admins d'un cabinet par son SMTP par défaut (AXE-887, AXE-911)."""

from __future__ import annotations

from typing import Any

import pytest

from axelcompta import prevenir_admins as module
from axelcompta.core.ids import TenantId

T = TenantId("t")


class _Expediteur:
    def __init__(self, panne: bool = False) -> None:
        self.envois: list[tuple[str, str]] = []
        self.panne = panne

    def envoyer(self, destinataire: str, sujet: str, texte: str) -> None:
        if self.panne:
            raise ConnectionError("smtp")
        self.envois.append((destinataire, sujet))


class _Branchements:
    def __init__(self, _engine: Any) -> None:
        pass

    def lister(self, _tenant: TenantId) -> list[Any]:
        return []


def _preparer(
    monkeypatch: pytest.MonkeyPatch, smtp: object, admins: list[str], expediteur: _Expediteur
) -> None:
    monkeypatch.setattr(module, "PostgresBranchements", _Branchements)
    monkeypatch.setattr(module, "choisir", lambda *_a: smtp)
    monkeypatch.setattr(module, "admins", lambda *_a: admins)
    monkeypatch.setattr(module, "expediteur_de", lambda _b: expediteur)


def test_chaque_admin_recoit_le_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    expediteur = _Expediteur()
    _preparer(monkeypatch, object(), ["a@x.fr", "b@x.fr"], expediteur)
    assert module.prevenir_admins(None, T, "Sujet", "Texte") == "mail à 2 admin(s)"  # type: ignore[arg-type]
    assert [d for d, _s in expediteur.envois] == ["a@x.fr", "b@x.fr"]


def test_sans_smtp_ou_en_panne_la_raison_est_rendue(monkeypatch: pytest.MonkeyPatch) -> None:
    _preparer(monkeypatch, None, ["a@x.fr"], _Expediteur())
    assert "non envoyé" in module.prevenir_admins(None, T, "S", "T")  # type: ignore[arg-type]
    _preparer(monkeypatch, object(), ["a@x.fr"], _Expediteur(panne=True))
    assert module.prevenir_admins(None, T, "S", "T") == "envoi en échec : ConnectionError"  # type: ignore[arg-type]
