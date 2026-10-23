"""Remise à neuf du portefeuille de démo, à la carte, depuis le menu Démo.

Démo uniquement, autorisé explicitement par Louis le 2026-09-25 : rien de
ceci n'existe en V1. Les décisions et les preuves signées sont verrouillées
en base (triggers `*_immuables`, doc 12 §1.3). Les effacer demande la
connexion propriétaire (`DATABASE_URL`, jamais `DATABASE_URL_WEB`) et la
suspension de ces verrous le temps d'une seule transaction : si une
instruction échoue, tout est annulé et les verrous restent en place. La
route qui l'appelle n'accepte que le portefeuille de démo et un admin.

Jamais touché, quelles que soient les parties cochées : le grand livre
(une décision ne le modifie pas, elle se lit par-dessus), le journal
d'audit, les comptes Supabase et les droits d'équipe (sans ligne de droit,
un compte redeviendrait admin). Les dossiers branchés à Digifactory
(`contact_nr` renseigné) non plus : leurs décisions, notifications et
photos ne sont pas celles de Karim, Sophie et Yanis.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from axelcompta.core.ids import TenantId
from axelcompta.demo_seed import poser_jalons_demo
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.signature_postgres import PostgresSignatureRepository

NOM_PORTEFEUILLE_DEMO = "Portefeuille démo"

_DOSSIERS_DU_TENANT = "SELECT id FROM dossiers WHERE tenant_id = :tenant AND contact_nr IS NULL"
_DOSSIERS_DIGIFACTORY = (
    "SELECT id FROM dossiers WHERE tenant_id = :tenant AND contact_nr IS NOT NULL"
)


@dataclass(frozen=True, slots=True)
class Partie:
    cle: str
    libelle: str
    detail: str


PARTIES: tuple[Partie, ...] = (
    Partie(
        "decisions",
        "Dépenses tranchées",
        "Les dépenses déjà tranchées repassent « à trancher ».",
    ),
    Partie(
        "decisions_digifactory",
        "Dépenses tranchées des dossiers Digifactory",
        "Seulement les décisions des dossiers branchés à Digifactory : leurs opérations "
        "repassent « à trancher ». Les opérations elles-mêmes ne sont pas touchées.",
    ),
    Partie(
        "jalons",
        "Frise 2025",
        "Clôture, signatures, greffe et impôts reviennent à leur état de départ.",
    ),
    Partie("justificatifs", "Justificatifs photo", "Les photos jointes sont supprimées."),
    Partie("rappels", "Rappels", "Règles de rappel et rappels déclenchés."),
    Partie(
        "notifications",
        "Notifications",
        "Les notifications de la cloche, qui bloquent aussi les renvois trop rapprochés.",
    ),
    Partie(
        "portefeuille",
        "Organisation",
        "Nom de l'organisation et entreprises retirées de la liste.",
    ),
)

CLES_PARTIES = frozenset(partie.cle for partie in PARTIES)


def _effacer_verrouillee(
    connexion: Connection,
    table: str,
    parametres: dict[str, str],
    dossiers: str = _DOSSIERS_DU_TENANT,
) -> None:
    connexion.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {table}_immuables"))
    connexion.execute(text(f"DELETE FROM {table} WHERE dossier_id IN ({dossiers})"), parametres)
    connexion.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER {table}_immuables"))


def _effacer(
    connexion: Connection,
    table: str,
    parametres: dict[str, str],
    dossiers: str = _DOSSIERS_DU_TENANT,
) -> None:
    connexion.execute(text(f"DELETE FROM {table} WHERE dossier_id IN ({dossiers})"), parametres)


def _remettre_en_base(connexion: Connection, parties: frozenset[str], tenant: str) -> None:
    parametres = {"tenant": tenant}
    if "decisions" in parties:
        # `annotations_dev` recopie les décisions pour le réentraînement ML.
        _effacer(connexion, "annotations_dev", parametres)
        _effacer_verrouillee(connexion, "decisions_humaines", parametres)
    if "decisions_digifactory" in parties:
        # Pour rejouer « tout confirmer » sur des données réelles : sans ça,
        # une répétition laisse le dossier entièrement tranché.
        _effacer(connexion, "annotations_dev", parametres, _DOSSIERS_DIGIFACTORY)
        _effacer_verrouillee(connexion, "decisions_humaines", parametres, _DOSSIERS_DIGIFACTORY)
    if "jalons" in parties:
        _effacer_verrouillee(connexion, "documents_signes", parametres)
    if "rappels" in parties:
        for table in ("rappels", "regles_rappel"):
            connexion.execute(text(f"DELETE FROM {table} WHERE tenant_id = :tenant"), parametres)
    if "notifications" in parties:
        _effacer(connexion, "notifications_envoyees", parametres)
    if "portefeuille" in parties:
        connexion.execute(
            text(
                "UPDATE dossiers SET retire_le = NULL "
                "WHERE tenant_id = :tenant AND contact_nr IS NULL"
            ),
            parametres,
        )
        connexion.execute(
            text("UPDATE tenants SET nom = :nom WHERE id = :tenant"),
            {**parametres, "nom": NOM_PORTEFEUILLE_DEMO},
        )


def reinitialiser_demo(
    proprietaire: Engine, tenant_id: TenantId, parties: frozenset[str], justificatifs: Path
) -> list[str]:
    """Remet les `parties` du portefeuille `tenant_id` dans leur état
    d'amorçage. Retourne les dossiers concernés."""
    inconnues = parties - CLES_PARTIES
    if inconnues:
        raise ValueError(f"parties inconnues : {sorted(inconnues)}")
    with proprietaire.begin() as connexion:
        dossier_ids = list(
            connexion.execute(text(_DOSSIERS_DU_TENANT), {"tenant": str(tenant_id)}).scalars()
        )
        _remettre_en_base(connexion, parties, str(tenant_id))
        if "justificatifs" in parties:
            for dossier_id in dossier_ids[:10_000]:
                connexion.execute(
                    text(
                        "DELETE FROM justificatifs "
                        "WHERE tenant_id = :tenant AND dossier_id = :dossier"
                    ),
                    {"tenant": str(tenant_id), "dossier": dossier_id},
                )
    if "jalons" in parties:
        poser_jalons_demo(
            PostgresDossierRepository(proprietaire),
            PostgresLedgerService(proprietaire),
            PostgresSignatureRepository(proprietaire),
        )
    if "justificatifs" in parties:
        for dossier_id in dossier_ids[:10_000]:
            shutil.rmtree(justificatifs / dossier_id, ignore_errors=True)
            shutil.rmtree(justificatifs / str(tenant_id) / dossier_id, ignore_errors=True)
    return dossier_ids
