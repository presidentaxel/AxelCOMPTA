"""Crée un dossier par contact Digifactory du portefeuille, puis synchronise.

**Aucun compte n'est créé** (depuis le 2026-11-05, AXE-726) : le dirigeant
de chaque société est invité par le gestionnaire avec sa vraie adresse
(écran Invitations), et confirme sa configuration à la première connexion
(AXE-730). La forme, le premier exercice et l'activité viennent de Sirene
(AXE-834) ; une société cessée est ignorée, une activité qui n'est pas du
VTC est signalée.

Le compte Digifactory de Serenity contient aussi des contacts qui ne sont
pas des chauffeurs (ses propres sociétés, des plateformes) : on ne crée de
dossier **que pour les contacts listés** (AXE-726). Un contact hors liste
est signalé, jamais enregistré. `--lister` affiche les contacts sans rien
écrire, pour choisir.

Usage, depuis backend/ :

    python scripts/ajouter_chauffeurs_digifactory.py --lister
    python scripts/ajouter_chauffeurs_digifactory.py --contacts 7416,8780 --sans-synchro
    python scripts/ajouter_chauffeurs_digifactory.py --contacts 7416,8780
    python scripts/ajouter_chauffeurs_digifactory.py --sirene   # réaligne les dossiers existants

Idempotent : un contact déjà mappé est laissé tel quel. La synchro rejoue
sans doublon (curseur).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv

from axelcompta.core.db import engine_depuis_env
from axelcompta.demo_digifactory import (
    TENANT_DEMO,
    dossier_depuis_contact,
    nom_affiche,
    numero_contact,
    preparer_dossier,
    siren_contact,
)
from axelcompta.ingestion.providers.digifactory import DigifactoryHttpClient
from axelcompta.synchro_digifactory import synchroniser_portefeuille
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.sirene import FicheSirene, configurer_depuis_sirene, fiche_depuis_reponse


async def _contacts_bruts() -> dict[str, dict[str, object]]:
    client = DigifactoryHttpClient.depuis_env()
    try:
        brut = await client.contacts()
    finally:
        await client.aclose()
    return {str(nr): contact for nr, contact in brut.items() if isinstance(contact, dict)}


def _fiche_sirene(siren: str | None) -> FicheSirene | None:
    """Recherche d'entreprises (data.gouv, sans clé)."""
    if siren is None:
        return None
    reponse = httpx.get(
        "https://recherche-entreprises.api.gouv.fr/search",
        params={"q": siren, "per_page": 1},
        headers={"accept": "application/json"},
        timeout=15.0,
    )
    reponse.raise_for_status()
    corps = reponse.json()
    return fiche_depuis_reponse(corps, siren) if isinstance(corps, dict) else None


def _aligner_sirene(depot: PostgresDossierRepository) -> None:
    """Dossiers déjà en base : forme, premier exercice, activité et éléments à
    confirmer repris de Sirene. Un exercice déjà juste ne bouge pas."""
    for contact in asyncio.run(_contacts_bruts()).values():
        dossier = depot.par_contact_nr(numero_contact(contact))
        if dossier is None:
            continue
        fiche = _fiche_sirene(siren_contact(contact))
        if fiche is None:
            print(f"{dossier.id} : pas de fiche Sirene, laissé tel quel", flush=True)
            continue
        nouveau = configurer_depuis_sirene(dossier, fiche, date.today())
        if nouveau != dossier:
            depot.reconfigurer_depuis_sirene(nouveau)
        print(
            f"{dossier.id} : {nouveau.forme_juridique}, exercice du {nouveau.exercice_debut}, "
            f"NAF {nouveau.code_naf}, à confirmer {list(nouveau.a_confirmer)}",
            flush=True,
        )


def _arguments() -> argparse.Namespace:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parseur.add_mutually_exclusive_group(required=True)
    action.add_argument("--lister", action="store_true", help="affiche les contacts, n'écrit rien")
    action.add_argument(
        "--contacts", help="numéros de contact à importer, séparés par des virgules"
    )
    action.add_argument(
        "--sirene", "--formes", action="store_true", help="réaligne les dossiers sur Sirene"
    )
    parseur.add_argument("--sans-synchro", action="store_true", help="dossiers seulement")
    return parseur.parse_args()


def _numeros(valeur: str) -> frozenset[str]:
    numeros = frozenset(n.strip() for n in valeur.split(",") if n.strip())
    if not numeros or not all(n.isdigit() for n in numeros):
        raise SystemExit("--contacts attend des numéros séparés par des virgules")
    return numeros


def _lister(depot: PostgresDossierRepository, contacts: dict[str, dict[str, object]]) -> None:
    for numero, contact in sorted(contacts.items(), key=lambda c: int(c[0])):
        deja = depot.par_contact_nr(numero)
        etat = f"déjà en base ({deja.id})" if deja else "pas en base"
        print(f"{numero} : {nom_affiche(contact, numero)} — {etat}", flush=True)


def _importer(
    depot: PostgresDossierRepository, contacts: dict[str, dict[str, object]], liste: str
) -> tuple[Dossier, ...]:
    voulus_nr = _numeros(liste)
    inconnus = voulus_nr - contacts.keys()
    if inconnus:
        raise SystemExit(f"contacts absents de Digifactory : {', '.join(sorted(inconnus))}")
    for numero in sorted(contacts.keys() - voulus_nr, key=int):
        print(f"{numero} : hors liste, ignoré", flush=True)
    depot.enregistrer_tenant(Tenant(id=TENANT_DEMO, nom="Portefeuille démo"))
    poses = (_poser(depot, contacts[numero]) for numero in sorted(voulus_nr, key=int))
    return tuple(dossier for dossier in poses if dossier is not None)


def _synchroniser(dossiers: tuple[Dossier, ...]) -> int:
    engine = engine_depuis_env()
    erreurs = 0
    for dossier in dossiers:
        print(f"Synchro {dossier.id}…", flush=True)
        for resultat in synchroniser_portefeuille(engine, (dossier,)):
            if resultat.erreur:
                erreurs += 1
                print(f"  ECHEC {resultat.erreur}", flush=True)
            elif resultat.rapport:
                rapport = resultat.rapport
                print(
                    f"  {rapport.nouvelles} nouvelles, {rapport.deja_connues} déjà connues, "
                    f"{rapport.rejets} rejetées",
                    flush=True,
                )
    return 1 if erreurs else 0


def main() -> int:
    arguments = _arguments()
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    depot = PostgresDossierRepository(engine_depuis_env())
    if arguments.sirene:
        _aligner_sirene(depot)
        return 0
    contacts = asyncio.run(_contacts_bruts())
    if arguments.lister:
        _lister(depot, contacts)
        return 0
    dossiers = _importer(depot, contacts, arguments.contacts)
    return 0 if arguments.sans_synchro else _synchroniser(dossiers)


def _poser(depot: PostgresDossierRepository, contact: dict[str, object]) -> Dossier | None:
    """Le dossier du contact, créé d'après Sirene s'il n'existe pas.
    `None` : société cessée, rien n'est créé."""
    numero = numero_contact(contact)
    existant = depot.par_contact_nr(numero)
    if existant is not None:
        print(f"{existant.id} ({existant.nom}) : déjà en base", flush=True)
        return existant
    voulu = dossier_depuis_contact(contact, date.today())
    dossier, avertissements = preparer_dossier(
        voulu, _fiche_sirene(siren_contact(contact)), date.today()
    )
    for avertissement in avertissements:
        print(f"{voulu.id} ({voulu.nom}) : {avertissement}", flush=True)
    if dossier is None:
        return None
    depot.enregistrer(dossier)
    print(f"{dossier.id} ({dossier.nom}) : créé", flush=True)
    return dossier


if __name__ == "__main__":
    sys.exit(main())
