"""Bulletin de connexion des dossiers d'un portefeuille (AXE-728).

Lecture seule. Par dossier retenu pour la synchro : opérations Digifactory
reçues et période couverte, comptes bancaires, santé de la connexion,
consentement, lignes en quarantaine. Aucune donnée brute (ni libellé, ni
montant). Un dossier en authentification forte, sans accès ou à zéro
opération est signalé avant qu'on catégorise.

La synchro elle-même tourne toutes les heures (`axelcompta.taches`) ; on la
relance à la main avec `python -m axelcompta.synchro_digifactory`.

Usage, depuis backend/ (DATABASE_URL défini) :

    python -m axelcompta.bulletin_connexion --tenant TENANT_DEMO
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import TenantId
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.tags import etat_du_portefeuille, retenus
from axelcompta.tenants.tags_postgres import PostgresTagsRepository

SOURCE = "digifactory"


@dataclass(frozen=True, slots=True)
class LigneBulletin:
    dossier_id: str
    nom: str
    contact_nr: str | None
    operations: int
    premiere: date | None
    derniere: date | None
    comptes: int
    comptes_retenus: int
    comptes_a_decider: int
    sante: str | None  # None : jamais relevé par une synchro
    consentement: str | None
    expire_le: date | None
    quarantaine: int


def alertes(ligne: LigneBulletin) -> tuple[str, ...]:
    """Ce qui empêche de catégoriser ce dossier tel quel."""
    if ligne.contact_nr is None:
        return ("pas de contact Digifactory",)
    trouvees: list[str] = []
    if ligne.sante is None:
        trouvees.append("jamais synchronisé")
    elif ligne.sante != "ok":
        trouvees.append(f"connexion {ligne.sante}")
    if ligne.consentement in ("expire", "a_renouveler"):
        trouvees.append(f"consentement {ligne.consentement}")
    if ligne.operations == 0:
        trouvees.append("zéro opération")
    if ligne.comptes_a_decider:
        trouvees.append(f"{ligne.comptes_a_decider} compte(s) à décider")
    if ligne.quarantaine:
        trouvees.append(f"{ligne.quarantaine} en quarantaine")
    return tuple(trouvees)


def _periode(ligne: LigneBulletin) -> str:
    if ligne.premiere is None or ligne.derniere is None:
        return "—"
    return f"{ligne.premiere:%d/%m/%Y} → {ligne.derniere:%d/%m/%Y}"


def rendre(lignes: Sequence[LigneBulletin], le: date) -> str:
    """Le bulletin en Markdown : un tableau, puis les dossiers à voir."""
    prets = [ligne for ligne in lignes if not alertes(ligne)]
    sortie = [
        f"# Bulletin de connexion du {le:%d/%m/%Y}",
        "",
        f"{len(lignes)} dossiers retenus pour la synchro, {len(prets)} prêts à catégoriser.",
        "",
        "| Dossier | Opérations | Période | Comptes (retenus) | Connexion | Consentement "
        "| Quarantaine |",
        "|---|---:|---|---|---|---|---:|",
    ]
    for ligne in lignes:
        expire = f" (→ {ligne.expire_le:%d/%m/%Y})" if ligne.expire_le else ""
        sortie.append(
            f"| {ligne.nom} ({ligne.dossier_id}) | {ligne.operations} | {_periode(ligne)} "
            f"| {ligne.comptes} ({ligne.comptes_retenus}) | {ligne.sante or '—'} "
            f"| {(ligne.consentement or '—')}{expire} | {ligne.quarantaine} |"
        )
    a_voir = [(ligne, alertes(ligne)) for ligne in lignes if alertes(ligne)]
    if a_voir:
        sortie += ["", "## À voir avant de catégoriser", ""]
        sortie += [f"- **{ligne.nom}** : {', '.join(motifs)}" for ligne, motifs in a_voir]
    return "\n".join(sortie) + "\n"


_REQUETE = text(
    """
    SELECT d.id,
      (SELECT count(DISTINCT b.transaction_id) FROM ingestion_brut b
         WHERE b.dossier_id = d.id AND b.source = :source) AS operations,
      (SELECT min(left(b.payload->>'date', 10)) FROM ingestion_brut b
         WHERE b.dossier_id = d.id AND b.source = :source) AS premiere,
      (SELECT max(left(b.payload->>'date', 10)) FROM ingestion_brut b
         WHERE b.dossier_id = d.id AND b.source = :source) AS derniere,
      (SELECT count(*) FROM comptes_bancaires c WHERE c.dossier_id = d.id) AS comptes,
      (SELECT count(*) FROM comptes_bancaires c
         WHERE c.dossier_id = d.id AND c.retenu) AS comptes_retenus,
      (SELECT count(*) FROM comptes_bancaires c
         WHERE c.dossier_id = d.id AND c.retenu IS NULL) AS comptes_a_decider,
      cb.sante, cb.statut, cb.expire_le,
      (SELECT count(*) FROM quarantaine_ingestion q
         WHERE q.dossier_id = d.id AND q.source = :source
           AND NOT EXISTS (SELECT 1 FROM resolutions_quarantaine r
                             WHERE r.entree_id = q.id)) AS quarantaine
    FROM dossiers d
    LEFT JOIN consentements_bancaires cb ON cb.dossier_id = d.id
    WHERE d.id = ANY(:ids)
    """
)


def lire(engine: Engine, dossiers: Sequence[Dossier]) -> list[LigneBulletin]:
    with engine.connect() as connexion:
        connexion.execute(text("SET TRANSACTION READ ONLY"))
        par_id = {
            ligne.id: ligne
            for ligne in connexion.execute(
                _REQUETE, {"source": SOURCE, "ids": [d.id for d in dossiers]}
            )
        }
    lignes = []
    for dossier in dossiers:
        r = par_id[dossier.id]
        lignes.append(
            LigneBulletin(
                dossier_id=dossier.id,
                nom=dossier.nom,
                contact_nr=dossier.contact_nr,
                operations=r.operations,
                premiere=date.fromisoformat(r.premiere) if r.premiere else None,
                derniere=date.fromisoformat(r.derniere) if r.derniere else None,
                comptes=r.comptes,
                comptes_retenus=r.comptes_retenus,
                comptes_a_decider=r.comptes_a_decider,
                sante=r.sante,
                consentement=r.statut,
                expire_le=r.expire_le,
                quarantaine=r.quarantaine,
            )
        )
    return sorted(lignes, key=lambda ligne: (bool(alertes(ligne)), ligne.nom))


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--tenant", required=True)
    args = parseur.parse_args()

    engine = engine_depuis_env()
    tenant_id = TenantId(args.tenant)
    tous = PostgresDossierRepository(engine).lister_par_tenant(tenant_id)
    dossiers = retenus(
        tous, etat_du_portefeuille(PostgresTagsRepository(engine), tenant_id), "synchro"
    )
    print(rendre(lire(engine, dossiers), date.today()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
