"""AXE-819 : le chauffeur relie ses plateformes via Rollee Connect."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, date, datetime
from typing import Any

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.ingestion.webhooks_rollee import EvenementRollee, EvenementsRolleeMemoire
from axelcompta.plateformes_rollee import (
    RolleeNonBranche,
    ServicesRollee,
    Suivi,
    ouvrir_session,
    rattraper,
    recevoir,
    relire_comptes,
    traiter_evenements,
)
from axelcompta.tenants.branchements import (
    Branchement,
    BranchementsMemoire,
    Modification,
    modifier,
    nouveau,
)
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier, Tenant

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


# --- AXE-820 : webhooks et rattrapage ---------------------------------------


class _Reception:
    def __init__(self, parametres_chiffres: str | None) -> None:
        self.parametres = parametres_chiffres
        self.evenements = EvenementsRolleeMemoire()
        self.demandes: list[str] = []

    def branchement(self, _id: str) -> tuple[TenantId, str] | None:
        return (T, self.parametres) if self.parametres else None

    def garder(self, evenement: EvenementRollee) -> bool:
        return self.evenements.garder(evenement)

    def demander_traitement(self, tenant_id: TenantId) -> None:
        self.demandes.append(tenant_id)


def _avec_secret() -> str:
    cree = nouveau(
        [],
        T,
        "rollee",
        "rollee",
        "Rollee",
        {"jeton": "j", "environnement": "sandbox", "secret_webhook": "s3cret"},
    )
    return cree.parametres_chiffres


def _signer(corps: bytes) -> str:
    return hmac.new(b"s3cret", corps, hashlib.sha512).hexdigest()


def test_recevoir_verifie_garde_une_fois_et_depose_un_job() -> None:
    reception = _Reception(_avec_secret())
    corps = json.dumps({"action": "disconnect_account", "data": {"user_id": "user-1"}}).encode()
    assert recevoir(reception, "b1", corps, "mauvaise", LE) == "refuse"
    assert recevoir(reception, "b1", corps, _signer(corps), LE) == "garde"
    assert recevoir(reception, "b1", corps, _signer(corps), LE) == "deja_recu"
    assert reception.demandes == [T]
    assert recevoir(_Reception(None), "inconnu", corps, _signer(corps), LE) == "inconnu"
    assert recevoir(reception, "b1", b"x", _signer(b"x"), LE) == "illisible"


def _suivi(
    services: ServicesRollee, notifications: list[str], revenus: list[str] | None = None
) -> Suivi:
    dossiers = InMemoryDossierRepository()
    dossiers.enregistrer_tenant(Tenant(id=T, nom="T"))
    dossiers.enregistrer(DOSSIER)
    return Suivi(
        services=services,
        evenements=EvenementsRolleeMemoire(),
        dossiers=dossiers,
        notifier=lambda d: notifications.append(d),
        relever_revenus=_faux_releve(revenus) if revenus is not None else None,
    )


def _faux_releve(revenus: list[str]) -> Any:
    async def relever(dossier: Dossier) -> str:
        revenus.append(dossier.id)
        return "revenus lus"

    return relever


def _evenement(payload: dict[str, Any]) -> EvenementRollee:
    return EvenementRollee(
        json.dumps(payload), T, "b1", str(payload.get("type") or payload.get("action")), payload, LE
    )


def test_une_plateforme_perdue_previent_le_chauffeur_une_fois() -> None:
    services, _journal, _ = _services()
    asyncio.run(ouvrir_session(services, DOSSIER))
    notifications: list[str] = []
    suivi = _suivi(services, notifications)
    perte = {"action": "disconnect_account", "data": {"user_id": "user-1", "id": "acc-b"}}
    suivi.evenements.garder(_evenement(perte))
    suivi.evenements.garder(_evenement({**perte, "rejoue": 1}))

    resultat = traiter_evenements(suivi, T)

    assert notifications == ["DIGI_1"]  # Bolt perdu, pas deux fois
    assert resultat == "2 événements Rollee traités"
    assert suivi.evenements.a_traiter(T, 10) == []


def test_des_donnees_pretes_relevent_les_revenus_et_l_inconnu_est_ignore() -> None:
    services, _journal, _ = _services()
    asyncio.run(ouvrir_session(services, DOSSIER))
    revenus: list[str] = []
    suivi = _suivi(services, [], revenus)
    suivi.evenements.garder(
        _evenement({"type": "update_multi_endpoint", "data": {"user_id": "user-1"}})
    )
    suivi.evenements.garder(_evenement({"type": "rollee_connect_events", "data": {}}))
    suivi.evenements.garder(_evenement({"type": "update_endpoint", "data": {"user_id": "inconnu"}}))
    traiter_evenements(suivi, T)
    assert isinstance(suivi.evenements, EvenementsRolleeMemoire)
    resultats = sorted(e.resultat or "" for e in suivi.evenements.evenements.values())
    assert revenus == ["DIGI_1"]
    assert resultats == ["ignoré (rollee_connect_events)", "revenus lus", "user inconnu inconnu"]


def test_le_rattrapage_relit_chaque_dossier_relie() -> None:
    services, journal, _ = _services()
    asyncio.run(ouvrir_session(services, DOSSIER))
    revenus: list[str] = []
    lignes = rattraper(_suivi(services, [], revenus))
    assert revenus == ["DIGI_1"] and "comptes user-1" in journal
    assert lignes == ["revenus lus"]
