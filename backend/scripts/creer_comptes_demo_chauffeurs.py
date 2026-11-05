"""Crée le compte chauffeur du dossier de review UX (Sophie) dans Supabase Auth.

Ces comptes ne portent que `app_metadata.dossier_id` (accès indiv), jamais
`tenant_id` : contrairement à `creer_compte_gestionnaire.py`, ce ne sont pas
des comptes gestionnaire, donc pas d'accès portefeuille. Un `env: "demo"`
est aussi posé dans `app_metadata`, purement indicatif (démo_auth.py ne lit
que `dossier_id`/`tenant_id`) — sert à repérer ces comptes dans le dashboard
Supabase et à ne pas les confondre avec de vrais comptes chauffeur pilote
plus tard.

Usage, depuis backend/ (SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans
l'environnement, voir .env.example) :

    python scripts/creer_comptes_demo_chauffeurs.py

Le mot de passe de chaque compte est demandé au clavier, jamais en argument.
Un compte déjà existant (même e-mail) fait échouer sa création (409) sans
bloquer les suivants — le script continue et rapporte à la fin.
"""

from __future__ import annotations

import getpass

import httpx

from axelcompta.demo_comptes import SupabaseConfig

# Depuis le 2026-11-05, seul le dossier de review UX (Sophie) reste en base :
# Karim et Yanis ont été supprimés, la base est celle du portefeuille réel.
COMPTES_DEMO = (
    ("demo-sophie@axelcompta.fr", "DEMO_sophie"),
)


def main() -> int:
    config = SupabaseConfig.depuis_env()
    echecs = 0
    for email, dossier_id in COMPTES_DEMO:
        mot_de_passe = getpass.getpass(f"Mot de passe pour {email} : ")
        if len(mot_de_passe) < 12:
            print(f"  Ignoré, mot de passe trop court (12 caractères minimum) : {email}")
            echecs += 1
            continue
        corps: dict[str, object] = {
            "email": email,
            "password": mot_de_passe,
            "email_confirm": True,
            "app_metadata": {"dossier_id": dossier_id, "env": "demo"},
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
            print(f"  Échec ({reponse.status_code}) pour {email} : {reponse.text}")
            echecs += 1
            continue
        print(f"  Compte créé : {email} (dossier {dossier_id})")

    if echecs:
        print(f"{echecs} compte(s) en échec, voir ci-dessus.")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
