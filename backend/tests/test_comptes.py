from __future__ import annotations

import json

import httpx
import pytest

from axelcompta.comptes import (
    StatutInvitation,
    SupabaseCompteRepository,
    SupabaseConfig,
)
from axelcompta.core.ids import DossierId


def test_depuis_env_leve_si_url_manquante(monkeypatch: pytest.MonkeyPatch) -> None:
    """doc 08 §2.7 : pas de valeur par défaut silencieuse."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "peu-importe")
    with pytest.raises(RuntimeError):
        SupabaseConfig.depuis_env()


def test_depuis_env_leve_si_service_role_key_manquante(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://exemple.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(RuntimeError):
        SupabaseConfig.depuis_env()


def test_depuis_env_construit_la_config_si_tout_est_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://exemple.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "une-cle")
    config = SupabaseConfig.depuis_env()
    assert config.url == "https://exemple.supabase.co"
    assert config.service_role_key == "une-cle"


def _depot_supabase(utilisateurs: list[dict[str, object]], appels: list[httpx.Request]):  # type: ignore[no-untyped-def]
    def repondre(requete: httpx.Request) -> httpx.Response:
        appels.append(requete)
        if requete.method == "GET":
            page = int(requete.url.params.get("page", "1"))
            par_page = int(requete.url.params.get("per_page", "50"))
            debut = (page - 1) * par_page
            return httpx.Response(200, json={"users": utilisateurs[debut : debut + par_page]})
        if requete.method == "POST":
            return httpx.Response(200, json={"id": "nouvel-utilisateur"})
        return httpx.Response(200, json={})

    client = httpx.Client(
        base_url="https://exemple.supabase.co/auth/v1", transport=httpx.MockTransport(repondre)
    )
    return SupabaseCompteRepository(SupabaseConfig("https://exemple.supabase.co", "cle"), client)


def _utilisateur(dossier_id: str, confirme: bool = False) -> dict[str, object]:
    return {
        "id": f"u-{dossier_id}",
        "email": f"{dossier_id}@exemple.fr",
        "app_metadata": {"dossier_id": dossier_id},
        "email_confirmed_at": "2026-09-01T00:00:00Z" if confirme else None,
    }


def test_un_dossier_au_dela_de_la_premiere_page_est_bien_trouve() -> None:
    """Régression : sans pagination, on ne lisait que les 50 premiers comptes,
    un dossier déjà invité passait pour non invité."""
    utilisateurs = [_utilisateur(f"d{i}") for i in range(450)]
    depot = _depot_supabase(utilisateurs, [])

    invitation = depot.statut(DossierId("d449"))

    assert invitation is not None and invitation.email == "d449@exemple.fr"


def test_statuts_en_masse_ne_lit_les_comptes_qu_une_fois() -> None:
    utilisateurs = [_utilisateur("d1", confirme=True), _utilisateur("d2")]
    appels: list[httpx.Request] = []
    depot = _depot_supabase(utilisateurs, appels)

    resultat = depot.statuts([DossierId("d1"), DossierId("d2"), DossierId("d3")])

    assert resultat[DossierId("d1")].statut is StatutInvitation.ACTIF
    assert resultat[DossierId("d2")].statut is StatutInvitation.INVITE
    assert DossierId("d3") not in resultat
    assert len([a for a in appels if a.method == "GET"]) == 1


def test_membres_distingue_invitation_envoyee_et_acceptee() -> None:
    utilisateurs: list[dict[str, object]] = [
        {
            "email": "marie@exemple.fr",
            "app_metadata": {"tenant_id": "T1"},
            "email_confirmed_at": None,
        },
        {
            "email": "paul@exemple.fr",
            "app_metadata": {"tenant_id": "T1"},
            "email_confirmed_at": "2026-09-01T00:00:00Z",
        },
        {
            "email": "autre@exemple.fr",
            "app_metadata": {"tenant_id": "T2"},
            "email_confirmed_at": "2026-09-01T00:00:00Z",
        },
    ]
    depot = _depot_supabase(utilisateurs, [])

    membres = depot.membres("T1")

    assert [(membre.email, membre.accepte) for membre in membres] == [
        ("marie@exemple.fr", False),
        ("paul@exemple.fr", True),
    ]


def test_invitation_renvoie_vers_la_page_du_mot_de_passe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le lien dépose la personne sur la page qui lui fait choisir un mot
    de passe, pas sur l'accueil de l'application."""
    monkeypatch.setenv("AXELCOMPTA_URL_APP", "https://compta.axelproject.fr/")
    appels: list[httpx.Request] = []
    depot = _depot_supabase([], appels)

    depot.inviter_membre("T1", "marie@exemple.fr")
    depot.inviter(DossierId("d1"), "sophie@exemple.fr", verifier_existant=False)

    invitations = [a for a in appels if a.method == "POST" and a.url.path.endswith("/invite")]
    assert [json.loads(a.content) for a in invitations] == [
        {
            "email": "marie@exemple.fr",
            "redirect_to": "https://compta.axelproject.fr/auth/lien",
        },
        {
            "email": "sophie@exemple.fr",
            "redirect_to": "https://compta.axelproject.fr/chauffeur/accepter-invitation",
        },
    ]


def test_renvoyer_pointe_vers_la_page_du_mot_de_passe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXELCOMPTA_URL_APP", "https://compta.axelproject.fr")
    appels: list[httpx.Request] = []
    depot = _depot_supabase([_utilisateur("d1")], appels)

    depot.renvoyer(DossierId("d1"))

    renvois = [a for a in appels if a.method == "POST" and a.url.path.endswith("/resend")]
    assert len(renvois) == 1
    assert renvois[0].url.params["redirect_to"] == (
        "https://compta.axelproject.fr/chauffeur/accepter-invitation"
    )
    assert json.loads(renvois[0].content) == {"type": "signup", "email": "d1@exemple.fr"}


def test_retirer_un_membre_supprime_son_compte_auth_pas_un_chauffeur() -> None:
    utilisateurs: list[dict[str, object]] = [
        {"id": "gest", "email": "marie@exemple.fr", "app_metadata": {"tenant_id": "T1"}},
        {"id": "chauffeur", "email": "sophie@exemple.fr", "app_metadata": {"dossier_id": "d1"}},
    ]
    appels: list[httpx.Request] = []
    depot = _depot_supabase(utilisateurs, appels)

    depot.retirer_membre("T1", "Marie@exemple.fr")
    depot.retirer_membre("T1", "sophie@exemple.fr")
    depot.retirer_membre("T1", "inconnu@exemple.fr")

    suppressions = [appel for appel in appels if appel.method == "DELETE"]
    assert [appel.url.path for appel in suppressions] == ["/auth/v1/admin/users/gest"]


def test_inviter_sans_reverifier_ne_relit_pas_les_comptes() -> None:
    appels: list[httpx.Request] = []
    depot = _depot_supabase([], appels)

    depot.inviter(DossierId("d1"), "x@exemple.fr", verifier_existant=False)

    assert [a.method for a in appels] == ["POST", "PUT"]
    assert appels[1].url.path.endswith("/admin/users/nouvel-utilisateur")
