"""Mapping SQLAlchemy Core de `Tenant` et `Dossier` (doc 03 §3bis). Un seul
schéma (doc 17 §3) : l'isolation par `tenant_id` se fait dans les requêtes du
repository (`DossierRepository.lister_par_tenant`) ; la RLS Postgres de la V1
(doc 03 §7) reste à faire.
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text

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
