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
# Le dirigeant confirme forme et régimes (AXE-730).
ACTE_CONFIGURATION = "configuration_confirmee"
# Compte bancaire retenu (pro) ou écarté (personnel) par le dirigeant (AXE-729).
ACTE_COMPTE_RETENU = "compte_bancaire_retenu"
ACTE_COMPTE_ECARTE = "compte_bancaire_ecarte"
# Périodicité et échéance de la TVA réglées (AXE-805).
ACTE_PARAMETRES_TVA = "parametres_tva"
# Siège, capital et associés saisis par le dirigeant (AXE-846).
ACTE_IDENTITE = "identite_saisie"
# Écart avec un registre officiel tranché par le dirigeant (AXE-849).
ACTE_ECART_REGISTRE = "ecart_registre_tranche"


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
