"""Pose les noms attendus de B'CARS SERVICES et ajoute son compte flotte.

Simulation par défaut. `--appliquer` écrit les liens, relit les comptes et
note le journal comme un choix manuel. Ne relève pas les revenus. N'affiche
aucun nom de chauffeur : seulement le dossier, des identifiants et des nombres.

    python scripts/corriger_rollee_bcars.py
    python scripts/corriger_rollee_bcars.py --appliquer
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.ingestion.comptes_rollee import retenir_compte
from axelcompta.ingestion.liens_rollee import Lien
from axelcompta.ingestion.providers.rollee import RolleeHttpClient, RolleeIndisponible
from axelcompta.ingestion.rapprochement_rollee import empreinte, nom_du_profil
from axelcompta.plateformes_rollee import ServicesRollee, client_du_branchement, relire_comptes
from axelcompta.rapprochement_rollee_service import (
    DepotsRapprochement,
    cle_empreintes,
    depots_postgres,
    indices_dossier,
    sources_reelles,
)
from axelcompta.tenants.branchements import Branchement
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.journal_acces import PostgresJournalAcces

DOSSIER_ID = DossierId("DIGI_86930")
LIENS = (
    "652e57e2-e3e2-4ffb-9a18-343bc1a0d95e",
    "927b77da-eccd-4124-bba0-49a902edb688",
)
NOUVEAU = "5e320c90-364c-40cb-969d-574d3714d69b"
FLOTTE = LIENS[1]
ACTE = "lien_rollee"
ACTEUR = UserId("corriger-rollee-bcars")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--appliquer", action="store_true")
    return asyncio.run(_corriger(parseur.parse_args().appliquer))


async def _corriger(appliquer: bool) -> int:
    engine = engine_depuis_env()
    dossier = PostgresDossierRepository(engine).obtenir(DOSSIER_ID)
    if dossier is None:
        print("Dossier DIGI_86930 introuvable.")
        return 1
    noms = await _noms(engine, dossier)
    print(f"{dossier.nom} : {len(noms)} empreinte(s) de nom, {len(LIENS)} liens, 1 lien à ajouter.")
    depots = depots_postgres(engine)
    if not appliquer:
        await _simuler(depots.services, dossier.tenant_id, noms)
        print("Simulation : rien n'est écrit.")
        return 0
    _poser(depots, dossier, noms, engine)
    comptes = await relire_comptes(depots.services, dossier)
    retenus = sum(1 for compte in comptes if compte.retenu)
    ignores = sum(1 for compte in comptes if compte.titulaire_autre)
    print(f"{len(comptes)} comptes relus, {retenus} retenus, {ignores} ignorés. Revenus non lus.")
    return 0


async def _noms(engine: Engine, dossier: Dossier) -> tuple[str, ...]:
    sources = await sources_reelles(engine, dossier.tenant_id, (dossier,))
    return tuple(sorted(indices_dossier(dossier, sources, cle_empreintes()).empreintes.noms))


async def _simuler(services: ServicesRollee, tenant_id: TenantId, noms: tuple[str, ...]) -> None:
    par_user = {u.rollee_user_id: u for u in services.comptes.utilisateurs(DOSSIER_ID)}
    flotte = par_user.get(FLOTTE)
    for user_id in (*LIENS, NOUVEAU):
        utilisateur = par_user.get(user_id)
        if utilisateur is None and user_id != NOUVEAU:
            print(f"{user_id} : lien absent.")
            continue
        branchement_id = (
            utilisateur.branchement_id
            if utilisateur
            else (flotte.branchement_id if flotte else None)
        )
        if branchement_id is None:
            print(f"{user_id} : branchement inconnu.")
            continue
        lus, retenus, ignores = await _lire_comptes(
            services, tenant_id, branchement_id, user_id, frozenset(noms)
        )
        print(f"{user_id} : {lus} comptes, {retenus} retenus, {ignores} ignorés.")


async def _lire_comptes(
    services: ServicesRollee,
    tenant_id: TenantId,
    branchement_id: str,
    user_id: str,
    attendus: frozenset[str],
) -> tuple[int, int, int]:
    branchement = _branchement(services, tenant_id, branchement_id)
    if branchement is None:
        return 0, 0, 0
    client = client_du_branchement(services, branchement)
    try:
        return await _bilan(client, user_id, attendus)
    finally:
        await client.aclose()


def _branchement(
    services: ServicesRollee, tenant_id: TenantId, branchement_id: str
) -> Branchement | None:
    return next(
        (b for b in services.branchements.lister(tenant_id) if b.id == branchement_id), None
    )


async def _bilan(
    client: RolleeHttpClient, user_id: str, attendus: frozenset[str]
) -> tuple[int, int, int]:
    retenus = ignores = total = 0
    cle = cle_empreintes()
    for brut in await client.comptes(user_id):
        if not brut.get("id"):
            continue
        total += 1
        decision = await _decision(client, str(brut["id"]), cle, attendus)
        retenus += int(decision == (True, False))
        ignores += int(decision == (False, True))
    return total, retenus, ignores


async def _decision(
    client: RolleeHttpClient, account_id: str, cle: bytes, attendus: frozenset[str]
) -> tuple[bool, bool]:
    try:
        profil = await client.profil(account_id)
    except RolleeIndisponible as exc:
        if exc.statut is not None and exc.statut >= 500:
            return False, False
        raise
    nom = nom_du_profil(profil if isinstance(profil, dict) else {})
    return retenir_compte(empreinte(cle, nom), attendus, False)


def _poser(
    depots: DepotsRapprochement, dossier: Dossier, noms: tuple[str, ...], engine: Engine
) -> None:
    maintenant = datetime.now(UTC)
    journal = PostgresJournalAcces(engine)
    for user_id in LIENS:
        if not depots.liens.fixer_noms(user_id, noms):
            print(f"{user_id} : lien absent, rien n'est posé.")
            continue
        journal.noter(dossier.id, ACTE, f"choisi:{user_id}", ACTEUR, maintenant)
        print(f"{user_id} : noms attendus posés.")
    _ajouter(depots, dossier, noms, maintenant, journal)


def _ajouter(
    depots: DepotsRapprochement,
    dossier: Dossier,
    noms: tuple[str, ...],
    maintenant: datetime,
    journal: PostgresJournalAcces,
) -> None:
    if any(u.rollee_user_id == NOUVEAU for u in depots.services.comptes.utilisateurs(dossier.id)):
        print(f"{NOUVEAU} : déjà relié.")
        return
    flotte = next(
        (u for u in depots.services.comptes.utilisateurs(dossier.id) if u.rollee_user_id == FLOTTE),
        None,
    )
    if flotte is None:
        print(f"{NOUVEAU} : branchement flotte introuvable.")
        return
    depots.liens.lier(
        Lien(
            dossier.id,
            NOUVEAU,
            flotte.branchement_id,
            "manuel",
            maintenant,
            None,
            str(ACTEUR),
            noms,
        )
    )
    journal.noter(dossier.id, ACTE, f"choisi:{NOUVEAU}", ACTEUR, maintenant)
    print(f"{NOUVEAU} : lien ajouté.")


if __name__ == "__main__":
    sys.exit(main())
