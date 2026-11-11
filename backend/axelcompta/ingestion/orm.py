"""Tables du journal d'ingestion (doc 12 §1.2 : archivage brut immuable,
quarantaine, reprise incrémentale). Insert-only sauf le curseur, qui ne fait
qu'avancer."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
)

from axelcompta.core.db import metadata

# Tout ce que le fournisseur a renvoyé, tel quel. `id` = empreinte du contenu
# (dossier + source + payload canonique) : rejouer la même ligne ne crée rien,
# et une ligne modifiée côté fournisseur crée une nouvelle entrée sans effacer
# l'ancienne.
ingestion_brut = Table(
    "ingestion_brut",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("source", String, nullable=False),
    Column("transaction_id", String, nullable=True),
    Column("updated_at", String, nullable=True),
    Column("payload", JSON, nullable=False),
    Column("recu_le", DateTime, nullable=False),
)

# Ce qui n'a pas pu être comptabilisé sans jugement humain : ligne illisible,
# transaction modifiée ou supprimée après avoir été comptabilisée. `id` =
# empreinte (dossier, source, motif, payload) : un même cas n'est signalé
# qu'une fois malgré le recouvrement des lectures.
quarantaine_ingestion = Table(
    "quarantaine_ingestion",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("source", String, nullable=False),
    Column("motif", String, nullable=False),
    Column("transaction_id", String, nullable=True),
    Column("payload", JSON, nullable=False),
    Column("mis_en_quarantaine_le", DateTime, nullable=False),
)

# Point de reprise par (dossier, source) : plus grand `updated_at` traité.
curseurs_synchro = Table(
    "curseurs_synchro",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id"), primary_key=True),
    Column("source", String, primary_key=True),
    Column("dernier_updated_at", DateTime, nullable=False),
    Column("maj_le", DateTime, nullable=False),
)

# État courant du consentement DSP2, une ligne par dossier. Ce n'est pas une
# écriture comptable : on remplace le relevé précédent (doc 14 §2.2).
consentements_bancaires = Table(
    "consentements_bancaires",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id"), primary_key=True),
    Column("expire_le", Date, nullable=True),
    Column("statut", String, nullable=False),
    Column("releve_le", DateTime(timezone=True), nullable=False),
    Column("sante", String, nullable=False),
    Column("en_pause", Boolean, nullable=False),
    Column("acces_donnees", Boolean, nullable=False),
    Column("dernier_rafraichissement", DateTime, nullable=True),
)

# Un compte bancaire du dossier et son sous-compte 512x (AXE-832). Le numéro
# attribué ne change plus ; le nom et le solde suivent le relevé du
# fournisseur.
comptes_bancaires = Table(
    "comptes_bancaires",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False),
    Column("identifiant", String, nullable=False),
    Column("compte_comptable", String, nullable=False),
    Column("nom", String, nullable=True),
    Column("solde_banque_cts", BigInteger, nullable=True),
    Column("solde_releve_le", DateTime(timezone=True), nullable=True),
    Column("cree_le", DateTime(timezone=True), nullable=False),
    # AXE-729 : NULL à décider, TRUE comptabilisé, FALSE écarté.
    Column("retenu", Boolean, nullable=True),
    Column("a_relire", Boolean, nullable=False, server_default="false"),
    PrimaryKeyConstraint("dossier_id", "identifiant", name="comptes_bancaires_clef"),
    UniqueConstraint("dossier_id", "compte_comptable", name="comptes_bancaires_compte_unique"),
    CheckConstraint("compte_comptable LIKE '512_%'", name="comptes_bancaires_sous_compte"),
)

# AXE-819 : le « user » Rollee d'un dossier (créé à la première demande de
# connexion) et le branchement Rollee par lequel il a été créé.
utilisateurs_rollee = Table(
    "utilisateurs_rollee",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id"), primary_key=True),
    Column("rollee_user_id", String, nullable=False, unique=True),
    Column("branchement_id", String, nullable=False),
    Column("cree_le", DateTime(timezone=True), nullable=False),
)

# Les comptes de plateformes que le chauffeur a reliés dans Rollee Connect,
# relus chez Rollee (jamais saisis ici). Aucun montant.
comptes_rollee = Table(
    "comptes_rollee",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("nom", String, nullable=False),
    Column("connecte", Boolean, nullable=False),
    Column("reconnexion", Boolean, nullable=False),
    Column("relie_le", DateTime(timezone=True), nullable=True),
    Column("maj_le", DateTime(timezone=True), nullable=False),
)

# AXE-820 : webhooks Rollee reçus, gardés tels quels, traités par la file.
# Identifiant = empreinte du corps : un webhook rejoué n'est gardé qu'une fois.
evenements_rollee = Table(
    "evenements_rollee",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("branchement_id", String, nullable=False),
    Column("type", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("recu_le", DateTime(timezone=True), nullable=False),
    Column("traite_le", DateTime(timezone=True), nullable=True),
    Column("resultat", String, nullable=True),
)
