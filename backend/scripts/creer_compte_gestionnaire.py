"""Crée (ou promeut) un compte gestionnaire dans Supabase Auth.

Le lien gestionnaire est `app_metadata.tenant_id` (doc 03 §7) : seule la
clé service role peut l'écrire, contrairement à `user_metadata`, que
l'utilisateur peut modifier lui-même (idem pour `dossier_id`). D'où ce script plutôt qu'un
formulaire d'inscription.

Usage, depuis backend/ (SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans
l'environnement, voir .env.example) :

    python scripts/creer_compte_gestionnaire.py gestionnaire@exemple.fr

Le mot de passe est demandé au clavier, jamais passé en argument.
Mode mono (doc 03 §1) : ajouter `--dossier-id DEMO_karim` pour que le même
compte porte aussi le lien indiv.
"""

from __future__ import annotations

import argparse
import getpass
import sys

import httpx

from axelcompta.comptes import SupabaseConfig
from axelcompta.demo_seed import TENANT_DEMO


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("email")
    parseur.add_argument("--tenant-id", default=TENANT_DEMO)
    parseur.add_argument("--dossier-id", default=None)
    args = parseur.parse_args()

    mot_de_passe = getpass.getpass("Mot de passe du compte : ")
    if len(mot_de_passe) < 12:
        print("Mot de passe trop court (12 caractères minimum).", file=sys.stderr)
        return 1

    config = SupabaseConfig.depuis_env()
    liens = {"tenant_id": args.tenant_id}
    if args.dossier_id:
        liens["dossier_id"] = args.dossier_id
    corps: dict[str, object] = {
        "email": args.email,
        "password": mot_de_passe,
        "email_confirm": True,
        "app_metadata": liens,
    }

    reponse = httpx.post(
        f"{config.url}/auth/v1/admin/users",
        headers={
            "apikey": config.service_role_key,
            "Authorization": f"Bearer {config.service_role_key}",
        },
        json=corps,
        timeout=10.0,
    )
    if reponse.status_code >= 400:
        print(f"Échec ({reponse.status_code}) : {reponse.text}", file=sys.stderr)
        return 1
    print(f"Compte créé : {args.email} (tenant {args.tenant_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
