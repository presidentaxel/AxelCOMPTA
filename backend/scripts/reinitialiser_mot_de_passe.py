"""Pose un nouveau mot de passe sur un compte Supabase déjà créé.

Le tableau Supabase ne laisse pas saisir un mot de passe à la main : il
n'envoie qu'un e-mail de récupération. Ce courrier part par l'envoi
intégré du projet, au quota très bas, et n'arrive souvent pas. La clé
service role, déjà utilisée pour créer les comptes, écrit le mot de passe
directement.

Usage, depuis backend/ (SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans
l'environnement) :

    python scripts/reinitialiser_mot_de_passe.py demo-karim@axelcompta.fr

Le mot de passe est demandé au clavier, jamais passé en argument.
"""

from __future__ import annotations

import getpass
import sys

import httpx

from axelcompta.comptes import SupabaseConfig


def _trouver_id(client: httpx.Client, email: str) -> str | None:
    for page in range(1, 51):
        reponse = client.get("/admin/users", params={"page": page, "per_page": 200})
        reponse.raise_for_status()
        lot = reponse.json().get("users", [])
        for utilisateur in lot:
            if (utilisateur.get("email") or "").lower() == email.lower():
                return str(utilisateur["id"])
        if len(lot) < 200:
            return None
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage : python scripts/reinitialiser_mot_de_passe.py <email>", file=sys.stderr)
        return 1
    email = sys.argv[1].strip()
    mot_de_passe = getpass.getpass("Nouveau mot de passe : ")
    if len(mot_de_passe) < 12:
        print("Mot de passe trop court (12 caractères minimum).", file=sys.stderr)
        return 1

    config = SupabaseConfig.depuis_env()
    client = httpx.Client(
        base_url=f"{config.url}/auth/v1",
        headers={
            "apikey": config.service_role_key,
            "Authorization": f"Bearer {config.service_role_key}",
        },
        timeout=15.0,
    )
    utilisateur_id = _trouver_id(client, email)
    if utilisateur_id is None:
        print(f"Aucun compte pour {email}.", file=sys.stderr)
        return 1
    reponse = client.put(f"/admin/users/{utilisateur_id}", json={"password": mot_de_passe})
    if reponse.status_code >= 400:
        print(f"Échec ({reponse.status_code}) : {reponse.text}", file=sys.stderr)
        return 1
    print(f"Mot de passe mis à jour : {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
