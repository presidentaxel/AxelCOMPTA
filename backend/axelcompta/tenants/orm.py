"""Mapping SQLAlchemy Core de `Tenant` et `Dossier` (doc 03 §3bis). Un seul
schéma (doc 17 §3) : l'isolation par `tenant_id` se fait dans les requêtes du
repository (`DossierRepository.lister_par_tenant`) ; la RLS Postgres de la V1
(doc 03 §7) reste à faire.
"""

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
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    text,
    true,
)

from axelcompta.core.db import metadata

tenants = Table(
    "tenants",
    metadata,
    Column("id", String, primary_key=True),
    Column("nom", String, nullable=False),
    Column("relance_consentement", String, nullable=False, server_default="auto"),
)

dossiers = Table(
    "dossiers",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("forme_juridique", String, nullable=False),
    Column("regime_imposition", String, nullable=False),
    Column("regime_tva", String, nullable=False),
    Column("nom", String, nullable=False),
    Column("tva_recettes_regime", String, nullable=False),
    Column("exercice_debut", Date, nullable=False),
    Column("plateformes", JSON, nullable=False),
    Column("mode_acces_bancaire", String, nullable=False),
    # Unique quand renseigné (Postgres autorise plusieurs NULL) : un contact
    # Digifactory ne peut pointer que vers un seul dossier.
    Column("contact_nr", String, nullable=True, unique=True),
    Column("exercice_fin", Date, nullable=True),
    Column("retire_le", Date, nullable=True),
    # Identité légale (liasse fiscale, FEC) : un bloc lu et écrit d'un seul
    # tenant, jamais requêté champ par champ — JSON plutôt que 15 colonnes.
    Column("identite", JSON, nullable=True),
    Column("pack_metier", String, nullable=False, server_default="vtc"),
    Column("option_ir_debut", Integer, nullable=True),
    Column("relance_consentement", String, nullable=True),
    Column("code_naf", String, nullable=True),
    Column("a_confirmer", JSON, nullable=False, server_default="[]"),
    Column("tva_periodicite", String, nullable=True),
    Column("tva_jour_echeance", Integer, nullable=True),
    # AXE-849 : SIREN (relecture des registres) et écarts non tranchés.
    Column("siren", String, nullable=True),
    Column("ecarts_registre", JSON, nullable=False, server_default="[]"),
    Column("deficits_anterieurs_euros", BigInteger, nullable=False, server_default="0"),
)

# Lectures des registres officiels (INSEE, RNE), append-only (AXE-849).
lectures_registre = Table(
    "lectures_registre",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("siren", String, nullable=False),
    Column("sources", JSON, nullable=False),
    Column("fiche", JSON, nullable=False),
    Column("lu_le", DateTime(timezone=True), nullable=False),
)

# Écarts tranchés : qui, quand, quelle valeur retenue. Append-only (AXE-849).
resolutions_ecart = Table(
    "resolutions_ecart",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("champ", String, nullable=False),
    Column("declare", String, nullable=False),
    Column("officiel", String, nullable=False),
    Column("retenue", String, nullable=False),
    Column("par", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
    CheckConstraint("retenue IN ('declaree', 'officielle')", name="resolutions_ecart_retenue"),
)

# Bilans d'ouverture repris d'un FEC (AXE-804) : un par dossier, ajout seul.
ouvertures_importees = Table(
    "ouvertures_importees",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, unique=True),
    Column("nom_fichier", String, nullable=False),
    Column("empreinte", String, nullable=False),
    Column("cloture", Date, nullable=False),
    Column("ouverture", Date, nullable=False),
    Column("role", String, nullable=False),
    Column("par", String, nullable=False),
    Column("auteur_nom", String, nullable=True),
    Column("motif", String, nullable=True),
    Column("attestation", Text, nullable=False),
    Column("correspondance", JSON, nullable=False),
    Column("deficits_euros", BigInteger, nullable=False),
    Column("ecriture_id", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
)

# Exercices clos, append-only (verrou en base, migration `b8e3f5a1c762`).
exercices_clos = Table(
    "exercices_clos",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id"), primary_key=True),
    Column("debut", Date, primary_key=True),
    Column("fin", Date, nullable=False),
    Column("clos_le", DateTime, nullable=False),
    Column("clos_par", String, nullable=False),
    Column("changements", JSON, nullable=False),
    # Texte exact accepté par le chauffeur en validant la clôture (preuve).
    Column("attestation", Text, nullable=True),
)

# Décisions d'affectation du résultat, append-only (migration `d6a9c4e17b83`) :
# ce que le chauffeur a choisi, quand, et sous quelle identité.
affectations_resultat = Table(
    "affectations_resultat",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id"), primary_key=True),
    Column("annee_exercice", Integer, primary_key=True),
    Column("scenario", String, nullable=False),
    Column("dividendes_cts", Integer, nullable=False),
    Column("reserve_legale_cts", Integer, nullable=False),
    Column("decide_le", DateTime, nullable=False),
    Column("decide_par", String, nullable=False),
)

# Estimations CCA/FNP de l'exercice ouvert (migration `c4e8a1b92d06`).
# Remplaçables : ce n'est pas une écriture validée.
provisions_cloture = Table(
    "provisions_cloture",
    metadata,
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), primary_key=True),
    Column("annee", Integer, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("nature", String, nullable=False),
    Column("compte_charge", String, nullable=False),
    Column("centimes", Integer, nullable=False),
    Column("libelle", String, nullable=False),
)

# Registre des immobilisations (AXE-802), append-only : une fiche ne se
# modifie pas, une cession s'ajoute (migration b3f7d1a9c4e2).
immobilisations = Table(
    "immobilisations",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("designation", String, nullable=False),
    Column("compte", String, nullable=False),
    Column("mise_en_service", Date, nullable=False),
    Column("base_cts", BigInteger, nullable=False),
    Column("duree_mois", Integer, nullable=False),
    Column("ecriture_acquisition", String, nullable=True),
    Column("cree_le", DateTime(timezone=True), nullable=False),
)

cessions_immobilisations = Table(
    "cessions_immobilisations",
    metadata,
    Column("immobilisation_id", String, ForeignKey("immobilisations.id"), primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False),
    Column("le", Date, nullable=False),
    Column("prix_cts", BigInteger, nullable=False),
    Column("cree_le", DateTime(timezone=True), nullable=False),
)

# Contrats de LOA (AXE-803), append-only (migration d8a2c6e4f1b9).
contrats_loa = Table(
    "contrats_loa",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("loueur", String, nullable=False),
    Column("vehicule", String, nullable=False),
    Column("debut", Date, nullable=False),
    Column("duree_mois", Integer, nullable=False),
    Column("loyer_mensuel_cts", BigInteger, nullable=False),
    Column("premier_loyer_cts", BigInteger, nullable=False),
    Column("prix_levee_cts", BigInteger, nullable=False),
    Column("co2_g_km", Integer, nullable=True),
    Column("cree_le", DateTime(timezone=True), nullable=False),
)

# Avenants de régime d'imposition (doc 06 §7), append-only : verrou en base
# contre UPDATE et DELETE (migration `a4d7e2c9b518`).
avenants_regime = Table(
    "avenants_regime",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("exercice_effet", Integer, nullable=False),
    Column("regime_imposition", String, nullable=False),
    Column("option_ir_debut", Integer, nullable=True),
    Column("motif", String, nullable=False),
    Column("enregistre_le", DateTime, nullable=False),
    Column("enregistre_par", String, nullable=False),
)

regles_rappel = Table(
    "regles_rappel",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("libelle", String, nullable=False),
    Column("message", String, nullable=False),
    # Canaux prévus : sms, mail, appel. L'envoi réel vient plus tard.
    Column("canaux", JSON, nullable=False),
    # tous : chaque entreprise. selection : seulement dossier_ids.
    Column("portee", String, nullable=False, server_default="tous"),
    Column("dossier_ids", JSON, nullable=True),
    # manuel : bouton sur la fiche. avant_cloture : part seul N jours avant la fin.
    Column("declencheur", String, nullable=False, server_default="manuel"),
    Column("jours_avant", Integer, nullable=True),
    Column("actif", Boolean, nullable=False, server_default=true()),
    UniqueConstraint("tenant_id", "libelle", name="uq_regles_rappel_tenant_libelle"),
)

rappels = Table(
    "rappels",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=True),
    Column("regle_id", String, ForeignKey("regles_rappel.id"), nullable=True),
    Column("message", String, nullable=False),
    Column("canal", String, nullable=False),
    Column("cree_le", DateTime, nullable=False),
)

droits_membre = Table(
    "droits_membre",
    metadata,
    Column("tenant_id", String, ForeignKey("tenants.id"), primary_key=True),
    Column("email", String, primary_key=True),
    # admin : nom, équipe, retraits, règles. membre : invitations et envois.
    # lecture : consultation seule.
    Column("role", String, nullable=False),
)

# Ce qui arrive au portefeuille, pas à un dossier (AXE-812, migration
# `b8e4c2d7a613`) : connexions, réinitialisation de la double
# authentification d'un membre. Ajout seul (trigger).
journal_portefeuille = Table(
    "journal_portefeuille",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("type_acte", String, nullable=False),
    Column("reference", String, nullable=False),
    Column("acteur", String, nullable=False),
    Column("acte_le", DateTime(timezone=True), nullable=False),
)

# Agrégats de la vue portefeuille (AXE-566, migration `e7b3d9a15c42`). Périmés
# par des triggers Postgres à chaque écriture qui les concerne : `version`
# monte, `a_jour` retombe. Voir `tenants/agregats.py`.
agregats_dossier = Table(
    "agregats_dossier",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id", ondelete="CASCADE"), primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("version", Integer, nullable=False, server_default="0"),
    Column("a_jour", Boolean, nullable=False, server_default=false()),
    Column("version_calcul", Integer, nullable=True),
    Column("ca_ht_cts", BigInteger, nullable=False, server_default="0"),
    Column("charges_cts", BigInteger, nullable=False, server_default="0"),
    Column("resultat_cts", BigInteger, nullable=False, server_default="0"),
    Column("exercice_debut", Date, nullable=True),
    Column("exercice_fin", Date, nullable=True),
    Column("alerte_tva", Text, nullable=True),
    Column("calcule_le", DateTime(timezone=True), nullable=True),
)

# Tags d'un portefeuille (AXE-829). Les tags proposés y sont créés au besoin.
tags = Table(
    "tags",
    metadata,
    Column("tenant_id", String, ForeignKey("tenants.id"), primary_key=True),
    Column("nom", String, primary_key=True),
    Column("description", String, nullable=False),
    Column("cree_le", DateTime(timezone=True), nullable=False),
)

# Pose et retrait de tags, append-only : l'état d'un tag sur un dossier est
# le dernier événement. L'historique est la trace (qui, quoi, quand).
evenements_tags = Table(
    "evenements_tags",
    metadata,
    Column("id", String, primary_key=True),
    # Ordre d'insertion : à date égale, le dernier inséré fait foi.
    Column("rang", BigInteger, Identity(), nullable=False),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("tag", String, nullable=False),
    Column("pose", Boolean, nullable=False),  # True : posé ; False : retiré
    Column("par", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["tenant_id", "tag"], ["tags.tenant_id", "tags.nom"]),
)

# Réglages d'exclusion, append-only : le dernier par traitement fait foi.
reglages_exclusion = Table(
    "reglages_exclusion",
    metadata,
    Column("id", String, primary_key=True),
    Column("rang", BigInteger, Identity(), nullable=False),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("traitement", String, nullable=False),
    Column("tags", JSON, nullable=False),
    Column("par", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
)

# Contacts Digifactory sans dossier, proposés au gestionnaire (AXE-845).
# Réécrits à chaque détection par le worker (rôle propriétaire).
contacts_proposes = Table(
    "contacts_proposes",
    metadata,
    Column("tenant_id", String, ForeignKey("tenants.id"), primary_key=True),
    Column("contact_nr", String, primary_key=True),
    Column("nom", String, nullable=False),
    Column("siren", String, nullable=True),
    Column("forme", String, nullable=True),
    Column("exercice_debut", Date, nullable=True),
    Column("code_naf", String, nullable=True),
    Column("avertissements", JSON, nullable=False),
    Column("cessee", Boolean, nullable=False),
    Column("detecte_le", DateTime(timezone=True), nullable=False),
)

# Décisions du gestionnaire sur ces contacts, append-only : la dernière fait foi.
decisions_contacts = Table(
    "decisions_contacts",
    metadata,
    Column("id", String, primary_key=True),
    Column("rang", BigInteger, Identity(), nullable=False),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("contact_nr", String, nullable=False),
    Column("decision", String, nullable=False),
    Column("par", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
)

# AXE-872 : les intégrations du portefeuille, plusieurs par type (SMTP, SMS,
# Digifactory…). Remplace `integrations_envoi`, qui n'en gardait qu'une par
# canal. Paramètres chiffrés (`core.chiffrement`), jamais relus à l'écran.
branchements = Table(
    "branchements",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("type", String, nullable=False),  # mail | sms | digifactory
    Column("fournisseur", String, nullable=False),  # smtp | http | digifactory
    Column("nom", String, nullable=False),
    Column("parametres_chiffres", String, nullable=False),
    Column("par_defaut", Boolean, nullable=False),
    Column("actif", Boolean, nullable=False),
    Column("maj_par", String, nullable=False),
    Column("maj_le", DateTime(timezone=True), nullable=False),
    UniqueConstraint("tenant_id", "type", "nom", name="uq_branchements_nom"),
)
# Un seul défaut par type et par portefeuille.
Index(
    "uq_branchements_defaut",
    branchements.c.tenant_id,
    branchements.c.type,
    unique=True,
    postgresql_where=text("par_defaut"),
)

# Le branchement qu'un dossier utilise pour un type, quand ce n'est pas
# celui par défaut. Pas de ligne : le défaut.
branchements_dossier = Table(
    "branchements_dossier",
    metadata,
    Column("dossier_id", String, ForeignKey("dossiers.id"), primary_key=True),
    Column("type", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("branchement_id", String, ForeignKey("branchements.id"), nullable=False),
)
