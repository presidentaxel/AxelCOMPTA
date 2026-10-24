"""Table `justificatifs` — une photo par écriture, dans un tenant."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, LargeBinary, PrimaryKeyConstraint, String, Table

from axelcompta.core.db import metadata

justificatifs = Table(
    "justificatifs",
    metadata,
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False),
    Column("ecriture_id", String, nullable=False),
    Column("empreinte", String, nullable=False),
    Column("extension", String, nullable=False),
    Column("taille_octets", Integer, nullable=False),
    Column("contenu", LargeBinary, nullable=False),
    PrimaryKeyConstraint("tenant_id", "dossier_id", "ecriture_id", name="justificatifs_clef"),
)
