"""Crée un dossier par contact Digifactory du portefeuille, puis synchronise.

**Aucun compte n'est créé** (depuis le 2026-11-05, AXE-726) : le dirigeant
de chaque société est invité par le gestionnaire avec sa vraie adresse
(écran Invitations), et confirme sa configuration à la première connexion
(AXE-730). La forme juridique est reprise de Sirene quand le contact a un
SIREN ; le reste de la configuration est une valeur par défaut.

Usage, depuis backend/ :

    python scripts/ajouter_chauffeurs_digifactory.py               # dossiers + synchro
    python scripts/ajouter_chauffeurs_digifactory.py --sans-synchro # dossiers seulement
    python scripts/ajouter_chauffeurs_digifactory.py --formes       # formes Sirene seulement

Idempotent : un contact déjà mappé est laissé tel quel. La synchro rejoue
sans doublon (curseur).
"""

from __future__ import annotations

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


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    depot = PostgresDossierRepository(engine_depuis_env())
    if len(sys.argv) > 1 and sys.argv[1] == "--formes":
        _aligner_formes(depot)
        return 0
    depot.enregistrer_tenant(Tenant(id=TENANT_DEMO, nom="Portefeuille démo"))
    voulus = tuple(
        dossier_depuis_contact(contact, date.today())
        for contact in asyncio.run(_contacts_bruts()).values()
    )
    dossiers = tuple(_poser(depot, voulu) for voulu in voulus)
    _aligner_formes(depot)
    if "--sans-synchro" in sys.argv[1:]:
        return 0
    engine = engine_depuis_env()
    erreurs = 0
    for dossier in dossiers:
        print(f"Synchro {dossier.id}…", flush=True)
        resultats = synchroniser_portefeuille(engine, (dossier,))
        for resultat in resultats:
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


def _poser(depot: PostgresDossierRepository, voulu: Dossier) -> Dossier:
    dossier, etat = _assurer_dossier(depot, voulu)
    print(f"{dossier.id} ({dossier.nom}) : {etat}", flush=True)
    return dossier


if __name__ == "__main__":
    sys.exit(main())
