"""AXE-872 : le bouton « Tester » ne contacte que le fournisseur, sans rien
envoyer à un chauffeur, et rend un message lisible."""

from __future__ import annotations

from typing import Any

import pytest

from axelcompta import tester_branchement
from axelcompta.core.ids import TenantId
from axelcompta.ingestion.providers.base import ProviderHealth
from axelcompta.ingestion.providers.rollee import RolleeHttpClient
from axelcompta.tenants.branchements import Branchement, nouveau
from axelcompta.workflow.rappels_envoi import ExpediteurSmtp

T = TenantId("t")
SMTP = {"hote": "h", "port": "587", "utilisateur": "u", "mot_de_passe": "p", "expediteur": "e"}


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _branchement(type_: str, fournisseur: str, parametres: dict[str, str]) -> Branchement:
    return nouveau([], T, type_, fournisseur, "X", parametres)


def test_un_smtp_qui_accepte_les_identifiants_est_ok_sans_envoi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifies: list[str] = []
    monkeypatch.setattr(ExpediteurSmtp, "verifier", lambda self: verifies.append("ok"))
    essai = tester_branchement.tester(_branchement("mail", "smtp", SMTP))
    assert (essai.statut, verifies) == ("ok", ["ok"]) and "Aucun e-mail" in essai.message


def test_un_smtp_qui_refuse_donne_la_raison(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_self: Any) -> None:
        raise ConnectionError("authentification refusée")

    monkeypatch.setattr(ExpediteurSmtp, "verifier", refuse)
    essai = tester_branchement.tester(_branchement("mail", "smtp", SMTP))
    assert essai.statut == "echec" and "authentification refusée" in essai.message


def test_digifactory_dit_si_le_jeton_est_accepte(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Provider:
        def __init__(self, client_reel: Any) -> None:
            self.client = client_reel

        async def health(self) -> ProviderHealth:
            return ProviderHealth(ok=False, message="401")

    monkeypatch.setattr(tester_branchement, "DigifactoryProvider", _Provider)
    essai = tester_branchement.tester(
        _branchement("digifactory", "digifactory", {"jeton": "j", "url": "https://digi"})
    )
    assert essai.statut == "echec" and "401" in essai.message


def test_un_fournisseur_de_sms_ne_se_teste_pas_sans_envoyer() -> None:
    sms = {"url": "https://sms", "cle_api": "k", "expediteur": "S"}
    assert tester_branchement.tester(_branchement("sms", "http", sms)).statut == "indisponible"


def test_rollee_renouvelle_son_jeton_et_le_fait_garder(monkeypatch: pytest.MonkeyPatch) -> None:
    """AXE-818 : le test Rollee renouvelle le jeton ; le nouveau est rendu
    à l'appelant, qui le garde dans le branchement."""

    class _Client:
        environnement = "sandbox"

        def __init__(self, rappel: Any) -> None:
            self.rappel = rappel

        async def renouveler(self) -> str:
            self.rappel("neuf")
            return "neuf"

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        RolleeHttpClient,
        "depuis_parametres",
        classmethod(lambda _cls, _p, rappel=None: _Client(rappel)),
    )
    gardes: list[str] = []
    rollee = _branchement("rollee", "rollee", {"jeton": "vieux", "environnement": "sandbox"})
    essai = tester_branchement.tester(rollee, gardes.append)
    assert essai.statut == "ok" and gardes == ["neuf"]
