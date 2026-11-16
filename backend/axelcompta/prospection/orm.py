"""Table des demandes d'échange (AXE-949).

Pas de `tenant_id` ni de `dossier_id` : une demande arrive avant tout
portefeuille, d'une personne qui n'a pas de compte. Le rôle web ne peut donc
pas la lire en entier : il ajoute une ligne, compte les demandes récentes et
note le résultat de la notification (voir la migration).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, Table

from axelcompta.core.db import metadata

demandes_echange = Table(
    "demandes_echange",
    metadata,
    Column("id", String, primary_key=True),
    Column("nom", String, nullable=False),
    Column("email", String, nullable=False),
    Column("organisation", String, nullable=False),
    Column("role", String, nullable=False),
    Column("message", String, nullable=True),
    Column("cree_le", DateTime(timezone=True), nullable=False),
    # Rempli quand l'équipe a été prévenue (Slack).
    Column("notifiee_le", DateTime(timezone=True), nullable=True),
    Column("tentatives", Integer, nullable=False, server_default="0"),
    Column("derniere_erreur", String, nullable=True),
    CheckConstraint("role IN ('cabinet', 'centrale')", name="ck_demandes_echange_role"),
    Index("ix_demandes_echange_email_cree_le", "email", "cree_le"),
)
