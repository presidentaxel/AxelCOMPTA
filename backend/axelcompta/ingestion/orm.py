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
    Integer,
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
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("rollee_user_id", String, primary_key=True),
    Column("branchement_id", String, nullable=False),
    Column("cree_le", DateTime(timezone=True), nullable=False),  # date du lien
    # AXE-911 : cree (espace chauffeur), auto (rapprochement), manuel (gestionnaire).
    Column("origine", String, nullable=False, server_default="cree"),
    Column("indice", String, nullable=True),
    Column("relie_par", String, nullable=True),
    CheckConstraint("origine IN ('cree', 'auto', 'manuel')", name="ck_utilisateurs_rollee_origine"),
)

# AXE-911 : un lien retiré n'est jamais effacé (ajout seul).
liens_rollee_retires = Table(
    "liens_rollee_retires",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("rollee_user_id", String, nullable=False),
    Column("branchement_id", String, nullable=False),
    Column("origine", String, nullable=False),
    Column("indice", String, nullable=True),
    Column("relie_par", String, nullable=True),
    Column("relie_le", DateTime(timezone=True), nullable=False),
    Column("retire_le", DateTime(timezone=True), nullable=False),
    Column("retire_par", String, nullable=False),
    Column("motif", String, nullable=False),
)

# AXE-911 : users Rollee que le rapprochement n'a pas reliés seuls. Aucune
# donnée en clair : candidats (dossier, raisons) et aperçu masqué.
rapprochements_rollee = Table(
    "rapprochements_rollee",
    metadata,
    Column("rollee_user_id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("branchement_id", String, nullable=False),
    Column("etat", String, nullable=False),
    Column("candidats", JSON, nullable=False),
    Column("apercu", JSON, nullable=False),
    Column("maj_le", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "etat IN ('a_choisir', 'non_trouve', 'ecarte')", name="ck_rapprochements_rollee_etat"
    ),
)

# Carte des users Rollee déjà lus : empreintes et aperçu masqué, rien en clair.
# Un passage suivant les compare sans rappeler le profil ni l'IBAN.
cartes_rollee = Table(
    "cartes_rollee",
    metadata,
    Column("rollee_user_id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("branchement_id", String, nullable=False),
    Column("dossier_metadata", String, nullable=True),
    Column("empreintes", JSON, nullable=False),
    Column("apercu", JSON, nullable=False),
    Column("lu_le", DateTime(timezone=True), nullable=False),
    Column("accounts_number", Integer, nullable=True),
    Column("nom", String, nullable=True),
    Column("email_masque", String, nullable=True),
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
    Column("rollee_user_id", String, nullable=True),
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

# AXE-821 : relevés de revenus des plateformes (Rollee), une ligne par compte
# et par période, et leur rapprochement avec le virement en banque.
settlements_plateforme = Table(
    "settlements_plateforme",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("account_id", String, nullable=False),
    Column("plateforme", String, nullable=False),
    Column("periode_debut", Date, nullable=False),
    Column("periode_fin", Date, nullable=False),
    Column("verse_le", Date, nullable=False),
    Column("brut_cts", BigInteger, nullable=False),
    Column("commission_cts", BigInteger, nullable=False),
    Column("regime_tva_commission", String, nullable=False),
    Column("verse_cts", BigInteger, nullable=False),
    Column("devise", String, nullable=False),
    Column("source", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("etat", String, nullable=False),
    Column("ecriture_id", String, nullable=True),
    Column("motif", String, nullable=True),
    Column("maj_le", DateTime(timezone=True), nullable=False),
)
