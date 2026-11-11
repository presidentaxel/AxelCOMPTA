"""AXE-819 : le chauffeur relie ses plateformes via Rollee Connect."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.plateformes_rollee import (
    RolleeNonBranche,
    ServicesRollee,
    ouvrir_session,
    relire_comptes,
)
from axelcompta.tenants.branchements import (
    Branchement,
    BranchementsMemoire,
    Modification,
    modifier,
    nouveau,
)
from axelcompta.tenants.models import Dossier

T = TenantId("t")
LE = datetime(2026, 11, 11, tzinfo=UTC)
DOSSIER = Dossier(
    DossierId("DIGI_1"),
    T,
    "SAS",
    "IS",
    "reel_normal",
    "MK",
    "assujetti_taux_reduit",
    date(2026, 1, 1),
    plateformes=("uber", "bolt"),
)


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


class _Client:
    def __init__(self, journal: list[str], garder: Any) -> None:
        self.journal = journal
        self.garder = garder

    async def creer_utilisateur(self, metadonnees: dict[str, str]) -> dict[str, Any]:
        self.journal.append(f"creer {metadonnees}")
        return {
            "id": "user-1",
            "link": "https://connect/1",
            "session_expires_at": "2026-11-11T10:30",
        }

    async def nouvelle_session(self, user_id: str) -> dict[str, Any]:
        self.journal.append(f"session {user_id}")
        return {"link": "https://connect/2", "session": "s2"}

    async def comptes(self, user_id: str) -> list[dict[str, Any]]:
        self.journal.append(f"comptes {user_id}")
        self.garder("jeton-neuf")
        return [
            {"id": "acc-u", "name": "Uber", "connected": True},
            {"id": "acc-b", "name": "Bolt", "connected": False},
        ]

    async def aclose(self) -> None:
        return None


def _services(rollee: bool = True) -> tuple[ServicesRollee, list[str], Branchement | None]:
    branchements = BranchementsMemoire()
    cree = None
    if rollee:
        cree = nouveau(
            [], T, "rollee", "rollee", "Rollee", {"jeton": "j", "environnement": "sandbox"}
        )
        branchements.enregistrer([cree], "admin", LE)
    journal: list[str] = []
    services = ServicesRollee(
        branchements,
        ComptesRolleeMemoire(),
        fabrique=lambda _b, garder: _Client(journal, garder),  # type: ignore[arg-type,return-value]
        maintenant=lambda: LE,
    )
    return services, journal, cree


def test_le_premier_lien_cree_le_user_avec_le_seul_dossier_puis_les_suivants_non() -> None:
    services, journal, branchement = _services()
    premiere = asyncio.run(ouvrir_session(services, DOSSIER))
    seconde = asyncio.run(ouvrir_session(services, DOSSIER))
    assert (premiere.lien, seconde.lien) == ("https://connect/1", "https://connect/2")
    assert journal == ["creer {'dossier_id': 'DIGI_1'}", "session user-1"]
    utilisateur = services.comptes.utilisateur(DOSSIER.id)
    assert utilisateur is not None and branchement is not None
    assert utilisateur.branchement_id == branchement.id


def test_les_comptes_relus_sont_gardes_et_le_jeton_renouvele_aussi() -> None:
    services, journal, branchement = _services()
    assert asyncio.run(relire_comptes(services, DOSSIER)) == []  # pas de user : aucun appel
    assert journal == []
    asyncio.run(ouvrir_session(services, DOSSIER))
    comptes = asyncio.run(relire_comptes(services, DOSSIER))
    assert [(c.nom, c.etat) for c in comptes] == [("Uber", "connecte"), ("Bolt", "a_reconnecter")]
    assert [c.nom for c in services.comptes.comptes(DOSSIER.id)] == ["Uber", "Bolt"]
    assert branchement is not None
    (garde,) = services.branchements.lister(T)
    assert garde.parametres()["jeton"] == "jeton-neuf"


def test_plusieurs_rollee_sans_choix_ne_prennent_pas_un_defaut() -> None:
    services, _journal, _premier = _services()
    second = nouveau(
        services.branchements.lister(T),
        T,
        "rollee",
        "rollee",
        "Autre",
        {"jeton": "k", "environnement": "sandbox"},
    )
    services.branchements.enregistrer([second], "admin", LE)
    with pytest.raises(RolleeNonBranche, match="Plusieurs comptes"):
        asyncio.run(ouvrir_session(services, DOSSIER))


def test_sans_branchement_rollee_le_chauffeur_sait_quoi_faire() -> None:
    services, _journal, _ = _services(rollee=False)
    with pytest.raises(RolleeNonBranche, match="gestionnaire"):
        asyncio.run(ouvrir_session(services, DOSSIER))


def test_un_branchement_desactive_bloque_le_user_qui_en_depend() -> None:
    services, _journal, branchement = _services()
    asyncio.run(ouvrir_session(services, DOSSIER))
    assert branchement is not None
    services.branchements.enregistrer(
        modifier(services.branchements.lister(T), branchement.id, Modification(actif=False)),
        "admin",
        LE,
    )
    with pytest.raises(RolleeNonBranche, match="désactivé"):
        asyncio.run(relire_comptes(services, DOSSIER))
