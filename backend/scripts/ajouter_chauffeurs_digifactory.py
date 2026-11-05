"""Crée un dossier par contact Digifactory du portefeuille, puis synchronise.

**Aucun compte n'est créé** (depuis le 2026-11-05, AXE-726) : le dirigeant
de chaque société est invité par le gestionnaire avec sa vraie adresse
(écran Invitations), et confirme sa configuration à la première connexion
(AXE-730). La forme juridique est reprise de Sirene quand le contact a un
SIREN ; le reste de la configuration est une valeur par défaut.

Le compte Digifactory de Serenity contient aussi des contacts qui ne sont
pas des chauffeurs (ses propres sociétés, des plateformes) : on ne crée de
dossier **que pour les contacts listés** (AXE-726). Un contact hors liste
est signalé, jamais enregistré. `--lister` affiche les contacts sans rien
écrire, pour choisir.

Usage, depuis backend/ :

    python scripts/ajouter_chauffeurs_digifactory.py --lister
    python scripts/ajouter_chauffeurs_digifactory.py --contacts 7416,8780 --sans-synchro
    python scripts/ajouter_chauffeurs_digifactory.py --contacts 7416,8780
    python scripts/ajouter_chauffeurs_digifactory.py --formes

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
    forme_depuis_nature_juridique,
    nom_affiche,
    numero_contact,
    siren_contact,
)
from axelcompta.ingestion.providers.digifactory import DigifactoryHttpClient
from axelcompta.synchro_digifactory import synchroniser_portefeuille
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository


def _assurer_dossier(depot: PostgresDossierRepository, voulu: Dossier) -> tuple[Dossier, str]:
    if voulu.contact_nr is None:
        raise RuntimeError(f"{voulu.id} sans contact")
    existant = depot.par_contact_nr(voulu.contact_nr)
    if existant is not None:
        return existant, "déjà en base"
    depot.enregistrer(voulu)
    enregistre = depot.obtenir(voulu.id)
    if enregistre is None:
        raise RuntimeError(f"{voulu.id} non relu après écriture")
    return enregistre, "créé"


async def _contacts_bruts() -> dict[str, dict[str, object]]:
    client = DigifactoryHttpClient.depuis_env()
    try:
        brut = await client.contacts()
    finally:
        await client.aclose()
    return {str(nr): contact for nr, contact in brut.items() if isinstance(contact, dict)}


def _forme_sirene(siren: str) -> str | None:
    """Recherche d'entreprises (data.gouv, sans clé). On n'accepte que le
    résultat dont le SIREN est exactement celui demandé."""
    reponse = httpx.get(
        "https://recherche-entreprises.api.gouv.fr/search",
        params={"q": siren, "per_page": 1},
        headers={"accept": "application/json"},
        timeout=15.0,
    )
    reponse.raise_for_status()
    resultats = reponse.json().get("results") or []
    if not resultats or str(resultats[0].get("siren") or "") != siren:
        return None
    nature = resultats[0].get("nature_juridique")
    if not isinstance(nature, str):
        return None
    return forme_depuis_nature_juridique(nature)


def _aligner_formes(depot: PostgresDossierRepository) -> None:
    for contact in asyncio.run(_contacts_bruts()).values():
        dossier = depot.par_contact_nr(numero_contact(contact))
        if dossier is None:
            continue
        siren = siren_contact(contact)
        if siren is None:
            print(
                f"{dossier.id} : pas de SIREN, forme laissée {dossier.forme_juridique}", flush=True
            )
            continue
        forme = _forme_sirene(siren)
        if forme is None:
            print(f"{dossier.id} : nature juridique non reconnue", flush=True)
            continue
        if forme != dossier.forme_juridique:
            depot.poser_forme_juridique(dossier.id, forme)
        print(f"{dossier.id} : {forme}", flush=True)


def _arguments() -> argparse.Namespace:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parseur.add_mutually_exclusive_group(required=True)
    action.add_argument("--lister", action="store_true", help="affiche les contacts, n'écrit rien")
    action.add_argument(
        "--contacts", help="numéros de contact à importer, séparés par des virgules"
    )
    action.add_argument("--formes", action="store_true", help="reprend les formes Sirene")
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
    dossiers = tuple(
        _poser(depot, dossier_depuis_contact(contacts[numero], date.today()))
        for numero in sorted(voulus_nr, key=int)
    )
    _aligner_formes(depot)
    return dossiers


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
    if arguments.formes:
        _aligner_formes(depot)
        return 0
    contacts = asyncio.run(_contacts_bruts())
    if arguments.lister:
        _lister(depot, contacts)
        return 0
    dossiers = _importer(depot, contacts, arguments.contacts)
    return 0 if arguments.sans_synchro else _synchroniser(dossiers)


def _poser(depot: PostgresDossierRepository, voulu: Dossier) -> Dossier:
    dossier, etat = _assurer_dossier(depot, voulu)
    print(f"{dossier.id} ({dossier.nom}) : {etat}", flush=True)
    return dossier


if __name__ == "__main__":
    sys.exit(main())
