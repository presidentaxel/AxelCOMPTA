"""Insertion dans le journal d'audit, dans la transaction déjà ouverte.

Pas de lecture ici : la preuve est la ligne elle-même, jamais mise à jour.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.engine import Connection

from axelcompta.core.ids import DossierId, UserId

from .orm import journal_audit

# Décisions et signatures existent déjà. Connexion, export et consultation
# sont les actes V1 encore à tracer (doc 12) : même journal, mêmes colonnes.
ACTE_CONNEXION = "connexion"
ACTE_EXPORT = "export"
ACTE_CONSULTATION = "consultation"


def noter(
    connexion: Connection,
    dossier_id: DossierId,
    type_acte: str,
    reference: str,
    acteur: UserId,
    acte_le: datetime,
) -> None:
    connexion.execute(
        journal_audit.insert().values(
            id=str(uuid.uuid4()),
            dossier_id=dossier_id,
            type_acte=type_acte,
            reference=reference,
            acteur=acteur,
            acte_le=acte_le,
        )
    )
