"""AXE-808 : le câblage des rappels (`axelcompta/rappels.py`) avec des dépôts
en mémoire : l'e-mail vient du compte du chauffeur, un SMS n'a pas de numéro."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from axelcompta import rappels
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.demo_comptes import Invitation, StatutInvitation, SupabaseConfig
from axelcompta.tenants.branchements import BranchementsMemoire, nouveau
from axelcompta.workflow.rappels_envoi import EnvoisMemoire, envois_du_rappel

T, D = TenantId("t"), DossierId("d1")
LE = datetime(2026, 11, 9, 10, 0)


class _Comptes:
    def statut(self, dossier_id: DossierId) -> Invitation:
        return Invitation(dossier_id, "karim@example.com", StatutInvitation.ACTIF)


class _Expediteur:
    envoyes: list[str] = []

    def envoyer(self, destinataire: str, sujet: str, texte: str) -> None:
        self.envoyes.append(destinataire)


def test_envoyer_lit_l_adresse_du_chauffeur_et_ignore_le_sms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )
    depot = EnvoisMemoire()
    smtp = {"hote": "h", "port": "587", "utilisateur": "u", "mot_de_passe": "p", "expediteur": "e"}
    sms = {"url": "https://sms", "cle_api": "k", "expediteur": "SERENITY"}
    branchements = BranchementsMemoire()
    branchements.enregistrer([nouveau([], T, "mail", "smtp", "E-mail", smtp)], "a", LE)
    branchements.enregistrer([nouveau([], T, "sms", "http", "SMS", sms)], "a", LE)
    depot.creer(envois_du_rappel("r1", T, D, "Message", ["mail", "sms"], ["mail", "sms"], LE))
    expediteur = _Expediteur()

    def fabrique(*_a: Any, **_k: Any) -> Any:
        return None

    monkeypatch.setattr(rappels, "PostgresEnvois", lambda _e: depot)
    monkeypatch.setattr(rappels, "PostgresBranchements", lambda _e: branchements)
    monkeypatch.setattr(rappels, "SupabaseCompteRepository", lambda _c: _Comptes())
    monkeypatch.setattr(SupabaseConfig, "depuis_env", staticmethod(fabrique))
    monkeypatch.setattr(rappels, "PostgresLedgerService", fabrique)
    monkeypatch.setattr(rappels, "PostgresDecisionRepository", fabrique)
    monkeypatch.setattr(rappels, "ecritures_a_trancher", lambda *_a: ())
    monkeypatch.setattr(rappels, "expediteur_de", lambda _i: expediteur)

    bilan = rappels.envoyer(None, LE)  # type: ignore[arg-type]

    assert (bilan["envoye"], bilan["ignore"]) == (1, 1)
    assert expediteur.envoyes == ["karim@example.com"]
