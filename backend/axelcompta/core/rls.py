"""Contexte RLS (Row-Level Security) Postgres — doc 12 §1.1.

Isolation multi-tenant en profondeur : avant ce module, seule
`api/routes.py` (`_verifier_acces_dossier`) empêchait un dossier d'en lire
un autre — une couche applicative, jamais vérifiée si un bug de requête
oublie le filtre `WHERE dossier_id = ...` (doc 19 §8bis l'avait déjà
signalé comme un vrai gap connu, pas hypothétique). Ce module ajoute une
seconde barrière, au niveau base : les policies RLS (migration
`ROLE_WEB_ET_POLICIES`) filtrent chaque ligne côté Postgres, pour le rôle
`axelcompta_web` uniquement — `user` (les scripts d'administration :
migrations, l'amorçage des jeux de test, `synchro_digifactory`, `notifier`) reste
propriétaire des tables et n'est jamais concerné.

Le contexte est posé une fois par requête HTTP (middleware de `api/routes.py`),
lu ici via un `ContextVar` (pas un argument à faire passer dans chaque
repository), et appliqué à chaque transaction Postgres via `set_config(...,
true)` — l'équivalent de `SET LOCAL`, jamais `SET` : la portée doit rester
la transaction en cours, jamais la connexion. Le pool SQLAlchemy réutilise
les connexions entre deux requêtes différentes ; une variable de session
posée avec `SET` (portée connexion) fuiterait le contexte RLS d'une
requête vers la suivante servie par la même connexion recyclée. `SET
LOCAL`/`set_config(..., true)` est effacé à la fin de la transaction,
qu'elle commit ou rollback — jamais de fuite possible entre deux requêtes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.engine import Connection

_dossier_id: ContextVar[str | None] = ContextVar("_rls_dossier_id", default=None)
_tenant_id: ContextVar[str | None] = ContextVar("_rls_tenant_id", default=None)


@contextmanager
def contexte_identite(dossier_id: str | None, tenant_id: str | None) -> Iterator[None]:
    """Pose le contexte RLS pour la durée du bloc (une requête HTTP
    entière, middleware de `api/routes.py`). Réentrant : un contexte imbriqué
    (tests) restaure l'ancien en sortant, pas `None`."""
    jeton_dossier = _dossier_id.set(dossier_id)
    jeton_tenant = _tenant_id.set(tenant_id)
    try:
        yield
    finally:
        _dossier_id.reset(jeton_dossier)
        _tenant_id.reset(jeton_tenant)


def appliquer_rls(connexion: Connection) -> None:
    """À appeler en tout premier, juste après l'ouverture d'une transaction
    (`engine.begin()`/`engine.connect()`), avant toute requête réelle sur
    une connexion qui utilise le rôle `axelcompta_web`. Sans effet (mais
    sans erreur) hors contexte — utile pour les repositories partagés entre
    requêtes HTTP (rôle web, contexte posé) et scripts d'administration
    (rôle `user`, policies non appliquées, `set_config` est un no-op côté
    lecture des policies puisqu'elles ne s'appliquent pas à ce rôle).

    `set_config` plutôt qu'un `SET LOCAL app.x = '...'` construit par
    concaténation : paramétrable comme n'importe quelle requête, aucune
    injection possible même si `dossier_id`/`tenant_id` contenaient un
    caractère spécial."""
    connexion.execute(
        text(
            "SELECT set_config('app.dossier_id', :dossier_id, true), "
            "set_config('app.tenant_id', :tenant_id, true)"
        ),
        {"dossier_id": _dossier_id.get() or "", "tenant_id": _tenant_id.get() or ""},
    )
