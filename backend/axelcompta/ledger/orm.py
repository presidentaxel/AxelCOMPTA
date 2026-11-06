"""Mapping SQLAlchemy Core de `Ecriture`/`LigneEcriture` (doc 06 §2). Défini
séparément de `models.py` : le domaine reste pur (doc 08 §2.1), seul
`repository.py` fait de l'I/O contre ces tables.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, Date, ForeignKey, Index, String, Table

from axelcompta.core.db import metadata

ecritures = Table(
    "ecritures",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False),
    Column("journal", String, nullable=False),
    Column("date", Date, nullable=False),
    Column("libelle", String, nullable=False),
    Column("reference_piece", String, nullable=True),
)

lignes_ecriture = Table(
    "lignes_ecriture",
    metadata,
    Column("id", String, primary_key=True),
    Column("ecriture_id", String, ForeignKey("ecritures.id"), nullable=False, index=True),
    Column("compte", String, nullable=False),
    Column("sens", String, nullable=False),
    Column("montant_centimes", BigInteger, nullable=False),
    Column("devise", String, nullable=False),
    Column("analytique", String, nullable=True),
    Column("code_tva", String, nullable=True),
)

# Lecture d'un grand livre : par dossier, dans l'ordre (AXE-824).
Index("ix_ecritures_dossier_date", ecritures.c.dossier_id, ecritures.c.date, ecritures.c.id)
