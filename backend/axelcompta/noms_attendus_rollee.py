"""Poser les noms attendus sur les liens Rollee d'avant la PR 170 (AXE-922).

Composition root. Depuis la migration `f3a9c7e15d82`, un lien sans noms
attendus est traité comme « créé par le chauffeur » : tous les comptes de
plateforme du user Rollee sont retenus. Les liens posés avant (à la main ou
par le rapprochement) n'en ont pas. Or un user « flotte » peut porter les
comptes de plusieurs chauffeurs : leurs revenus seraient lus pour ce dossier.

Pour chaque lien `auto` ou `manuel` sans noms attendus : les noms du dossier
(contact Digifactory, associés), puis, compte par compte, ce qui serait
retenu. `ecrire` : pose les noms et relit les comptes du dossier. Aucun nom
n'est affiché, seulement des identifiants abrégés et des nombres.
"""

from __future__ import annotations

from dataclasses import dataclass

from axelcompta.core.ids import TenantId
from axelcompta.ingestion.comptes_rollee import UtilisateurRollee
from axelcompta.ingestion.liens_rollee import Lien
from axelcompta.plateformes_rollee import (
    ServicesRollee,
    _branchement_du_user,
    client_du_branchement,
    relire_comptes,
    titulaire_du_compte,
)
from axelcompta.rapprochement_rollee_service import (
    DepotsRapprochement,
    cle_empreintes,
    indices_dossier,
)
from axelcompta.tenants.models import Dossier


@dataclass(frozen=True, slots=True)
class Evaluation:
    comptes: int = 0
    retenus: int = 0
    autres: int = 0  # au nom d'un autre chauffeur


def a_completer(liens: list[Lien]) -> list[Lien]:
    """Les liens à compléter : posés par le rapprochement ou à la main, sans
    noms attendus. Un lien « cree » (user créé pour ce dossier) reste tel quel."""
    return [lien for lien in liens if lien.origine != "cree" and lien.noms_attendus is None]


def ligne(dossier: Dossier, lien: Lien, noms: tuple[str, ...], evaluation: Evaluation) -> str:
    debut = f"{dossier.nom} · {lien.rollee_user_id[:8]}… : "
    if not noms:
        return debut + "aucun nom connu, aucun compte ne sera retenu"
    return debut + (
        f"{evaluation.comptes} compte(s), {evaluation.retenus} retenu(s), "
        f"{evaluation.autres} au nom d'un autre chauffeur"
    )


async def evaluer(
    services: ServicesRollee, dossier: Dossier, lien: Lien, noms: tuple[str, ...]
) -> Evaluation:
    """Ce que les noms attendus retiendraient, compte par compte (lecture seule)."""
    utilisateur = UtilisateurRollee(dossier.id, lien.rollee_user_id, lien.branchement_id, noms)
    client = client_du_branchement(services, _branchement_du_user(services, dossier, utilisateur))
    try:
        bruts = [b for b in await client.comptes(lien.rollee_user_id) if b.get("id")]
        decisions = [
            await titulaire_du_compte(client, str(brut["id"]), utilisateur) for brut in bruts
        ]
    finally:
        await client.aclose()
    return Evaluation(
        len(decisions),
        sum(1 for retenu, _autre in decisions if retenu),
        sum(1 for _retenu, autre in decisions if autre),
    )


async def poser_noms_attendus(
    depots: DepotsRapprochement, tenant_id: TenantId, ecrire: bool
) -> list[str]:
    liens = a_completer(depots.liens.liens(tenant_id))
    if not liens:
        return ["Aucun lien Rollee à compléter."]
    par_id = {str(d.id): d for d in depots.dossiers.lister_par_tenant(tenant_id)}
    concernes = tuple(
        par_id[i] for i in dict.fromkeys(str(lien.dossier_id) for lien in liens) if i in par_id
    )
    sources = await depots.sources(tenant_id, concernes)
    cle = cle_empreintes()
    lignes = []
    for dossier in concernes:
        noms = tuple(sorted(indices_dossier(dossier, sources, cle).empreintes.noms))
        for lien in (x for x in liens if str(x.dossier_id) == str(dossier.id)):
            evaluation = (
                await evaluer(depots.services, dossier, lien, noms) if noms else Evaluation()
            )
            lignes.append(ligne(dossier, lien, noms, evaluation))
            if ecrire:
                depots.liens.fixer_noms(lien.rollee_user_id, noms)
        if ecrire:
            await relire_comptes(depots.services, dossier)
    mode = "noms posés, comptes relus" if ecrire else "simulation : rien n'est écrit"
    return [*lignes, f"{len(liens)} lien(s) à compléter ({mode})."]
