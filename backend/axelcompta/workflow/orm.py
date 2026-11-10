"""Mapping SQLAlchemy Core de `DecisionHumaine`/`AnnotationDev` (doc 17 §9
bloc A). Défini séparément de `decisions.py` : le domaine reste pur (doc 08
§2.1), seul `decisions_postgres.py` fait de l'I/O contre ces tables.

Append-only par construction : ni l'une ni l'autre table n'a de colonne
mise à jour en place, `enregistrer_decision`/`enregistrer_annotation` ne
font que des `INSERT` (doc 06 §1, même logique que `ledger/orm.py`).

**Pas de `ForeignKey` vers `dossiers`/`ecritures`, contrairement à
`ledger/orm.py`, jusqu'au 2026-09-22** : à l'origine (2026-09-07),
dossiers et écritures étaient recalculés en mémoire et jamais écrits, donc
une FK aurait fait échouer tout `INSERT`. Ces tables sont peuplées depuis le
2026-09-21 (`demo_seed`, synchro Digifactory) et les FK sont posées (migration
`7cd5053e8209`) : décisions et annotations vers `dossiers` et `ecritures`,
propositions vers `dossiers` seulement (voir le commentaire de la table).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    String,
    Table,
)

from axelcompta.core.db import metadata

decisions_humaines = Table(
    "decisions_humaines",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("ecriture_id", String, ForeignKey("ecritures.id"), nullable=False),
    Column("categorie", String, nullable=False),
    Column("etage_origine", String, nullable=False),
    Column("confiance_origine", Float, nullable=False),
    Column("decide_par", String, nullable=False),
    Column("decide_le", DateTime, nullable=False),
)

annotations_dev = Table(
    "annotations_dev",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False),
    Column("ecriture_id", String, ForeignKey("ecritures.id"), nullable=False),
    Column("juste", Boolean, nullable=False),
    Column("note", String, nullable=False),
    Column("annote_par", String, nullable=False),
    Column("annote_le", DateTime, nullable=False),
)

# Ce que le pipeline avait proposé pour chaque écriture catégorisée
# automatiquement. Nécessaire à la file de revue : une `DecisionHumaine`
# garde `etage_origine`/`confiance_origine` (doc 07 §3.1), or ces valeurs
# ne se retrouvent plus une fois le ledger persisté au lieu d'être
# recalculé à chaque requête. Une seule ligne par écriture, jamais mise à
# jour (la proposition d'origine ne change pas après coup).
propositions_categorisation = Table(
    "propositions_categorisation",
    metadata,
    # Pas de FK sur `ecriture_id`, volontairement : la synchro écrit la
    # proposition AVANT l'écriture (une proposition orpheline est sans effet,
    # une écriture à trancher sans proposition casserait la file de revue).
    Column("ecriture_id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("categorie", String, nullable=False),
    Column("etage", String, nullable=False),
    Column("confiance", Float, nullable=False),
    # Carte, virement, prélèvement… (AXE-836, migration d1e7a3c9f264).
    Column("moyen_paiement", String, nullable=True),
)

# Notifications internes de l'indiv (cloche de l'espace chauffeur). On
# retient quelles écritures étaient déjà signalées, pour ne notifier à
# nouveau que s'il y en a de nouvelles (ou en rappel après un délai). Ni
# montant ni libellé ici (minimisation, doc 10) : le message se recompose
# depuis le nombre d'écritures. `lue_le` est la seule colonne modifiable.
notifications_envoyees = Table(
    "notifications_envoyees",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("type", String, nullable=False),
    Column("envoye_le", DateTime, nullable=False),
    Column("ecriture_ids", JSON, nullable=False),
    Column("lue_le", DateTime, nullable=True),
)

# Preuve de signature, append-only : un INSERT par signature, jamais de
# mise à jour. Isolation par `dossier_id` (policy RLS), comme les décisions.
documents_signes = Table(
    "documents_signes",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("type_document", String, nullable=False),
    Column("contenu_pdf", LargeBinary, nullable=False),
    Column("signataire", String, nullable=False),
    Column("signe_le", DateTime(timezone=True), nullable=False),
    Column("provider", String, nullable=False),
    Column("qualifie", Boolean, nullable=False),
)

# Piste des actes déjà persistés (décision, signature). Append-only :
# le détail métier reste dans sa table, ici seulement qui a fait quoi.
journal_audit = Table(
    "journal_audit",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("type_acte", String, nullable=False),
    Column("reference", String, nullable=False),
    Column("acteur", String, nullable=False),
    Column("acte_le", DateTime(timezone=True), nullable=False),
)

# Verdicts « juste » / « faux » sur un classement (AXE-823), sans écriture.
# Append-only : le dernier par écriture fait foi.
verdicts_classement = Table(
    "verdicts_classement",
    metadata,
    Column("id", String, primary_key=True),
    Column("rang", BigInteger, Identity(), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("ecriture_id", String, nullable=False),
    Column("verdict", String, nullable=False),
    Column("par", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
)

# Sujets de la file expert gardés par dossier (AXE-824). Valables tant que
# `version_source` égale `agregats_dossier.version` du dossier.
file_expert_dossier = Table(
    "file_expert_dossier",
    metadata,
    Column(
        "dossier_id",
        String,
        ForeignKey("dossiers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("version_source", Integer, nullable=False),
    Column("version_calcul", Integer, nullable=False),
    Column("sujets", JSON, nullable=False),
    Column("calcule_le", DateTime(timezone=True), nullable=False),
)

# Opérations déjà classées gardées par dossier (AXE-824). Même version que
# `agregats_dossier`. Le verdict « juste » / « faux » n'y est pas : il change
# sans écriture et se pose à la lecture.
classees_dossier = Table(
    "classees_dossier",
    metadata,
    Column(
        "dossier_id",
        String,
        ForeignKey("dossiers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("version_source", Integer, nullable=False),
    Column("version_calcul", Integer, nullable=False),
    Column("operations", JSON, nullable=False),
    Column("calcule_le", DateTime(timezone=True), nullable=False),
)

# Résolution d'une entrée de quarantaine d'ingestion (AXE-424) : une seule
# par entrée (unicité), jamais modifiée.
resolutions_quarantaine = Table(
    "resolutions_quarantaine",
    metadata,
    Column("id", String, primary_key=True),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("entree_id", String, nullable=False, unique=True),
    Column("decision", String, nullable=False),
    Column("ecritures", JSON, nullable=False),
    Column("par", String, nullable=False),
    Column("le", DateTime(timezone=True), nullable=False),
)

# AXE-800 (migration `c9f3a1e6d248`) : l'expert-comptable prend la charge
# juridique de ses changements. Trois tables en ajout seul (trigger) : la
# plus récente habilitation et le plus récent engagement font foi.
habilitations_expert = Table(
    "habilitations_expert",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("email", String, nullable=False),
    Column("nom", String, nullable=False),
    Column("cabinet", String, nullable=False),
    Column("numero_ordre", String, nullable=False),
    Column("lettre_mission", String, nullable=False),
    Column("date_lettre", Date, nullable=False),
    Column("dossiers", JSON, nullable=False),  # identifiants des dossiers couverts
    Column("accordee_par", String, nullable=False),
    Column("accordee_le", DateTime(timezone=True), nullable=False),
)

engagements_expert = Table(
    "engagements_expert",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False, index=True),
    Column("email", String, nullable=False),
    Column("version", String, nullable=False),
    Column("texte", String, nullable=False),  # mot pour mot
    Column("adresse", String, nullable=False),
    Column("acteur", String, nullable=False),
    Column("accepte_le", DateTime(timezone=True), nullable=False),
)

decisions_expert = Table(
    "decisions_expert",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, ForeignKey("tenants.id"), nullable=False),
    Column("dossier_id", String, ForeignKey("dossiers.id"), nullable=False, index=True),
    Column("ecriture_id", String, nullable=True),
    Column("nature", String, nullable=False),
    Column("motif", String, nullable=False),
    Column("auteur", String, nullable=False),
    Column("auteur_nom", String, nullable=False),
    Column("version_engagement", String, nullable=False),
    Column("decide_le", DateTime(timezone=True), nullable=False),
    Column("ecritures", JSON, nullable=False),  # écrites avec la décision (I6)
)
