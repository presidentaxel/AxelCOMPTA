"""Vérification des jetons Supabase Auth côté chauffeur (doc 17 §9 bloc B,
« reste du bloc B », doc 19 §5.1-2).

Composition root de démo comme `demo_comptes.py`/`demo_api.py` (doc 18) :
intentionnellement **hors** du découpage `axelcompta/*` défini en doc 03
§3, pas une nouvelle brique d'architecture — même raisonnement que
`demo_comptes.py` (implémentation maison prévue en V1, ADR-003).

**Deux liens indépendants sur un même compte (doc 03 §7, 2026-09-21)** :
`dossier_id` (accès indiv) et `tenant_id` (accès gestionnaire), tous deux
lus dans `app_metadata`, jamais `user_metadata`. Avant le 2026-09-21 ce
module n'authentifiait que le chauffeur et le dashboard gestionnaire était
sans login ; ce n'est plus le cas. Ne pas confondre « aucune identité
fournie » (`None`, les routes concernées répondent alors 401) avec
« identité invalide » (401 levée ici, avec le détail).

**Découverte en testant contre le vrai projet Supabase (2026-09-08)** : ce
projet signe ses jetons en ES256 via les « JWT Signing Keys » (clé
asymétrique publiée en JWKS), pas en HS256 avec `SUPABASE_JWT_SECRET`. La
vérification de bloc B du 2026-09-07 (« un jeton signé à la main avec ce
secret est accepté par Supabase ») testait autre chose — que Supabase
accepte ce secret comme preuve d'identité *envers ses propres routes*, pas
que les jetons qu'il *émet* soient signés avec. Les deux sont des
vérifications différentes ; seule celle-ci (2026-09-08, contre un vrai
jeton de connexion) fait foi pour ce module. En clair : `SUPABASE_JWT_SECRET`
n'est plus utilisée par ce module — la vérification se fait contre la clé
publique exposée par Supabase, aucun secret à connaître côté serveur pour
valider un jeton.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Header, HTTPException

from axelcompta.core.ids import DossierId, TenantId, UserId

# ES256 : algorithme par défaut des « JWT Signing Keys » Supabase (constaté
# 2026-09-08). RS256 accepté aussi : configuration possible côté Supabase,
# le JWKS fait foi dans les deux cas — jamais HS256 (secret partagé, plus
# émis par ce projet).
_ALGORITHMES_SUPABASE = ["ES256", "RS256"]
_AUDIENCE_SUPABASE = "authenticated"
_SUFFIXE_JWKS = "/auth/v1/.well-known/jwks.json"
# AXE-822 : compte de test qui lit l'espace chauffeur de n'importe quel
# dossier de son portefeuille, en lecture seule, jusqu'à une date. Exception
# de la période de test (Louis seulement), à retirer avant que les chauffeurs
# se connectent.
ROLE_LECTEUR_TEST = "lecteur_tous_dossiers"


class JetonInvalideError(ValueError):
    """Jeton absent de contenu exploitable — signature/expiration invalide,
    ou compte Supabase valide sans `dossier_id` ni `tenant_id` (ni chauffeur
    ni gestionnaire, doc 03 §7)."""


@dataclass(frozen=True, slots=True)
class IdentiteAuthentifiee:
    """Un compte porte deux liens indépendants (doc 03 §7) : `dossier_id`
    (indiv) et `tenant_id` (gestionnaire), tous deux lus dans
    `app_metadata`. Au moins un des deux est toujours renseigné."""

    user_id: UserId
    email: str
    dossier_id: DossierId | None = None
    tenant_id: TenantId | None = None
    # Niveau d'authentification Supabase (AXE-812) : « aal2 » une fois le
    # code TOTP vérifié dans cette session, « aal1 » avec le mot de passe seul.
    aal: str = "aal1"
    # AXE-822 : portefeuille que le compte de test peut lire, dossier par
    # dossier. Jamais un `tenant_id` : il n'ouvre aucune route gestionnaire.
    # Son `dossier_id` vient de l'en-tête `X-Dossier`, vérifié par l'API.
    lecteur_test_tenant: TenantId | None = None


@lru_cache(maxsize=1)
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    """Un client par URL Supabase, mis en cache — `PyJWKClient` a son
    propre cache interne de clés en plus (le JWKS ne change quasiment
    jamais)."""
    return jwt.PyJWKClient(f"{supabase_url}{_SUFFIXE_JWKS}")


def _url_supabase_depuis_env() -> str:
    """Pas de valeur par défaut silencieuse (doc 08 §2.7) : la variable est
    obligatoire ou on échoue tout de suite."""
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL manquante (voir .env.example)")
    return url


def verifier_jwt(
    jeton: str, cle_verification: Any, aujourd_hui: date | None = None
) -> IdentiteAuthentifiee:
    """Vérifie un jeton d'accès Supabase et en extrait l'identité chauffeur.
    `cle_verification` est la clé publique déjà résolue (production : via
    `_jwks_client`, tests : une clé EC de test) — séparé de la résolution
    réseau pour rester testable sans HTTP. Lève `JetonInvalideError` sur
    toute anomalie."""
    try:
        charge_utile: dict[str, Any] = jwt.decode(
            jeton,
            cle_verification,
            algorithms=_ALGORITHMES_SUPABASE,
            audience=_AUDIENCE_SUPABASE,
        )
    except jwt.PyJWTError as exc:
        raise JetonInvalideError(f"jeton invalide : {exc}") from exc

    # `app_metadata` et jamais `user_metadata` : ce dernier est modifiable par
    # l'utilisateur lui-même (API Auth Supabase), donc inutilisable pour un
    # droit d'accès. Avant le 2026-09-21, `dossier_id` était lu dans
    # `user_metadata` : un chauffeur invité pouvait s'attribuer le dossier
    # d'un autre. Pas de repli sur l'ancien emplacement, qui rouvrirait la
    # faille (voir scripts/migrer_liens_vers_app_metadata.py pour les
    # comptes existants).
    app_metadata = charge_utile.get("app_metadata", {})
    if "role_test" in app_metadata:
        return _lecteur_test(charge_utile, app_metadata, aujourd_hui)
    dossier_id = app_metadata.get("dossier_id")
    tenant_id = app_metadata.get("tenant_id")
    if not dossier_id and not tenant_id:
        raise JetonInvalideError(
            "compte sans dossier_id ni tenant_id — ni chauffeur ni gestionnaire"
        )

    return IdentiteAuthentifiee(
        user_id=UserId(charge_utile["sub"]),
        email=charge_utile.get("email", ""),
        dossier_id=DossierId(dossier_id) if dossier_id else None,
        tenant_id=TenantId(tenant_id) if tenant_id else None,
        aal=str(charge_utile.get("aal", "aal1")),
    )


def _lecteur_test(
    charge_utile: dict[str, Any], app_metadata: dict[str, Any], aujourd_hui: date | None
) -> IdentiteAuthentifiee:
    """AXE-822. Rôle, portefeuille et date de fin obligatoires ; passé la
    date, le compte ne voit plus rien. Aucun lien `dossier_id` ni `tenant_id`
    n'est repris du jeton : le compte n'est ni chauffeur ni gestionnaire."""
    if app_metadata.get("role_test") != ROLE_LECTEUR_TEST:
        raise JetonInvalideError("rôle de test inconnu")
    tenant_id = app_metadata.get("tenant_id")
    if not tenant_id:
        raise JetonInvalideError("compte de test sans portefeuille")
    try:
        expire_le = date.fromisoformat(str(app_metadata.get("expire_le")))
    except ValueError as exc:
        raise JetonInvalideError("compte de test sans date de fin lisible") from exc
    if expire_le < (aujourd_hui or datetime.now(UTC).date()):
        raise JetonInvalideError("compte de test expiré")
    return IdentiteAuthentifiee(
        user_id=UserId(charge_utile["sub"]),
        email=charge_utile.get("email", ""),
        lecteur_test_tenant=TenantId(tenant_id),
    )


def _identite_depuis_en_tete(authorization: str | None) -> IdentiteAuthentifiee | None:
    """`None` si aucun en-tête (cas gestionnaire actuel, doc ci-dessus) —
    401 explicite si l'en-tête est présent mais inexploitable, jamais une
    401 silencieuse confondue avec une absence d'authentification."""
    if authorization is None:
        return None
    prefixe = "Bearer "
    if not authorization.startswith(prefixe):
        raise HTTPException(status_code=401, detail="En-tête Authorization mal formé.")
    jeton = authorization.removeprefix(prefixe)
    try:
        client = _jwks_client(_url_supabase_depuis_env())
        cle = client.get_signing_key_from_jwt(jeton).key
        return verifier_jwt(jeton, cle)
    except (JetonInvalideError, jwt.PyJWTError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def identite_chauffeur_optionnelle(
    authorization: Annotated[str | None, Header()] = None,
) -> IdentiteAuthentifiee | None:
    """Dépendance FastAPI — voir `_identite_depuis_en_tete`."""
    return _identite_depuis_en_tete(authorization)


def identite_tolerante(authorization: str | None) -> IdentiteAuthentifiee | None:
    """Comme `_identite_depuis_en_tete`, mais ne lève jamais — `None` sur un
    jeton absent ou invalide. Réservé au middleware RLS de `demo_api.py`
    (`core/rls.py`) : lui seul pose le contexte, la décision d'autoriser
    ou non reste entièrement dans `_verifier_acces_dossier` et les
    dépendances existantes, jamais ici."""
    try:
        return _identite_depuis_en_tete(authorization)
    except HTTPException:
        return None
