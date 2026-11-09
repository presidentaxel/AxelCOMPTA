"""Crée ou supprime le compte de test qui lit l'espace chauffeur de tout un
portefeuille (AXE-822).

Exception de la période de test, pour Louis seulement : le compte lit, en
lecture seule, l'espace chauffeur de n'importe quel dossier du portefeuille,
jusqu'à sa date de fin. Il n'est ni chauffeur ni gestionnaire. Son
`app_metadata` ne s'écrit qu'avec la clé service role, d'où ce script.

Usage, depuis backend/ (SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans
l'environnement, voir .env.example) :

    python scripts/compte_de_test.py creer test@exemple.fr --jusqu-au 2026-12-31
    python scripts/compte_de_test.py supprimer test@exemple.fr

Le mot de passe est demandé au clavier, jamais passé en argument. La date de
fin est obligatoire et ne dépasse pas 90 jours : passé cette date, l'API
refuse le compte (`demo_auth._lecteur_test`) ; le supprimer reste à faire.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import UTC, date, datetime, timedelta

import httpx

from axelcompta.demo_auth import ROLE_LECTEUR_TEST
from axelcompta.demo_comptes import SupabaseConfig
from axelcompta.demo_seed import TENANT_DEMO

DUREE_MAX = timedelta(days=90)


def _en_tetes(config: SupabaseConfig) -> dict[str, str]:
    return {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
    }


def _date_de_fin(texte: str) -> date:
    fin = date.fromisoformat(texte)
    aujourd_hui = datetime.now(UTC).date()
    if not aujourd_hui <= fin <= aujourd_hui + DUREE_MAX:
        raise ValueError(f"date de fin entre aujourd'hui et {aujourd_hui + DUREE_MAX}")
    return fin


def creer(config: SupabaseConfig, email: str, tenant_id: str, fin: date) -> int:
    mot_de_passe = getpass.getpass("Mot de passe du compte de test : ")
    if len(mot_de_passe) < 12:
        print("Mot de passe trop court (12 caractères minimum).", file=sys.stderr)
        return 1
    reponse = httpx.post(
        f"{config.url}/auth/v1/admin/users",
        headers=_en_tetes(config),
        json={
            "email": email,
            "password": mot_de_passe,
            "email_confirm": True,
            "app_metadata": {
                "role_test": ROLE_LECTEUR_TEST,
                "tenant_id": tenant_id,
                "expire_le": fin.isoformat(),
            },
        },
        timeout=10.0,
    )
    if reponse.status_code >= 400:
        print(f"Échec ({reponse.status_code}) : {reponse.text}", file=sys.stderr)
        return 1
    print(f"Compte de test créé : {email} (portefeuille {tenant_id}, jusqu'au {fin})")
    return 0


def _identifiant(config: SupabaseConfig, email: str) -> str | None:
    """Parcourt les comptes page par page (borné) pour trouver cet e-mail."""
    for page in range(1, 51):
        reponse = httpx.get(
            f"{config.url}/auth/v1/admin/users",
            headers=_en_tetes(config),
            params={"page": page, "per_page": 100},
            timeout=10.0,
        )
        reponse.raise_for_status()
        comptes = reponse.json().get("users", [])
        for compte in comptes:
            if str(compte.get("email", "")).lower() == email.lower():
                return str(compte["id"])
        if len(comptes) < 100:
            return None
    return None


def supprimer(config: SupabaseConfig, email: str) -> int:
    identifiant = _identifiant(config, email)
    if identifiant is None:
        print(f"Aucun compte {email}.", file=sys.stderr)
        return 1
    reponse = httpx.delete(
        f"{config.url}/auth/v1/admin/users/{identifiant}", headers=_en_tetes(config), timeout=10.0
    )
    if reponse.status_code >= 400:
        print(f"Échec ({reponse.status_code}) : {reponse.text}", file=sys.stderr)
        return 1
    print(f"Compte de test supprimé : {email}")
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    action = parseur.add_subparsers(dest="action", required=True)
    creation = action.add_parser("creer")
    creation.add_argument("email")
    creation.add_argument("--jusqu-au", required=True, help="AAAA-MM-JJ, 90 jours au plus")
    creation.add_argument("--tenant-id", default=TENANT_DEMO)
    suppression = action.add_parser("supprimer")
    suppression.add_argument("email")
    args = parseur.parse_args()

    config = SupabaseConfig.depuis_env()
    if args.action == "supprimer":
        return supprimer(config, args.email)
    try:
        fin = _date_de_fin(args.jusqu_au)
    except ValueError as exc:
        print(f"Date de fin refusée : {exc}", file=sys.stderr)
        return 1
    return creer(config, args.email, args.tenant_id, fin)


if __name__ == "__main__":
    raise SystemExit(main())
