"""Tables du module anomaly (AXE-814)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Identity, String, Table, Text

from axelcompta.core.db import metadata

# Une ligne par changement d'état d'une alerte, jamais modifiée ni supprimée
# (trigger `qualifications_anomalie_immuables`). `rang` ordonne les lignes
# insérées à la même seconde.
qualifications_anomalie = Table(
    "qualifications_anomalie",
    metadata,
    Column("id", String, primary_key=True),
    Column("rang", BigInteger, Identity(), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("alerte_id", String, nullable=False),
    Column("etat", String, nullable=False),
    Column("commentaire", Text, nullable=False),
    Column("acteur", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
)
