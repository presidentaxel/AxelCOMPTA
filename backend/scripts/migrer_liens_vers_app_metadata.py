"""Migre les comptes existants : `user_metadata.dossier_id` -> `app_metadata`.

Avant le 2026-09-21, le lien chauffeur -> dossier était posé dans
`user_metadata`, que l'utilisateur peut modifier lui-même (API Auth
Supabase). `api/auth.py` lit désormais `app_metadata` uniquement : sans
cette migration, les comptes chauffeur déjà invités n'ont plus accès à leur
dossier.

Par défaut, simple simulation (liste ce qui serait changé). `--appliquer`
écrit pour de bon. Clé service role requise (SUPABASE_URL,
SUPABASE_SERVICE_ROLE_KEY), donc à lancer depuis un poste de confiance.

    python scripts/migrer_liens_vers_app_metadata.py            # simulation
    python scripts/migrer_liens_vers_app_metadata.py --appliquer
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx

from axelcompta.comptes import SupabaseConfig


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--appliquer", action="store_true")
    args = parseur.parse_args()

    config = SupabaseConfig.depuis_env()
    client = httpx.Client(
        base_url=f"{config.url}/auth/v1",
        headers={
            "apikey": config.service_role_key,
            "Authorization": f"Bearer {config.service_role_key}",
        },
        timeout=10.0,
    )
    reponse = client.get("/admin/users")
    reponse.raise_for_status()
    utilisateurs: list[dict[str, Any]] = reponse.json().get("users", [])

    a_migrer = [
        u
        for u in utilisateurs
        if u.get("user_metadata", {}).get("dossier_id")
        and not u.get("app_metadata", {}).get("dossier_id")
    ]
    for utilisateur in a_migrer:
        dossier_id = utilisateur["user_metadata"]["dossier_id"]
        print(f"{utilisateur.get('email')} : dossier {dossier_id}")
        if not args.appliquer:
            continue
        # `null` retire la clé de `user_metadata` : elle ne doit plus servir
        # de source de vérité, même par inadvertance.
        ecriture = client.put(
            f"/admin/users/{utilisateur['id']}",
            json={
                "app_metadata": {"dossier_id": dossier_id},
                "user_metadata": {"dossier_id": None},
            },
        )
        ecriture.raise_for_status()

    verbe = "migrés" if args.appliquer else "à migrer (simulation, ajouter --appliquer)"
    print(f"{len(a_migrer)} compte(s) {verbe}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
