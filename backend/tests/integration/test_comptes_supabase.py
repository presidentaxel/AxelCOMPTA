"""SupabaseCompteRepository contre un vrai projet Supabase (doc 17 §9 bloc
B). Utilisateurs de test toujours supprimés après (fixtures) — ne doit
rien laisser dans le projet réel.

**Attention** : `test_inviter_envoie_une_vraie_invitation` appelle
réellement `/invite` et envoie un vrai e-mail (quota très limité côté
Supabase sur le tier gratuit, doc 17 §9 bloc B) — ne pas lancer à la
légère ni en boucle/CI. Tous les autres tests créent l'utilisateur
directement via `/admin/users` (n'envoie jamais d'e-mail, contrairement à
`/invite`) pour vérifier `statut()` sans ce coût.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from axelcompta.comptes import (
    CompteDejaInviteError,
    StatutInvitation,
    SupabaseCompteRepository,
    SupabaseConfig,
)
from axelcompta.core.ids import DossierId

pytestmark = pytest.mark.supabase


@pytest.fixture
def config() -> SupabaseConfig:
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        pytest.skip("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY non définies — voir .env.example")
    return SupabaseConfig.depuis_env()


@pytest.fixture
def client_admin(config: SupabaseConfig) -> Iterator[httpx.Client]:
    with httpx.Client(
        base_url=f"{config.url}/auth/v1",
        headers={
            "apikey": config.service_role_key,
            "Authorization": f"Bearer {config.service_role_key}",
        },
        timeout=10.0,
    ) as client:
        yield client


@pytest.fixture
def dossier_test() -> DossierId:
    return DossierId(f"test-{uuid.uuid4().hex[:12]}")


@pytest.fixture
def repo(
    config: SupabaseConfig, client_admin: httpx.Client, dossier_test: DossierId
) -> Iterator[SupabaseCompteRepository]:
    repository = SupabaseCompteRepository(config, client=client_admin)
    yield repository
    _supprimer_si_existe(client_admin, dossier_test)


def _supprimer_si_existe(client_admin: httpx.Client, dossier_id: DossierId) -> None:
    utilisateurs: list[dict[str, Any]] = client_admin.get("/admin/users").json().get("users", [])
    for utilisateur in utilisateurs:
        if utilisateur.get("app_metadata", {}).get("dossier_id") == dossier_id:
            client_admin.delete(f"/admin/users/{utilisateur['id']}")


def _creer_sans_email(
    client_admin: httpx.Client, dossier_id: DossierId, email: str, confirme: bool
) -> None:
    """`/admin/users` (contrairement à `/invite`) n'envoie jamais d'e-mail —
    seed sûr et répétable pour tester `statut()`."""
    reponse = client_admin.post(
        "/admin/users",
        json={
            "email": email,
            "password": f"Test!{uuid.uuid4().hex[:16]}",
            "email_confirm": confirme,
            "app_metadata": {"dossier_id": dossier_id},
        },
    )
    reponse.raise_for_status()


def test_statut_est_none_avant_toute_invitation(
    repo: SupabaseCompteRepository, dossier_test: DossierId
) -> None:
    assert repo.statut(dossier_test) is None


def test_statut_actif_pour_un_compte_confirme(
    repo: SupabaseCompteRepository, client_admin: httpx.Client, dossier_test: DossierId
) -> None:
    email = f"{dossier_test}@axelproject.fr"
    _creer_sans_email(client_admin, dossier_test, email, confirme=True)

    invitation = repo.statut(dossier_test)

    assert invitation is not None
    assert invitation.statut is StatutInvitation.ACTIF
    assert invitation.email == email


def test_statut_invite_pour_un_compte_non_confirme(
    repo: SupabaseCompteRepository, client_admin: httpx.Client, dossier_test: DossierId
) -> None:
    email = f"{dossier_test}@axelproject.fr"
    _creer_sans_email(client_admin, dossier_test, email, confirme=False)

    invitation = repo.statut(dossier_test)

    assert invitation is not None
    assert invitation.statut is StatutInvitation.INVITE


def test_inviter_deux_fois_leve_sans_rappeler_supabase(
    repo: SupabaseCompteRepository, client_admin: httpx.Client, dossier_test: DossierId
) -> None:
    """doc 08 §2.7 : le garde-fou se déclenche avant tout appel réseau à
    `/invite` — pas de deuxième e-mail envoyé par erreur."""
    email = f"{dossier_test}@axelproject.fr"
    _creer_sans_email(client_admin, dossier_test, email, confirme=True)

    with pytest.raises(CompteDejaInviteError):
        repo.inviter(dossier_test, f"autre-{dossier_test}@axelproject.fr")


@pytest.mark.skip(
    reason="Envoie un vrai e-mail via /invite (quota Supabase limité) — "
    "à lancer manuellement (retirer ce skip) une fois d'accord avec Louis."
)
def test_inviter_envoie_une_vraie_invitation(
    repo: SupabaseCompteRepository, dossier_test: DossierId
) -> None:
    email = f"{dossier_test}@axelproject.fr"

    invitation = repo.inviter(dossier_test, email)

    assert invitation.statut is StatutInvitation.INVITE
    assert repo.statut(dossier_test) == invitation
