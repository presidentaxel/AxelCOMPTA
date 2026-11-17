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
from axelcompta.ingestion.comptes_rollee import (
    ComptesRolleeMemoire,
    UtilisateurRollee,
    depuis_rollee,
)
from axelcompta.ingestion.providers.rollee import RolleeIndisponible
from axelcompta.ingestion.rapprochement_rollee import empreinte, nom_du_profil
from axelcompta.ingestion.webhooks_rollee import EvenementRollee, EvenementsRolleeMemoire
from axelcompta.plateformes_rollee import (
    RolleeNonBranche,
    ServicesRollee,
    Suivi,
    ouvrir_session,
    rattraper,
    recevoir,
    relire_comptes,
    synchroniser_dossier,
    traiter_evenements,
)
from axelcompta.rapprochement_rollee_service import cle_empreintes
from axelcompta.revenus_rollee import _lire
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


def _deux_allocab(profils: dict[str, dict[str, str]] | None, erreur: int | None = None) -> Any:
    class Client:
        def __init__(self) -> None:
            self.lus: list[str] = []

        async def comptes(self, _user_id: str) -> list[dict[str, Any]]:
            return [
                {"id": "acc-barry", "name": "allocab-fleet-rev", "connected": True},
                {"id": "acc-autre", "name": "allocab-fleet-rev", "connected": True},
            ]

        async def profil(self, account_id: str) -> dict[str, str]:
            if erreur is not None:
                raise RolleeIndisponible("profil illisible", erreur)
            return (profils or {})[account_id]

        async def revenus(self, account_id: str, _depuis: date, _jusqua: date) -> dict[str, Any]:
            self.lus.append(account_id)
            return {}

        async def aclose(self) -> None:
            return None

    return Client()


def test_un_lien_cree_retient_tous_les_comptes_sans_lire_le_profil() -> None:
    services, _, branchement = _services()
    assert branchement is not None
    services.fabrique = lambda _b, _g: _deux_allocab(None)
    services.comptes.enregistrer_utilisateur(
        UtilisateurRollee(DOSSIER.id, "user-cree", branchement.id), LE
    )
    comptes = asyncio.run(relire_comptes(services, DOSSIER))
    assert [(c.account_id, c.retenu, c.titulaire_autre) for c in comptes] == [
        ("acc-barry", True, False),
        ("acc-autre", True, False),
    ]


def test_deux_comptes_allocab_ne_retiennent_que_le_nom_du_dossier() -> None:
    services, _, branchement = _services()
    assert branchement is not None
    client = _deux_allocab(
        {
            "acc-barry": {"full_name": "BARRY Boubacar"},
            "acc-autre": {"full_name": "GABI GALESSAN LEVAH"},
        }
    )
    services.fabrique = lambda _b, _g: client
    barry = empreinte(cle_empreintes(), nom_du_profil({"full_name": "BARRY Boubacar"}))
    services.comptes.enregistrer_utilisateur(
        UtilisateurRollee(DOSSIER.id, "927b77da", branchement.id, (barry,)), LE
    )
    comptes = asyncio.run(relire_comptes(services, DOSSIER))
    # AXE-923 : le compte de l'autre chauffeur n'est pas relié du tout, ni
    # enregistré, ni montré, ni cité dans la phrase de synchro.
    assert [(c.account_id, c.retenu) for c in comptes] == [("acc-barry", True)]
    assert services.comptes.comptes(DOSSIER.id) == comptes
    phrase = asyncio.run(synchroniser_dossier(services, DOSSIER))
    assert "autre chauffeur" not in phrase and phrase.count("allocab") == 1
    asyncio.run(_lire(services, DOSSIER, date(2026, 1, 1), date(2026, 11, 14)))
    assert client.lus == ["acc-barry"]


def test_un_compte_d_un_autre_chauffeur_deja_enregistre_disparait_a_la_relecture() -> None:
    """AXE-923 : le compte enregistré avant ce correctif (B'CARS en prod)."""
    services, _, branchement = _services()
    assert branchement is not None
    client = _deux_allocab(
        {
            "acc-barry": {"full_name": "BARRY Boubacar"},
            "acc-autre": {"full_name": "GABI GALESSAN LEVAH"},
        }
    )
    services.fabrique = lambda _b, _g: client
    barry = empreinte(cle_empreintes(), nom_du_profil({"full_name": "BARRY Boubacar"}))
    services.comptes.enregistrer_utilisateur(
        UtilisateurRollee(DOSSIER.id, "927b77da", branchement.id, (barry,)), LE
    )
    ancien = depuis_rollee(
        DOSSIER.id,
        {"id": "acc-autre", "name": "allocab-fleet-rev", "connected": True},
        None,
        LE,
        "927b77da",
        retenu=False,
        titulaire_autre=True,
    )
    services.comptes.remplacer_comptes(DOSSIER.id, [ancien], "927b77da")
    asyncio.run(relire_comptes(services, DOSSIER))
    assert [c.account_id for c in services.comptes.comptes(DOSSIER.id)] == ["acc-barry"]


def test_un_profil_en_500_n_est_pas_retenu() -> None:
    services, _, branchement = _services()
    assert branchement is not None
    services.fabrique = lambda _b, _g: _deux_allocab(None, 500)
    services.comptes.enregistrer_utilisateur(
        UtilisateurRollee(DOSSIER.id, "user-500", branchement.id, ("nom",)), LE
    )
    phrase = asyncio.run(synchroniser_dossier(services, DOSSIER))
    assert "illisible" in phrase
    assert [(c.retenu, c.titulaire_autre) for c in services.comptes.comptes(DOSSIER.id)] == [
        (False, False),
        (False, False),
    ]


def test_synchroniser_sans_user_n_appelle_pas_rollee() -> None:
    services, journal, _ = _services()
    phrase = asyncio.run(synchroniser_dossier(services, DOSSIER))
    assert phrase == "Aucun compte Rollee relié : rien à synchroniser."
    assert journal == []


def test_synchroniser_relit_les_comptes_deja_relies() -> None:
    services, _journal, _ = _services()
    asyncio.run(ouvrir_session(services, DOSSIER))
    phrase = asyncio.run(synchroniser_dossier(services, DOSSIER))
    assert phrase == "Rollee synchronisé : Uber, Bolt. Bolt est à reconnecter."


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


def test_un_webhook_d_un_user_inconnu_lance_son_rapprochement() -> None:
    """AXE-911 : un user Rollee qu'aucun dossier ne connaît est rapproché tout de suite."""
    services, _journal, _ = _services()
    suivi = _suivi(services, [])
    vus: list[tuple[str, dict[str, set[str]]]] = []

    async def rapprocher(tenant_id: TenantId, users: Any) -> str:
        vus.append((tenant_id, {u: set(f) for u, f in users.items()}))
        return "à choisir"

    suivi.rapprocher_inconnus = rapprocher
    suivi.evenements.garder(_evenement({"type": "update_endpoint", "data": {"user_id": "u-x"}}))
    traiter_evenements(suivi, T)
    assert vus == [(T, {"u-x": {"b1"}})]


def test_un_lot_relit_chaque_dossier_une_fois_et_les_inconnus_ensemble() -> None:
    """AXE-966 : Rollee envoie des dizaines de webhooks pour le même user ;
    le dossier n'est relu qu'une fois, et les inconnus en un seul passage."""
    services, _journal, _ = _services()
    asyncio.run(ouvrir_session(services, DOSSIER))
    revenus: list[str] = []
    suivi = _suivi(services, [], revenus)
    appels: list[dict[str, set[str]]] = []

    async def rapprocher(_tenant_id: TenantId, users: Any) -> str:
        appels.append({u: set(f) for u, f in users.items()})
        return "carte mise à jour"

    suivi.rapprocher_inconnus = rapprocher
    for n in range(30):
        suivi.evenements.garder(
            _evenement({"type": "update_endpoint", "data": {"user_id": "user-1"}, "n": n})
        )
    suivi.evenements.garder(_evenement({"action": "update_account", "data": {"user_id": "user-1"}}))
    for n in range(20):
        user = "u-x" if n % 2 else "u-y"
        evenement = EvenementRollee(
            f"inconnu-{n}",
            T,
            "b2" if n == 3 else "b1",
            "update_endpoint",
            {"type": "update_endpoint", "data": {"user_id": user}},
            LE,
        )
        suivi.evenements.garder(evenement)

    resultat = traiter_evenements(suivi, T)

    assert resultat == "51 événements Rollee traités"
    assert revenus == ["DIGI_1"]
    assert appels == [{"u-x": {"b1", "b2"}, "u-y": {"b1"}}]
    assert isinstance(suivi.evenements, EvenementsRolleeMemoire)
    textes = {e.resultat for e in suivi.evenements.evenements.values()}
    assert textes == {"revenus lus", "carte mise à jour"}
    assert suivi.evenements.a_traiter(T, 100) == []


def test_un_dossier_en_erreur_ne_touche_que_ses_evenements() -> None:
    services, _journal, _ = _services()
    asyncio.run(ouvrir_session(services, DOSSIER))
    suivi = _suivi(services, [])

    async def casse(_dossier: Dossier) -> str:
        raise RuntimeError("Rollee indisponible")

    suivi.relever_revenus = casse

    async def rapprocher(_tenant_id: TenantId, _users: Any) -> str:
        return "carte mise à jour"

    suivi.rapprocher_inconnus = rapprocher
    suivi.evenements.garder(_evenement({"type": "update_endpoint", "data": {"user_id": "user-1"}}))
    suivi.evenements.garder(_evenement({"type": "update_endpoint", "data": {"user_id": "u-x"}}))
    traiter_evenements(suivi, T)
    assert isinstance(suivi.evenements, EvenementsRolleeMemoire)
    textes = sorted(e.resultat or "" for e in suivi.evenements.evenements.values())
    assert textes == ["carte mise à jour", "erreur : RuntimeError : Rollee indisponible"]
