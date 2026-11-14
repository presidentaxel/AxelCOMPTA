"""Routes HTTP du produit (doc 17 §9, doc 19).

`axelcompta.api.app` est le point d'entrée HTTP : il délègue ici tant que
les routes n'ont pas chacune leur façade (AXE-428). Ceci reste une
composition root (doc 18), pas un module métier — elle peut importer
les modules directement, y compris une autre composition root.

**Bloc A/C (doc 17 §9) : la file de revue est maintenant réelle.**
`POST /dossiers/{id}/transactions/{ecriture_id}/decision` accepte/reclasse
une écriture « à trancher » — la décision est persistée pour de vrai
(`workflow.decisions_postgres`, doc 17 §9 bloc A), pas juste un changement
d'état côté React. Requiert donc `DATABASE_URL` et un Postgres démarré
(`docker compose up -d db` puis `alembic upgrade head` depuis `backend/`)
— **changement par rapport à avant** : la démo n'était jusqu'ici pas
censée avoir besoin d'infra pour tourner.

**Depuis le 2026-09-21, tout est lu en Postgres** : dossiers et tenants
(`tenants/`), ledger (`PostgresLedgerService`), propositions d'origine du
pipeline (`workflow/propositions*`). Rien n'est recalculé à la volée. Les
décisions humaines restent une couche append-only réappliquée par-dessus le
ledger persisté (`_ledger_avec_decisions`). Les dossiers viennent de
Digifactory (`scripts/ajouter_chauffeurs_digifactory.py`) ; le portefeuille visible d'un
gestionnaire est celui de son `tenant_id` (jeton), pas une constante.

Usage : `uvicorn axelcompta.api.app:app --reload --port 8000` depuis
backend/ (nécessite `pip install -e ".[dev]"` pour uvicorn). `api.app`
délègue à `create_app` ci-dessous : les routes sont encore ici.
"""

from __future__ import annotations

import asyncio
import dataclasses
import functools
import json
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol, cast

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine, Row
from sqlalchemy.exc import IntegrityError

from axelcompta.affectations import (
    AffectationImpossible,
    DividendesDecides,
    PropositionAffectation,
    bulletins_enregistres,
    decider,
    declarer_versement,
    dividendes_decides,
    enregistrer_bulletin,
    proposer,
)
from axelcompta.anomaly.detecteurs import CATEGORIE_CARBURANT
from axelcompta.anomaly.instruction import InstructionsRepository
from axelcompta.anomaly.instruction_postgres import PostgresInstructions
from axelcompta.anomaly.models import Alerte, MouvementSurveille
from axelcompta.anomaly.service import analyser
from axelcompta.api.auth import (
    IdentiteAuthentifiee,
    identite_chauffeur_optionnelle,
    identite_tolerante,
)
from axelcompta.api.erreurs import brancher_erreurs
from axelcompta.categorize.appris import (
    OperationTranchee,
    PropositionApprise,
    libelle_sans_categorie,
    propositions_apprises,
)
from axelcompta.categorize.llm import VERSION_PROMPT, cle_libelle
from axelcompta.categorize.ml_fallback import (
    charger_calibration,
    repli_sans_modele_permis,
)
from axelcompta.categorize.modele_requis import EtatCategorisation, signaler
from axelcompta.categorize.modele_requis import charger as charger_modele_et_etat
from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.rules_and_ml import (
    CATEGORIE_PAR_DEFAUT,
    CATEGORIE_RETRAIT_ESPECES,
    RulesAndMlPipeline,
)
from axelcompta.closing.affectation import (
    MillesimeDividendesInconnu,
    disponible,
    distribuable,
    fiscalite,
)
from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.cloture_fiscale import chiffre_affaires_ht
from axelcompta.closing.dividendes import RetenuesDividendes, retenues
from axelcompta.closing.immobilisations import (
    DUREE_PAR_DEFAUT,
    DUREES_PROPOSEES,
    Cession,
    Immobilisation,
    ImmobilisationInvalide,
    dotation,
    plus_ou_moins_value,
    valeur_nette,
    valider,
)
from axelcompta.closing.loa import (
    ContratLoa,
    cca,
    charge_premier_loyer,
    engagement_restant,
    terme,
)
from axelcompta.closing.loa import valider as valider_contrat_loa
from axelcompta.closing.models import (
    SANS_SAISIE,
    LiassePivot,
    ParametresCloture,
    ProvisionCloture,
    SaisiesCloture,
)
from axelcompta.closing.ouverture import id_a_nouveaux
from axelcompta.closing.ouverture_depot import (
    ROLE_DIRIGEANT,
    OuvertureDejaFaite,
    OuvertureImportee,
    OuverturesPostgres,
    OuverturesRepository,
)
from axelcompta.closing.ouverture_fec import Analyse, FecRefuse
from axelcompta.closing.ouverture_fec import analyser as analyser_fec
from axelcompta.closing.paie import Bulletin
from axelcompta.closing.provisions import valider_provision
from axelcompta.closing.tva_periodique import (
    EtatPeriode,
    echeance,
    ecriture_liquidation,
    etats_tva,
    periodes_du_dossier,
    prochaine_a_declarer,
    type_preuve,
    verifier_parametres,
)
from axelcompta.comptes import (
    CompteRepository,
    InvitationAbsente,
    InvitationFermee,
    StatutInvitation,
    SupabaseCompteRepository,
    SupabaseConfig,
)
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.identite import Adresse, Associe, IdentiteEntreprise
from axelcompta.core.ids import DossierId, EcritureId, TenantId, TransactionId, UserId
from axelcompta.core.libelles import categorie_du_suffixe, sans_categorie
from axelcompta.core.pcg import COMPTE_BANQUE, est_compte_banque
from axelcompta.core.rls import appliquer_rls, contexte_identite
from axelcompta.documents.justificatifs import JustificatifRepository
from axelcompta.documents.postgres import PostgresJustificatifRepository
from axelcompta.exercices import (
    PassageExercice,
    PassageRefuse,
    attestation,
    executer_passage,
    preparer_passage,
)
from axelcompta.filings.cerfa_2031 import PdfCerfa2031Renderer
from axelcompta.filings.cerfa_2033 import extraire_page_2033
from axelcompta.filings.cerfa_2065 import PdfCerfa2065Renderer
from axelcompta.filings.export_comptable import exporter_balance, exporter_grand_livre
from axelcompta.filings.fec import exporter_fec, libelle_compte, nom_fichier_fec
from axelcompta.filings.inpi_depot import GuideGreffe, PdfDepotInpiRenderer, guide_greffe
from axelcompta.filings.liasse_fiscale import PdfLiasseFiscaleRenderer
from axelcompta.filings.liasse_simplifiee import PdfLiasseSimplifieeRenderer
from axelcompta.filings.pdf_export_comptable import rendre_balance_pdf, rendre_grand_livre_pdf
from axelcompta.ingestion.annuaire_rollee import AnnuaireRollee, chercher
from axelcompta.ingestion.annuaire_rollee_postgres import PostgresAnnuaireRollee
from axelcompta.ingestion.comptes_bancaires import (
    CompteBancaire,
    CompteBancaireRepository,
    CompteDejaComptabilise,
    CompteInconnu,
    ComptesAChoisir,
    nombre_a_choisir,
    verifier_ecartable,
)
from axelcompta.ingestion.comptes_bancaires_postgres import PostgresCompteBancaireRepository
from axelcompta.ingestion.comptes_rollee import CompteRelie, synthese
from axelcompta.ingestion.comptes_rollee_postgres import PostgresComptesRollee
from axelcompta.ingestion.consentement import ReleveConsentement, SanteConnexion, classer
from axelcompta.ingestion.consentement_postgres import PostgresConsentementRepository
from axelcompta.ingestion.journal import EntreeQuarantaine, JournalIngestion
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.ingestion.liens_rollee import Lien, LienDejaPris, LiensRollee, lien_manuel
from axelcompta.ingestion.liens_rollee_postgres import PostgresLiensRollee
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ingestion.providers.digifactory import normaliser_payload
from axelcompta.ingestion.settlements_plateforme import (
    SettlementsRepository,
    SettlementStocke,
    a_verifier,
)
from axelcompta.ingestion.settlements_plateforme_postgres import PostgresSettlements
from axelcompta.jobs.file import (
    TYPE_IMPORT_DOSSIERS,
    TYPE_RAPPELS,
    TYPE_RAPPROCHEMENT_ROLLEE,
    TYPE_SYNCHRO,
    DemandesDeJobs,
    Job,
)
from axelcompta.jobs.postgres import FilePostgres
from axelcompta.ledger.banque import (
    comptes_hors_banque,
    est_reclassement_bancaire,
    ligne_banque,
    montant_bancaire,
)
from axelcompta.ledger.contrepassation import annulees, contrepasser
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.nouveaux_contacts import fiche_sirene, recherche_entreprises
from axelcompta.packs.vtc_demo import (
    charger_categories_banque,
    charger_compte_par_categorie,
    charger_plateformes,
    charger_regles,
    plancher_de,
)
from axelcompta.plateformes_rollee import (
    DepotReception,
    ReceptionPostgres,
    RolleeNonBranche,
    ServicesRollee,
    ouvrir_session,
    recevoir,
    relire_comptes,
)
from axelcompta.revenus_rollee import delier_revenus
from axelcompta.tenants.affectations import AffectationRepository
from axelcompta.tenants.affectations_postgres import PostgresAffectationRepository
from axelcompta.tenants.agregats import AgregatsRepository, AgregatStocke, LigneAgregat
from axelcompta.tenants.agregats_postgres import PostgresAgregatsRepository
from axelcompta.tenants.avenants import (
    AvenantRegime,
    AvenantRegimeRepository,
    MotifAvenant,
    a_venir,
    alerte_option_ir,
)
from axelcompta.tenants.avenants_postgres import PostgresAvenantRegimeRepository
from axelcompta.tenants.branchements import (
    Branchement,
    BranchementIntrouvable,
    BranchementsRepository,
    Modification,
    garder_parametre,
    lecture_publique,
    modifier,
    nouveau,
    types_branches,
    verifier_choix,
)
from axelcompta.tenants.branchements_postgres import PostgresBranchements
from axelcompta.tenants.confirmation import (
    ConfirmationRefusee,
    confirmer,
    formes_proposees,
    identite_manquante,
    raison_ambiguite,
)
from axelcompta.tenants.contacts_proposes import ContactsProposesRepository
from axelcompta.tenants.contacts_proposes_postgres import PostgresContactsProposes
from axelcompta.tenants.exercices import ExerciceRepository
from axelcompta.tenants.exercices_postgres import PostgresExerciceRepository
from axelcompta.tenants.franchise_tva import MillesimeInconnu, suivre_franchise
from axelcompta.tenants.identite_json import identite_vers_json
from axelcompta.tenants.identite_saisie import (
    FORMES_UNIPERSONNELLES,
    IdentiteInvalide,
    PersonneConnue,
    completer_pre_remplissage,
    pre_remplissage,
    qualite_par_defaut,
    verifier_identite,
)
from axelcompta.tenants.import_dossiers import MODELE_CSV, lire_csv, siren_valide
from axelcompta.tenants.import_dossiers import rapport as rapport_import
from axelcompta.tenants.journal_portefeuille import (
    ACTE_CONNEXION_MEMBRE,
    ACTE_MFA_REINITIALISEE,
    JournalPortefeuille,
)
from axelcompta.tenants.journal_portefeuille_postgres import PostgresJournalPortefeuille
from axelcompta.tenants.models import MODES_RELANCE, Dossier, Tenant
from axelcompta.tenants.orm import droits_membre, rappels, regles_rappel
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.provisions_cloture import ProvisionsClotureRepository
from axelcompta.tenants.provisions_cloture_postgres import PostgresProvisionsClotureRepository
from axelcompta.tenants.registres import FicheOfficielle, phrase, phrase_gestionnaire, trancher
from axelcompta.tenants.registres_depot import (
    RegistresPostgres,
    RegistresRepository,
    ResolutionEcart,
)
from axelcompta.tenants.repository import DossierRepository
from axelcompta.tenants.statuts import (
    ColonneMatrice,
    FormeJuridique,
    RegimeTva,
    charger_matrice,
    configuration_de,
)
from axelcompta.tenants.tags import (
    TRAITEMENTS,
    EtatTags,
    Tag,
    TagsRepository,
    etat_du_portefeuille,
    nom_de_tag,
)
from axelcompta.tenants.tags_postgres import PostgresTagsRepository
from axelcompta.tester_branchement import tester as tester_branchement
from axelcompta.webhooks_rollee import preparer as preparer_webhook
from axelcompta.workflow.audit import ACTE_CONNEXION, ACTE_EXPORT
from axelcompta.workflow.avis_etages import avis_etages, proposition_affichee
from axelcompta.workflow.budget_llm import debut_du_mois, libelles_du_mois, llm_actif
from axelcompta.workflow.classees import (
    Filtres,
    OperationClassee,
    Statut,
    compter,
    trier,
)
from axelcompta.workflow.classees import classer as classer_operations
from axelcompta.workflow.classees_cache import VERSION_CLASSEES
from axelcompta.workflow.consultations import JournalConsultations, PostgresJournalConsultations
from axelcompta.workflow.decisions import (
    CATEGORIE_A_PRECISER,
    CATEGORIE_ANNULATION,
    ContexteDecision,
    DecisionHumaine,
    DecisionRepository,
    decision_en_vigueur,
    nature_decision,
)
from axelcompta.workflow.decisions_et_reclassements import (
    EcrireDecisions,
    EnSequence,
    PostgresDecisionsEtReclassements,
)
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.expert import preparer_imputation
from axelcompta.workflow.expert_comptable import (
    ROLE_EXPERT,
    TEXTE_ENGAGEMENT,
    VERSION_ENGAGEMENT,
    DecisionExpert,
    Engagement,
    ExpertActif,
    ExpertRepository,
    Habilitation,
    exiger_dossier,
    expert_actif,
    motif_valide,
    verifier_engagement,
)
from axelcompta.workflow.expert_comptable_postgres import PostgresExpertRepository
from axelcompta.workflow.file_expert_cache import CacheFileExpert, SujetsGardes
from axelcompta.workflow.file_expert_cache_postgres import (
    PostgresCacheFileExpert,
    cache_operations_classees,
)
from axelcompta.workflow.jalons import JALONS_EXERCICE, etape_depuis_preuves
from axelcompta.workflow.journal_acces import (
    ACTES_VISIBLES_DU_DIRIGEANT,
    JournalAcces,
    PostgresJournalAcces,
)
from axelcompta.workflow.lots_llm import LotsLlm, LotsLlmMemoire
from axelcompta.workflow.lots_llm_postgres import PostgresLotsLlm
from axelcompta.workflow.notifications import (
    NotificationRepository,
    ecritures_a_trancher,
    pour_la_cloche,
)
from axelcompta.workflow.notifications_postgres import PostgresNotificationRepository
from axelcompta.workflow.propositions import PropositionRepository
from axelcompta.workflow.propositions_ia import PropositionIa, PropositionsIa
from axelcompta.workflow.propositions_ia_postgres import PostgresPropositionsIa
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.quarantaine import (
    LIBELLES_MOTIF,
    ResolutionRefusee,
    ecritures_de_resolution,
    famille_du_motif,
)
from axelcompta.workflow.rappels_auto import DECLENCHEURS_AUTO
from axelcompta.workflow.rappels_envoi import (
    EnvoisRepository,
    desinscription_valide,
    envois_du_rappel,
)
from axelcompta.workflow.rappels_envoi_postgres import PostgresEnvois
from axelcompta.workflow.reclassement import (
    annulations_liees,
    annuler_reclassements,
    grand_livre_comptable,
    grand_livre_tranche,
    reclasser,
)
from axelcompta.workflow.relances_consentement import mode_effectif
from axelcompta.workflow.resolutions_quarantaine import Resolution, ResolutionsRepository
from axelcompta.workflow.resolutions_quarantaine_postgres import PostgresResolutions
from axelcompta.workflow.revue import CATEGORIE_USAGE_PERSONNEL, resoudre_ecriture_a_trancher
from axelcompta.workflow.signature import DocumentSigne, SignatureRepository
from axelcompta.workflow.signature_demo import SignatureDemoProvider
from axelcompta.workflow.signature_postgres import PostgresSignatureRepository
from axelcompta.workflow.synchro import id_ecriture
from axelcompta.workflow.tva_imputation import tva_affichee
from axelcompta.workflow.verdicts import VerdictsRepository
from axelcompta.workflow.verdicts_postgres import PostgresVerdicts

_TYPES_IMAGE_ACCEPTES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")
_EXTENSIONS_IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

COMPTE_ATTENTE = "471"  # doc 06 §2 : compte d'attente par défaut, "à trancher"
TYPE_DOCUMENT_CLOTURE = "cloture"  # jalon d'exercice : la validation chauffeur n'apparaît qu'après
TYPE_DOCUMENT_GREFFE_INPI = "greffe_inpi"  # doc 20 : dépôt des comptes annuels
ORIGINE_FRONTEND_DEV = "http://localhost:3000"
# **Retiré le 2026-09-11 (doc 19 §8bis)** : `UTILISATEUR_DEMO` (stub pour
# le cas « gestionnaire sans login » sur les routes de tranchage/signature)
# n'a plus de raison d'être — ces routes exigent désormais un vrai jeton
# indiv (`_verifier_acces_dossier`), la révision structurante du même jour
# ayant retiré au gestionnaire tout accès à ces actions (doc 19 §2.1/§2.4).


class LignePortailVue(BaseModel):
    question: str
    reponse: str
    detail: str


class PieceGreffeVue(BaseModel):
    nom: str
    detail: str
    document: str | None


class GuideGreffeVue(BaseModel):
    """Réponses à reporter sur le portail INPI, et pièces au nom du guichet."""

    depose: bool
    lien: str
    lignes: list[LignePortailVue]
    pieces: list[PieceGreffeVue]


def _guide_vue(guide: GuideGreffe) -> GuideGreffeVue:
    return GuideGreffeVue(
        depose=guide.depose,
        lien=guide.lien,
        lignes=[
            LignePortailVue(question=ligne.question, reponse=ligne.reponse, detail=ligne.detail)
            for ligne in guide.lignes
        ],
        pieces=[
            PieceGreffeVue(nom=piece.nom, detail=piece.detail, document=piece.document)
            for piece in guide.pieces
        ],
    )


class RegimeAVenirVue(BaseModel):
    exercice: int
    regime: str  # libellé de la colonne de la matrice
    motif: str


class ActiviteLlmVue(BaseModel):
    """AXE-887 : volume du mois dans Intégrations. Jamais le coût."""

    libelles: int


class CategorisationVue(BaseModel):
    modele_charge: bool
    raison: str | None
    llm: ActiviteLlmVue | None = None


class DossierResume(BaseModel):
    dossier_id: str
    nom: str
    tva_recettes_regime: str
    plateformes: list[str]
    exercice_debut: str | None
    exercice_fin: str | None
    ca_ht_cts: int
    charges_cts: int
    resultat_cts: int
    tresorerie_cts: int
    tva_a_payer_cts: int
    nb_transactions: int
    nb_a_trancher: int
    statut_invitation: str | None  # None = "non_invité" (doc 19 §3.2) ; sinon "invité" | "actif"
    mode_acces_bancaire: str  # "gestionnaire" | "chauffeur_direct" (doc 19 §4)
    # Faux dès qu'un contact Digifactory est posé, même en chauffeur_direct.
    peut_connecter_sa_banque: bool
    # Preuve `cloture` enregistrée. Tant qu'elle manque, pas de validation de liasse.
    cloture_faite: bool
    greffe_inpi_signe: (
        bool  # doc 20 : dossier de dépôt des comptes annuels signé (démo, pas qualifié)
    )
    guide_greffe: GuideGreffeVue
    # Lus dans la matrice statut × régime (doc 06 §7) : l'écran n'a pas à
    # déduire lui-même le formulaire ou le dépôt de la forme juridique.
    declaration_resultat: str  # "2065" (IS) ou "2031" (IR)
    depot_greffe: bool
    # Approche du terme de l'option IR (N-1, N) et avenants de régime qui
    # prendront effet après l'exercice en cours (doc 06 §7).
    alerte_regime: str | None = None
    regimes_a_venir: list[RegimeAVenirVue] = []
    # Franchise en base : approche ou dépassement des seuils de l'année civile.
    alerte_tva: str | None = None
    # Président assimilé salarié : sa paie se saisit depuis son bulletin.
    paie_par_bulletin: bool = False
    # Forme et régime lus sur le dossier (SAS, SARL…) : l'écran chauffeur
    # n'a pas à les deviner, le portefeuille gestionnaire les avait déjà.
    forme_juridique: str
    regime_libelle: str


class DossierAgregat(BaseModel):
    """Ce que le gestionnaire voit d'un dossier (doc 19 §2.1) : agrégats et
    onboarding, rien de dérivé du détail (doc 19 §2.4). Volontairement un
    modèle distinct de `DossierResume` plutôt qu'un filtre a posteriori : un
    champ ajouté plus tard à `DossierResume` ne fuit pas vers le gestionnaire
    par inadvertance."""

    dossier_id: str
    nom: str
    tva_recettes_regime: str
    plateformes: list[str]
    exercice_debut: str | None
    exercice_fin: str | None
    ca_ht_cts: int
    charges_cts: int
    resultat_cts: int
    statut_invitation: str | None
    mode_acces_bancaire: str
    forme_juridique: str
    regime_imposition: str
    regime_tva: str
    # Étape grossière de l'année (doc 19 §5), sans le détail des écritures.
    annee_courante: int
    etape_courante: str
    annee_precedente: int
    etape_precedente: str
    # Approche du terme de l'option IR (doc 06 §7) : une information de
    # régime, pas un détail comptable (doc 19 §2.4).
    alerte_regime: str | None = None
    alerte_tva: str | None = None
    # AXE-829 : tags du dossier ; `exclu_compteurs` le sort des compteurs et
    # filtres d'Entreprises (il reste listé, grisé).
    tags: list[str] = []
    exclu_compteurs: bool = False
    # Configuration proposée sans certitude (AXE-834) : « forme_juridique »,
    # « exercice ». Une information de configuration, pas un détail comptable.
    a_confirmer: list[str] = []
    # AXE-849 : écarts non tranchés avec les registres officiels, en phrases.
    ecarts_registre: list[str] = []
    # AXE-851 : comptes bancaires qui attendent le choix du dirigeant. Leurs
    # opérations sont écartées par la synchro tant qu'il n'a pas choisi. Des
    # nombres et une date, jamais les comptes ni les opérations (doc 19 §2.4).
    comptes_a_choisir: int = 0
    comptes_a_choisir_depuis: str | None = None
    operations_en_attente_de_choix: int = 0

    # AXE-805 : la plus ancienne période de TVA terminée et pas déclarée
    # (« 2026-10 »), et son échéance. Pas de montant (doc 19 §2.4).
    tva_a_declarer: str | None = None
    tva_echeance: str | None = None


class DossierDeTestVue(BaseModel):
    """Une ligne de l'écran « Quel dossier ? » du compte de test (AXE-822)."""

    dossier_id: str
    nom: str
    forme_juridique: str
    nb_operations: int


class AlerteAnomalieVue(BaseModel):
    id: str
    code: str
    libelle_ui: str
    detail: str
    etat: str
    libelle_mouvement: str
    montant_centimes: int
    date: str
    moyen_paiement: str | None = None  # carte, virement, prélèvement… (AXE-836)


class EvenementAnomalieVue(BaseModel):
    etat: str
    acteur: str
    commentaire: str
    le: str


class InstructionAnomalieEntree(BaseModel):
    decision: Literal["en_instruction", "justifiee", "usage_personnel", "faux_positif"]
    commentaire: str = ""


class CompteBancaireVue(BaseModel):
    """AXE-832 : un compte bancaire, son sous-compte et ses deux soldes. Le
    solde de la banque est celui du dernier relevé, `None` s'il n'a jamais
    été relevé ; l'écart aussi."""

    compte: str
    nom: str | None
    solde_comptable_cts: int
    solde_banque_cts: int | None
    releve_le: str | None
    ecart_cts: int | None
    # AXE-729 : True comptabilisé, False écarté (personnel), None à décider.
    retenu: bool | None = True


class DecisionCompteEntree(BaseModel):
    retenu: bool


class TransactionVue(BaseModel):
    ecriture_id: str
    date: str
    libelle: str
    montant_cts: int  # signé : positif = argent reçu, négatif = argent sorti (ligne 512)
    compte: str
    statut: str  # "validé" | "à trancher" — vocabulaire unique de badge (doc 11 §4)
    a_justificatif: bool  # doc 17 §9 Semaine 3 : une photo a été jointe (contenu non lu)
    # Proposition pour une opération à trancher, calculée à la lecture : une
    # opération semblable déjà tranchée par l'indiv (« appris »), sinon les
    # règles (« regle ») et le modèle (« modele ») en vigueur. La proposition
    # d'origine, figée à la synchro, reste en base comme trace.
    proposition: str | None = None
    origine_proposition: str | None = None  # "appris" | "regle" | "ia" | "modele" | "banque"
    confiance_proposition: float | None = None
    # Décision humaine en vigueur. None : classée par une règle, ou pas encore.
    categorie: str | None = None
    # AXE-800 : l'opération a été reclassée par l'expert-comptable du
    # portefeuille. Le chauffeur voit qui, quand et pourquoi.
    reclassee_par: str | None = None
    reclassee_le: str | None = None
    motif_reclassement: str | None = None
    # AXE-831 : l'un ou l'autre. L'estimation vient de la table ; le montant
    # relevé, quand un justificatif le donnera, la remplace.
    tva_estimee_cts: int | None = None
    tva_relevee_cts: int | None = None


class DecisionEntree(BaseModel):
    categorie: str  # "usage_personnel" ou toute catégorie du pack (doc 17 §9 bloc C)


class CompteChoix(BaseModel):
    compte: str
    libelle: str


class SujetExpertVue(BaseModel):
    id: str
    dossier_id: str
    dossier_nom: str
    cote: Literal["chauffeur", "gestionnaire"]
    nature: Literal["a_trancher", "ticket", "anomalie", "registre"]
    libelle: str
    detail: str
    montant_cts: int | None
    ecriture_id: str | None
    imputable: bool
    compte_actuel: str | None = None
    compte_suggere: str | None = None
    # Comment l'argent est sorti (carte, virement…), lu à l'affichage pour
    # tous les sujets d'une opération bancaire (AXE-855).
    moyen_paiement: str | None = None


class LigneImputationVue(BaseModel):
    sens: Literal["debit", "credit"]
    compte: str
    montant_cts: int


class ImputationVue(BaseModel):
    ecriture_id: str
    contrepassation_id: str
    lignes: list[LigneImputationVue]
    sujets: list[SujetExpertVue]


class AnnulationImputationEntree(BaseModel):
    dossier_id: str
    ecriture_id: str
    contrepassation_id: str
    motif: str = ""  # obligatoire (AXE-800) : vérifié par `motif_valide`


class FileExpertVue(BaseModel):
    sujets: list[SujetExpertVue]
    comptes: list[CompteChoix]
    # AXE-829 : tags des dossiers présents dans la file, pour le filtre.
    tags_par_dossier: dict[str, list[str]] = {}


class ImputationEntree(BaseModel):
    dossier_id: str
    ecriture_id: str
    compte: str
    motif: str = ""  # obligatoire (AXE-800) : vérifié par `motif_valide`


MAX_DECISIONS_GROUPEES = 1000


class DecisionsGroupeesEntree(BaseModel):
    """« Tout confirmer » : une même catégorie pour des opérations que l'indiv
    a vues listées et confirmées d'un geste."""

    categorie: str
    ecriture_ids: list[str]


class InvitationEntree(BaseModel):
    email: str  # doc 17 §9 bloc B — pas les 3 profils démo, un vrai e-mail entré à la volée


MAX_INVITATIONS_PAR_LOT = 500
_FORME_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LigneInvitationEntree(BaseModel):
    dossier_id: str
    email: str


class InvitationsMasseEntree(BaseModel):
    invitations: list[LigneInvitationEntree] = Field(max_length=MAX_INVITATIONS_PAR_LOT)


class LigneInvitationVue(BaseModel):
    dossier_id: str
    email: str
    # invité | deja_invite | dossier_inconnu | email_invalide | doublon_dans_le_lot | erreur
    resultat: str


class InvitationsMasseVue(BaseModel):
    lignes: list[LigneInvitationVue]
    nb_invitees: int


class InvitationVue(BaseModel):
    dossier_id: str
    email: str
    statut: str  # "invité" | "actif" — jamais "non_invité" ici, ça n'existe qu'en absence


class SignatureGreffeVue(BaseModel):
    dossier_id: str
    signe: bool
    signe_le: str
    qualifie: bool  # doc 20 §4 : toujours False en démo, jamais une vraie signature RGS


def _ledger_avec_decisions(
    dossier: Dossier, base: LedgerService, decisions: DecisionRepository
) -> InMemoryLedgerService:
    """Le grand livre vu par les écrans et la clôture (AXE-420) : les
    reclassements écrits par les décisions, repliés dans leur opération
    (`reclassement.grand_livre_tranche`)."""
    resultat = InMemoryLedgerService()
    for ecriture in grand_livre_tranche(
        base.grand_livre(dossier.id), decisions.lister_decisions(dossier.id), _comptes(dossier)
    ):
        resultat.enregistrer(ecriture)
    return resultat


def _comptes(dossier: Dossier) -> tuple[dict[str, str | None], dict[str, str]]:
    """(comptes de statut du dossier, comptes du pack) pour traduire une décision."""
    return configuration_de(dossier).comptes_categories_statut(), charger_compte_par_categorie()


def _ledger_comptable(
    dossier: Dossier, base: LedgerService, decisions: DecisionRepository
) -> InMemoryLedgerService:
    """Le grand livre tel qu'en base, reclassements compris : FEC, grand
    livre et balance téléchargés (AXE-420). Mêmes soldes que la vue des écrans."""
    resultat = InMemoryLedgerService()
    for ecriture in grand_livre_comptable(
        base.grand_livre(dossier.id), decisions.lister_decisions(dossier.id), _comptes(dossier)
    ):
        resultat.enregistrer(ecriture)
    return resultat


def _statut_invitation_vue(statut: StatutInvitation) -> str:
    return {StatutInvitation.INVITE: "invité", StatutInvitation.ACTIF: "actif"}[statut]


def _construire_liasse(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    provisions: SaisiesCloture = SANS_SAISIE,
) -> LiassePivot:
    """Semaine 4 (doc 17 §9) : même appel que `_resume` (clôture) et que les
    exports du script de chauffeurs type (`_executer_un_chauffeur`), mais sur le
    ledger **avec les décisions humaines déjà appliquées**
    (`_ledger_avec_decisions`) : une transaction tranchée en 455/108 doit
    sortir de la liasse téléchargée, pas seulement du dashboard."""
    return ClotureSimplifieeService(ledger).cloturer(
        dossier.id,
        exercice=str(dossier.exercice_debut.year),
        parametres=_parametres(dossier, provisions),
    )


def _parametres(dossier: Dossier, provisions: SaisiesCloture = SANS_SAISIE) -> ParametresCloture:
    """Bornes déclarées de l'exercice et identité du dossier : ce qui fait
    passer la clôture du bilan simplifié à la liasse fiscale complète."""
    return ParametresCloture(
        exercice_debut=dossier.exercice_debut,
        exercice_fin=dossier.fin_exercice(),
        forme_juridique=dossier.forme_juridique,
        identite=dossier.identite,
        soumis_is=_colonne(dossier).soumis_is,
        associes=_colonne(dossier).associes,
        provisions=provisions.provisions,
        immobilisations=provisions.immobilisations,
        contrats_loa=provisions.contrats_loa,
        deficits_anterieurs=dossier.deficits_anterieurs_euros,
    )


def _provisions_saisies(dossier: Dossier, depot: ProvisionsClotureRepository) -> SaisiesCloture:
    """Estimations CCA/FNP de l'exercice et registre des immobilisations (AXE-802)."""
    return SaisiesCloture(
        depot.lister(dossier.tenant_id, dossier.id, dossier.fin_exercice().year),
        depot.lister_immobilisations(dossier.tenant_id, dossier.id),
        depot.lister_contrats_loa(dossier.tenant_id, dossier.id),
    )


def _regimes_a_venir(
    dossier: Dossier, avenants: tuple[AvenantRegime, ...]
) -> list[RegimeAVenirVue]:
    vues = []
    for avenant in a_venir(dossier, avenants):
        colonne = charger_matrice().colonne(
            FormeJuridique(dossier.forme_juridique), avenant.regime_imposition
        )
        vues.append(
            RegimeAVenirVue(
                exercice=avenant.exercice_effet,
                regime=colonne.libelle if colonne else avenant.regime_imposition.value,
                motif=_MOTIFS_AVENANT[avenant.motif],
            )
        )
    return vues


_MOTIFS_AVENANT = {
    MotifAvenant.FIN_OPTION_IR: ("Fin de l'option pour l'impôt sur le revenu (cinq exercices)"),
    MotifAvenant.RENONCIATION_OPTION_IR: ("Renonciation à l'option pour l'impôt sur le revenu"),
}


def _alerte_franchise_tva(dossier: Dossier, ecritures: tuple[Ecriture, ...]) -> str | None:
    """Seuls les dossiers en franchise sont suivis. L'année civile est celle
    de la clôture de l'exercice (les plafonds sont civils, § 130) ; le
    chiffre d'affaires est le 706 hors taxe de cette année."""
    if configuration_de(dossier).regime_tva is not RegimeTva.FRANCHISE:
        return None
    annee = dossier.fin_exercice().year
    try:
        return suivre_franchise(chiffre_affaires_ht(ecritures, annee), annee).message
    except MillesimeInconnu:
        return None


def _colonne(dossier: Dossier) -> ColonneMatrice:
    """Colonne du dossier dans la matrice statut × régime (doc 06 §7). Un
    dossier en base est déjà validé à l'écriture (`DossierRepository`)."""
    return configuration_de(dossier).colonne


def _exiger_depot_greffe(dossier: Dossier) -> None:
    if not _colonne(dossier).depot_comptes_inpi:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{_colonne(dossier).libelle} ne dépose pas ses comptes au greffe "
                "du tribunal de commerce."
            ),
        )


def _message_operations_restantes(reste: int) -> str:
    nom = "opération" if reste == 1 else "opérations"
    return f"Il reste {reste} {nom} à traiter."


def _exiger_dossier_clair(dossier: Dossier) -> None:
    """AXE-730 : pas de liasse tant que la forme ou l'identité de la société
    est incertaine. Même règle que la clôture (`preparer_passage`)."""
    raison = raison_ambiguite(dossier)
    if raison is not None:
        raise HTTPException(status_code=409, detail=raison)


def _exiger_operations_tranchees(dossier: Dossier, ledger: InMemoryLedgerService) -> None:
    """La liasse fiscale et la signature du greffe figent le résultat.
    Une opération encore au compte d'attente le changerait — même garde
    que la clôture (`preparer_passage`). Les pièces de travail (FEC,
    grand livre, balance) restent téléchargeables."""
    ecritures = ledger.grand_livre(dossier.id)
    exclues = annulees(ecritures)
    reste = sum(
        1
        for ecriture in ecritures
        if ecriture.id not in exclues
        and any(ligne.compte == COMPTE_ATTENTE for ligne in ecriture.lignes)
    )
    if reste:
        raise HTTPException(status_code=409, detail=_message_operations_restantes(reste))


def _ecritures_avec_cloture(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    provisions: SaisiesCloture = SANS_SAISIE,
) -> tuple[Ecriture, ...]:
    """Écritures de l'exercice (mêmes bornes que la liasse) + écritures
    d'inventaire (TVA, IS) : FEC, grand livre et balance téléchargés
    concordent ainsi avec la liasse, au centime."""
    return ClotureSimplifieeService(ledger).ecritures_exercice_completes(
        dossier.id, _parametres(dossier, provisions)
    )


def _digifactory_branche(app: FastAPI) -> bool:
    """Digifactory est le canal bancaire réel du portefeuille : branché, le
    chauffeur ne voit pas « Connecter ma banque » (AXE-433 viendra pour le
    mode `chauffeur_direct`)."""
    return bool(getattr(app.state, "digifactory_branche", True))


def _peut_connecter_sa_banque(digifactory_branche: bool) -> bool:
    """Tant que la banque passe par Digifactory, l'app chauffeur ne propose
    pas de connecter sa banque elle-même."""
    return not digifactory_branche


def _resume(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    comptes: CompteRepository,
    signatures: SignatureRepository,
    digifactory_branche: bool = True,
    provisions: SaisiesCloture = SANS_SAISIE,
) -> DossierResume:
    ecritures = ledger.grand_livre(dossier.id)
    liasse = _construire_liasse(dossier, ledger, provisions)
    nb_a_trancher = _nb_a_trancher(ecritures)
    invitation = comptes.statut(dossier.id)
    document_cloture = signatures.dernier(dossier.id, TYPE_DOCUMENT_CLOTURE)
    document_greffe = signatures.dernier(dossier.id, TYPE_DOCUMENT_GREFFE_INPI)
    return DossierResume(
        dossier_id=dossier.id,
        nom=dossier.nom,
        tva_recettes_regime=dossier.tva_recettes_regime,
        plateformes=list(dossier.plateformes),
        exercice_debut=liasse.exercice_debut.isoformat() if liasse.exercice_debut else None,
        exercice_fin=liasse.exercice_fin.isoformat() if liasse.exercice_fin else None,
        ca_ht_cts=liasse.cases.get("CA_HT", 0),
        charges_cts=liasse.cases.get("CHARGES", 0),
        resultat_cts=liasse.cases.get("RESULTAT", 0),
        alerte_tva=_alerte_franchise_tva(dossier, ecritures),
        tresorerie_cts=liasse.cases.get("TRESORERIE", 0),
        tva_a_payer_cts=liasse.cases.get("TVA_A_PAYER", 0),
        nb_transactions=len(ecritures),
        nb_a_trancher=nb_a_trancher,
        statut_invitation=_statut_invitation_vue(invitation.statut) if invitation else None,
        mode_acces_bancaire=dossier.mode_acces_bancaire,
        peut_connecter_sa_banque=_peut_connecter_sa_banque(digifactory_branche),
        cloture_faite=document_cloture is not None,
        greffe_inpi_signe=document_greffe is not None,
        guide_greffe=_guide_vue(guide_greffe(liasse)),
        declaration_resultat=_colonne(dossier).formulaires_resultat[0],
        depot_greffe=_colonne(dossier).depot_comptes_inpi,
        forme_juridique=dossier.forme_juridique,
        regime_libelle=_colonne(dossier).libelle,
    )


def _verifier_acces_dossier(
    dossier_id: str, identite: IdentiteAuthentifiee | None
) -> IdentiteAuthentifiee:
    """doc 19 §8bis (2026-09-11) : toutes les routes de niveau dossier sont
    indiv-exclusives depuis la révision structurante du même jour (doc 19
    §2.1/§2.4) — un jeton valide est désormais **obligatoire**, pas
    seulement cohérent s'il est fourni. Avant : l'absence de jeton
    (cas gestionnaire, jamais de login) passait sans restriction ; ce
    chemin n'a plus de raison d'être, rien dans l'app n'appelle plus ces
    routes sans jeton. Retourne l'identité (narrowée, non optionnelle) pour
    que l'appelant n'ait plus besoin du stub `UTILISATEUR_DEMO`."""
    if identite is None:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    if identite.dossier_id != dossier_id:
        raise HTTPException(status_code=403, detail="Ce dossier ne vous appartient pas.")
    return identite


def _verifier_acces_gestionnaire(
    identite: IdentiteAuthentifiee | None,
) -> tuple[TenantId, IdentiteAuthentifiee]:
    """doc 03 §7 : le lien `tenant_id` ouvre le portefeuille (agrégats,
    invitations), jamais le détail d'un dossier — voir
    `_verifier_acces_dossier`, qui ne regarde que `dossier_id`. Un compte
    indiv seul n'a pas de `tenant_id` : 403. Retourne le tenant de l'appelant
    et l'identité (narrowée, non optionnelle) : les dossiers visibles sont
    ensuite filtrés par ce tenant."""
    if identite is None:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    if identite.tenant_id is None:
        raise HTTPException(status_code=403, detail="Compte sans portefeuille.")
    return identite.tenant_id, identite


def _preuves_exercice(
    signatures: SignatureRepository, dossier_ids: Sequence[DossierId]
) -> dict[DossierId, set[str]]:
    """Types de jalons déjà enregistrés, par dossier, en une lecture pour
    tout le portefeuille : la table est append-only et indexée par dossier."""
    return signatures.types_presents(dossier_ids, [type_ for type_, _nom in JALONS_EXERCICE])


def _frises(
    statut_invitation: str | None, dossier: Dossier, preuves: set[str]
) -> tuple[int, str, int, str]:
    """doc 19 §2.1 : deux frises, l'exercice en cours et celui d'avant, que
    l'on traite pendant le début de l'année suivante. L'exercice du dossier
    est la seule donnée : terminé, il est celui d'avant et son étape est
    celle des preuves (`etape_depuis_preuves`) ; pas encore terminé, il est
    celui en cours et rien n'est connu de l'exercice d'avant. Retourne
    (année en cours, étape, année d'avant, étape)."""
    fin = dossier.fin_exercice()
    compte = "Suivi" if statut_invitation == "actif" else "Compte"
    if fin < datetime.now(UTC).date():
        etape = etape_depuis_preuves(statut_invitation, preuves)
        return fin.year + 1, compte, fin.year, etape
    return fin.year, compte, fin.year - 1, "Sans exercice"


def _agregat(
    stocke: AgregatStocke,
    dossier: Dossier,
    statut_invitation: str | None,
    preuves: set[str],
    comptes_a_choisir: ComptesAChoisir | None = None,
) -> DossierAgregat:
    """Ce que le gestionnaire voit : les montants gardés en base, et tout ce
    qui change sans écriture lu à l'affichage (le dossier, l'invitation, les
    preuves, la date du jour)."""
    annee_courante, etape_courante, annee_precedente, etape_precedente = _frises(
        statut_invitation, dossier, preuves
    )
    return DossierAgregat(
        dossier_id=dossier.id,
        nom=dossier.nom,
        tva_recettes_regime=dossier.tva_recettes_regime,
        plateformes=list(dossier.plateformes),
        exercice_debut=stocke.exercice_debut,
        exercice_fin=stocke.exercice_fin,
        ca_ht_cts=stocke.ca_ht_cts,
        charges_cts=stocke.charges_cts,
        resultat_cts=stocke.resultat_cts,
        statut_invitation=statut_invitation,
        mode_acces_bancaire=dossier.mode_acces_bancaire,
        forme_juridique=dossier.forme_juridique,
        regime_imposition=dossier.regime_imposition,
        regime_tva=dossier.regime_tva,
        annee_courante=annee_courante,
        etape_courante=etape_courante,
        annee_precedente=annee_precedente,
        etape_precedente=etape_precedente,
        alerte_regime=alerte_option_ir(dossier),
        alerte_tva=stocke.alerte_tva,
        a_confirmer=list(dossier.a_confirmer),
        ecarts_registre=[phrase_gestionnaire(e) for e in dossier.ecarts_registre],
        comptes_a_choisir=comptes_a_choisir.nombre if comptes_a_choisir else 0,
        comptes_a_choisir_depuis=(
            comptes_a_choisir.depuis.date().isoformat() if comptes_a_choisir else None
        ),
        operations_en_attente_de_choix=comptes_a_choisir.operations if comptes_a_choisir else 0,
    )


def calculer_agregat(
    dossier: Dossier,
    base: LedgerService,
    decisions: DecisionRepository,
    provisions: ProvisionsClotureRepository,
) -> AgregatStocke:
    """Les valeurs qui coûtent, calculées pour un seul dossier : celles que
    `_resume` met dans `ca_ht_cts`, `charges_cts`, `resultat_cts`,
    `exercice_debut`, `exercice_fin` et `alerte_tva`, sans ce qu'il lit en
    plus (invitation, preuves, guide du greffe)."""
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    liasse = _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
    return AgregatStocke(
        ca_ht_cts=liasse.cases.get("CA_HT", 0),
        charges_cts=liasse.cases.get("CHARGES", 0),
        resultat_cts=liasse.cases.get("RESULTAT", 0),
        exercice_debut=liasse.exercice_debut.isoformat() if liasse.exercice_debut else None,
        exercice_fin=liasse.exercice_fin.isoformat() if liasse.exercice_fin else None,
        alerte_tva=_alerte_franchise_tva(dossier, ledger.grand_livre(dossier.id)),
    )


def _vues_dossier(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    justificatifs: JustificatifRepository,
) -> list[TransactionVue]:
    """Une vue par écriture, sans proposition. La file expert n'en affiche
    aucune : elle ne paie pas leur calcul."""
    ecritures = ledger.grand_livre(dossier.id)
    exclues = annulees(ecritures)
    avec_photo = justificatifs.presents(dossier.tenant_id, dossier.id)
    # Un reclassement entre banques (ventilation 512 → 512x, AXE-832) n'est
    # pas une opération du relevé : le chauffeur ne le voit pas.
    return [
        _transaction_vue(e, e.id in avec_photo, e.id in exclues, regime_tva=dossier.regime_tva)
        for e in ecritures
        if not est_reclassement_bancaire(e)
    ]


def _avec_reclassements_expert(
    vues: list[TransactionVue], decisions: Sequence[DecisionExpert]
) -> list[TransactionVue]:
    """AXE-800 : la dernière imputation d'expert sur une opération, ou sur
    l'écriture qu'elle a posée, s'affiche au chauffeur avec son auteur et
    son motif. Une annulation efface l'affichage (la dernière décision
    fait foi)."""
    par_ecriture: dict[str, DecisionExpert | None] = {}
    for decision in sorted(decisions, key=lambda d: d.le):
        if decision.nature == "qualification":
            continue
        retenue = decision if decision.nature == "imputation" else None
        cibles = {str(e) for e in decision.ecritures}
        if decision.ecriture_id is not None:
            cibles.add(str(decision.ecriture_id))
        for cible in cibles:
            par_ecriture[cible] = retenue
    return [
        vue.model_copy(
            update={
                "reclassee_par": f"{d.auteur_nom}, expert-comptable",
                "reclassee_le": d.le.date().isoformat(),
                "motif_reclassement": d.motif,
            }
        )
        if (d := par_ecriture.get(vue.ecriture_id)) is not None
        else vue
        for vue in vues
    ]


def _transactions_dossier(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    justificatifs: JustificatifRepository,
    decisions: tuple[DecisionHumaine, ...] = (),
    pipeline: RulesAndMlPipeline | None = None,
    ia: Mapping[str, PropositionIa] | None = None,
) -> list[TransactionVue]:
    """Extrait de la route (doc 08 §2 : longueur de fonction)."""
    vues = _avec_categories(_vues_dossier(dossier, ledger, justificatifs), decisions)
    banques = {
        str(e.id): ligne.compte
        for e in ledger.grand_livre(dossier.id)
        if (ligne := ligne_banque(e)) is not None
    }
    return _avec_propositions(dossier, vues, decisions, pipeline, banques, ia)


def _avec_categories(
    vues: list[TransactionVue], decisions: tuple[DecisionHumaine, ...]
) -> list[TransactionVue]:
    """La dernière décision d'une écriture est sa catégorie en vigueur."""
    categories: dict[str, str] = {}
    for decision in decisions:
        categories[str(decision.ecriture_id)] = decision.categorie
    if not categories:
        return vues
    return [
        vue.model_copy(update={"categorie": categories[vue.ecriture_id]})
        if vue.ecriture_id in categories
        else vue
        for vue in vues
    ]


_ORIGINE_PAR_ETAGE = {Etage.REGLE: "regle", Etage.ML: "modele", Etage.BANQUE: "banque"}


def _transactions_a_relire(
    dossier: Dossier,
    a_trancher: list[TransactionVue],
    requetes: list[tuple[str, int]],
    banques: dict[str, str],
) -> list[NormalizedTransaction]:
    """Les opérations à trancher, rejouées dans le pipeline. Le sous-compte
    512x (AXE-832) permet d'y reconnaître les virements internes (AXE-826)."""
    return [
        NormalizedTransaction(
            id=TransactionId(vue.ecriture_id),
            dossier_id=dossier.id,
            date=date.fromisoformat(vue.date),
            montant_cts=vue.montant_cts,
            libelle=libelle,
            source_provider="lecture",
            raw_payload={},
            compte_bancaire=banques.get(vue.ecriture_id),
        )
        for vue, (libelle, _) in zip(a_trancher, requetes, strict=True)
    ]


def _avec_propositions(
    dossier: Dossier,
    vues: list[TransactionVue],
    decisions: tuple[DecisionHumaine, ...],
    pipeline: RulesAndMlPipeline | None,
    banques: dict[str, str] | None = None,
    ia: Mapping[str, PropositionIa] | None = None,
) -> list[TransactionVue]:
    """Une proposition par opération à trancher : d'abord une opération
    semblable que l'indiv a déjà tranchée (dernière décision de chaque
    écriture), puis une règle, puis l'IA (AXE-888), puis le modèle et la
    banque. Rien si tous s'abstiennent."""
    a_trancher = [vue for vue in vues if vue.statut == "à trancher"]
    if not a_trancher:
        return vues
    categories = {decision.ecriture_id: decision.categorie for decision in decisions}
    par_id = {vue.ecriture_id: vue for vue in vues}
    tranchees = [
        OperationTranchee(libelle_sans_categorie(vue.libelle), vue.montant_cts, categorie)
        for ecriture_id, categorie in categories.items()
        if (vue := par_id.get(ecriture_id)) is not None
    ]
    requetes = [(libelle_sans_categorie(v.libelle), v.montant_cts) for v in a_trancher]
    apprises = propositions_apprises(tranchees, requetes)
    actuelles = (
        pipeline.categoriser_lot(
            dossier.id, _transactions_a_relire(dossier, a_trancher, requetes, banques or {})
        )
        if pipeline is not None
        else [None] * len(a_trancher)
    )
    mises_a_jour: dict[str, dict[str, object]] = {}
    for vue, apprise, actuelle in zip(a_trancher, apprises, actuelles, strict=True):
        retenue = _proposition_retenue(vue, apprise, actuelle, ia or {})
        if retenue is not None:
            mises_a_jour[vue.ecriture_id] = retenue
    return [
        vue.model_copy(update=mises_a_jour[vue.ecriture_id])
        if vue.ecriture_id in mises_a_jour
        else vue
        for vue in vues
    ]


def _proposition_retenue(
    vue: TransactionVue,
    apprise: PropositionApprise | None,
    actuelle: ProposedEntry | None,
    ia: Mapping[str, PropositionIa],
) -> dict[str, object] | None:
    if apprise is not None:
        return {
            "proposition": apprise.categorie,
            "origine_proposition": "appris",
            "confiance_proposition": round(apprise.similarite, 2),
        }
    utile = actuelle is not None and actuelle.categorie != CATEGORIE_PAR_DEFAUT
    if utile and actuelle is not None and actuelle.etage is Etage.REGLE:
        return _proposition_du_pipeline(actuelle)
    propre = ia.get(cle_libelle(vue.libelle))
    if propre is not None and propre.proposable:
        return {
            "proposition": propre.categorie,
            "origine_proposition": "ia",
            "confiance_proposition": round(propre.confiance, 2),
        }
    return _proposition_du_pipeline(actuelle) if utile and actuelle is not None else None


def _proposition_du_pipeline(actuelle: ProposedEntry) -> dict[str, object]:
    return {
        "proposition": actuelle.categorie,
        "origine_proposition": _ORIGINE_PAR_ETAGE.get(actuelle.etage),
        "confiance_proposition": round(actuelle.confiance, 2),
    }


def _nb_a_trancher(ecritures: tuple[Ecriture, ...] | list[Ecriture]) -> int:
    exclues = annulees(ecritures)
    return sum(
        1
        for e in ecritures
        if e.id not in exclues and any(ligne.compte == COMPTE_ATTENTE for ligne in e.lignes)
    )


def _montant_512(ecriture: Ecriture) -> int:
    """Le sens de la ligne de banque (512 ou 512x) donne le montant signé
    façon relevé bancaire (doc 11 §1 : « chiffres irréprochables »), pas le
    montant absolu."""
    return montant_bancaire(ecriture)


def _compte_affiche(ecriture: Ecriture) -> str:
    """Une écriture de settlement a plusieurs comptes en contrepartie du 512
    (706/622/44566/44571) — pas un seul compte à afficher tel quel."""
    autres = comptes_hors_banque(ecriture)
    return autres[0] if len(autres) == 1 else "règlement plateforme"


def _vue_tranchee(
    dossier: Dossier, ecriture: Ecriture, a_justificatif: bool, categorie: str
) -> TransactionVue:
    """Réponse d'une décision ou d'une correction : la catégorie vient d'être posée."""
    return _transaction_vue(
        ecriture,
        a_justificatif,
        annulee=False,
        regime_tva=dossier.regime_tva,
        categorie=categorie,
    ).model_copy(update={"categorie": categorie})


def _transaction_vue(
    ecriture: Ecriture,
    a_justificatif: bool,
    annulee: bool,
    *,
    regime_tva: str = "franchise",
    categorie: str | None = None,
) -> TransactionVue:
    a_trancher = not annulee and any(ligne.compte == COMPTE_ATTENTE for ligne in ecriture.lignes)
    estimee, relevee = _montants_tva(ecriture, regime_tva, categorie)
    return TransactionVue(
        ecriture_id=ecriture.id,
        date=ecriture.date.isoformat(),
        libelle=sans_categorie(ecriture.libelle),  # AXE-848 : jamais la catégorie technique
        montant_cts=_montant_512(ecriture),
        compte=_compte_affiche(ecriture),
        statut="à trancher" if a_trancher else "validé",
        a_justificatif=a_justificatif,
        tva_estimee_cts=estimee,
        tva_relevee_cts=relevee,
    )


def _montants_tva(
    ecriture: Ecriture, regime_tva: str, categorie: str | None
) -> tuple[int | None, int | None]:
    """(estimation de la table, montant relevé). Le montant déjà écrit sur la
    ligne fait foi ; sinon l'estimation est celle de la table, à la date."""
    tva = tva_affichee(
        ecriture.lignes,
        montant_ttc_cts=abs(_montant_512(ecriture)),
        categorie=categorie,
        jour=ecriture.date,
        regime_tva=regime_tva,
    )
    if tva is None:
        return None, None
    if tva.origine == "relevee":
        return None, tva.centimes
    return tva.centimes, None


def _categories_par_compte() -> dict[str, str]:
    inverse: dict[str, str] = {}
    for categorie, compte in charger_compte_par_categorie().items():
        inverse.setdefault(compte, categorie)
    return inverse


def _mouvement_anomalie(
    dossier: Dossier,
    ecriture: Ecriture,
    categorie: str,
    a_justificatif: bool,
) -> MouvementSurveille | None:
    autres = comptes_hors_banque(ecriture)
    if len(autres) != 1 or not categorie:
        return None
    return MouvementSurveille(
        dossier_id=dossier.id,
        ecriture_id=ecriture.id,
        date=ecriture.date,
        libelle=sans_categorie(ecriture.libelle),  # AXE-848
        montant_centimes=_montant_512(ecriture),
        categorie=categorie,
        justificatif_id=ecriture.id if a_justificatif else None,
        nature_ticket=None,
    )


def _mouvements_surveilles(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    justificatifs: JustificatifRepository,
    decisions: DecisionRepository,
    moyens: Mapping[EcritureId, str] | None = None,
) -> tuple[MouvementSurveille, ...]:
    """Sorties catégorisées, hors écritures contre-passées. Plafond 10 000.
    `moyens` : le moyen de paiement par écriture, quand il est connu (AXE-836)."""
    ecritures = ledger.grand_livre(dossier.id)
    exclues = annulees(ecritures)
    avec_photo = justificatifs.presents(dossier.tenant_id, dossier.id)
    decidees = {
        decision.ecriture_id: decision.categorie
        for decision in decisions.lister_decisions(dossier.id)
    }
    par_compte = _categories_par_compte()
    mouvements: list[MouvementSurveille] = []
    for ecriture in ecritures:
        if ecriture.id in exclues or len(mouvements) >= 10_000:
            continue
        autres = comptes_hors_banque(ecriture)
        categorie = decidees.get(ecriture.id, "")
        if not categorie and len(autres) == 1:
            categorie = par_compte.get(autres[0], "")
        mouvement = _mouvement_anomalie(
            dossier,
            ecriture,
            categorie,
            ecriture.id in avec_photo,
        )
        if mouvement is not None:
            moyen = (moyens or {}).get(ecriture.id)
            mouvements.append(dataclasses.replace(mouvement, moyen_paiement=moyen))
    return tuple(mouvements)


_ENGINE_DEMO: Engine | None = None


def _engine() -> Engine:
    """Engine Postgres partagé, construit **à la première requête réelle**,
    pas à l'import du module : importer `api.routes` (pour ses tests, par
    exemple) ne doit pas exiger `DATABASE_URL_WEB`. Les tests surchargent
    les dépendances ci-dessous (`app.dependency_overrides[...] = ...`) avec
    des implémentations en mémoire pour ne jamais l'appeler du tout.

    `DATABASE_URL_WEB`, pas `DATABASE_URL` (doc 12 §1.1, migration
    `87fc7238e52e`) : le rôle `axelcompta_web`, soumis aux policies RLS —
    jamais le rôle `user` (propriétaire des tables, réservé aux scripts
    d'administration). Se connecter par erreur avec `DATABASE_URL` ici
    ferait tourner l'API entière sans RLS, silencieusement."""
    global _ENGINE_DEMO
    if _ENGINE_DEMO is None:
        _ENGINE_DEMO = engine_depuis_env("DATABASE_URL_WEB")
    return _ENGINE_DEMO


def get_decisions() -> DecisionRepository:
    """Dépendance FastAPI — voir `_engine`."""
    return PostgresDecisionRepository(_engine())


def get_dossiers() -> DossierRepository:
    """Dépendance FastAPI — dossiers et tenants (`tenants/`), peuplés par
    l'import Digifactory (voir docs/17-plan-demo-backend.md)."""
    return PostgresDossierRepository(_engine())


def get_ledger() -> LedgerService:
    """Dépendance FastAPI — le ledger persisté (écritures d'origine, sans les
    décisions humaines, qui sont une couche séparée)."""
    return PostgresLedgerService(_engine())


def get_ecrire_decisions(
    decisions: Annotated[DecisionRepository, Depends(get_decisions)],
    base: Annotated[LedgerService, Depends(get_ledger)],
) -> EcrireDecisions:
    """AXE-852 : décisions et OD de reclassement dans une seule transaction
    quand les deux dépôts sont en base. Les tests remplacent les dépôts par
    des versions en mémoire : ils reçoivent l'écriture en séquence, sur ces
    mêmes dépôts."""
    if isinstance(decisions, PostgresDecisionRepository) and isinstance(
        base, PostgresLedgerService
    ):
        return PostgresDecisionsEtReclassements(_engine())
    return EnSequence(decisions, base)


def get_propositions() -> PropositionRepository:
    """Dépendance FastAPI — ce que le pipeline avait proposé par écriture."""
    return PostgresPropositionRepository(_engine())


_PIPELINE: RulesAndMlPipeline | None = None
_ETAT_CATEGORISATION: EtatCategorisation | None = None


def get_pipeline() -> RulesAndMlPipeline:
    """Dépendance FastAPI — règles du pack et modèle chargés une fois par
    processus. Sans modèle sur le poste (fichier gitignoré), les règles
    seules pour servir les écrans, mais l'état est exposé et signalé
    (AXE-825) : `GET /portefeuille/categorisation`."""
    global _PIPELINE, _ETAT_CATEGORISATION
    if _PIPELINE is None:
        charge = charger_modele_et_etat()
        modele = charge.modele
        _ETAT_CATEGORISATION = charge.etat
        if modele is None and not repli_sans_modele_permis():
            signaler(charge.etat.raison or "Modèle de catégorisation absent.")
        _PIPELINE = RulesAndMlPipeline(
            regles=charger_regles(),
            modele=modele,
            calibration=charger_calibration() if modele is not None else None,
            categories_banque=charger_categories_banque(),
        )
    return _PIPELINE


def get_etat_categorisation() -> EtatCategorisation:
    get_pipeline()
    return _ETAT_CATEGORISATION or EtatCategorisation(True, "")


def get_lots_llm() -> LotsLlm:
    """AXE-887 : lots envoyés au LLM, lus sous la RLS du portefeuille.
    Étage éteint : rien à lire, aucune connexion."""
    return PostgresLotsLlm(_engine()) if llm_actif() else LotsLlmMemoire()


LotsLlmDep = Annotated[LotsLlm, Depends(get_lots_llm)]


DecisionsDep = Annotated[DecisionRepository, Depends(get_decisions)]
DossiersDep = Annotated[DossierRepository, Depends(get_dossiers)]
LedgerBaseDep = Annotated[LedgerService, Depends(get_ledger)]
EcrireDecisionsDep = Annotated[EcrireDecisions, Depends(get_ecrire_decisions)]
PropositionsDep = Annotated[PropositionRepository, Depends(get_propositions)]


def get_propositions_ia() -> PropositionsIa:
    """Dépendance FastAPI — propositions de l'IA par libellé (AXE-888)."""
    return PostgresPropositionsIa(_engine())


PropositionsIaDep = Annotated[PropositionsIa, Depends(get_propositions_ia)]


def get_verdicts() -> VerdictsRepository:
    """Verdicts « juste » / « faux » sur les classements (AXE-823)."""
    return PostgresVerdicts(_engine())


VerdictsDep = Annotated[VerdictsRepository, Depends(get_verdicts)]
PipelineDep = Annotated[RulesAndMlPipeline, Depends(get_pipeline)]


class LecteurConsentements(Protocol):
    def lister(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, ReleveConsentement]: ...


def get_consentements() -> LecteurConsentements:
    """Dépendance FastAPI — le relevé des connexions bancaires (lecture seule
    côté API : seule la synchro l'écrit)."""
    return PostgresConsentementRepository(_engine())


ConsentementsDep = Annotated[LecteurConsentements, Depends(get_consentements)]


_CLIENT_COMPTES: SupabaseCompteRepository | None = None


def get_comptes() -> CompteRepository:
    """Dépendance FastAPI — même idiome que `get_decisions` : le client
    Supabase se construit à la première requête réelle, jamais à l'import
    (`SupabaseConfig.depuis_env()` échouerait sinon sans
    SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY). Les tests surchargent avec
    `InMemoryCompteRepository` (doc 17 §9 bloc B — Louis, 2026-09-07 :
    « je ne veux pas dépendre de Supabase pour tous les tests »)."""
    global _CLIENT_COMPTES
    if _CLIENT_COMPTES is None:
        _CLIENT_COMPTES = SupabaseCompteRepository(SupabaseConfig.depuis_env())
    return _CLIENT_COMPTES


ComptesDep = Annotated[CompteRepository, Depends(get_comptes)]

_METHODES_LECTURE = frozenset({"GET", "HEAD"})


def get_identite(
    request: Request,
    identite: Annotated[IdentiteAuthentifiee | None, Depends(identite_chauffeur_optionnelle)],
    dossiers: DossiersDep,
    x_dossier: Annotated[str | None, Header(alias="X-Dossier")] = None,
) -> IdentiteAuthentifiee | None:
    """L'identité de l'appelant. Le compte de test (AXE-822) lit un dossier
    via `X-Dossier`, ou ouvre le portefeuille si l'appel vient du formulaire
    gestionnaire (`X-Cote`). Tout autre compte ignore ces en-têtes."""
    if identite is None or identite.lecteur_test_tenant is None:
        return identite
    if request.headers.get("x-cote") == "gestionnaire":
        return dataclasses.replace(
            identite,
            tenant_id=identite.lecteur_test_tenant,
            lecteur_test_tenant=None,
        )
    if identite.aal != "aal2":
        raise HTTPException(status_code=403, detail=MESSAGE_MFA_REQUISE)
    return _dossier_du_lecteur_test(identite, request.method, x_dossier, dossiers)


def _dossier_du_lecteur_test(
    identite: IdentiteAuthentifiee,
    methode: str,
    x_dossier: str | None,
    dossiers: DossierRepository,
) -> IdentiteAuthentifiee:
    """Lecture seule : toute écriture répond 403, quelle que soit la route.
    Le dossier demandé doit être dans le portefeuille du compte ; sinon 403,
    sans dire s'il existe ailleurs."""
    if methode not in _METHODES_LECTURE:
        raise HTTPException(status_code=403, detail="Compte de test : lecture seule.")
    if x_dossier is None:
        return identite
    dossier = dossiers.obtenir(DossierId(x_dossier))
    if dossier is None or dossier.tenant_id != identite.lecteur_test_tenant:
        raise HTTPException(
            status_code=403, detail="Ce dossier n'est pas dans le portefeuille de test."
        )
    return dataclasses.replace(identite, dossier_id=dossier.id)


IdentiteDep = Annotated[IdentiteAuthentifiee | None, Depends(get_identite)]


def get_consultations() -> JournalConsultations:
    """Dépendance FastAPI — voir `_engine`."""
    return PostgresJournalConsultations(_engine())


ConsultationsDep = Annotated[JournalConsultations, Depends(get_consultations)]


def get_journal_acces() -> JournalAcces:
    """Dépendance FastAPI — voir `_engine` (AXE-812)."""
    return PostgresJournalAcces(_engine())


def get_journal_portefeuille() -> JournalPortefeuille:
    """Dépendance FastAPI — voir `_engine` (AXE-812)."""
    return PostgresJournalPortefeuille(_engine())


JournalAccesDep = Annotated[JournalAcces, Depends(get_journal_acces)]
JournalPortefeuilleDep = Annotated[JournalPortefeuille, Depends(get_journal_portefeuille)]


def _tracer_export(
    journal: JournalAcces, dossier: Dossier, identite: IdentiteAuthentifiee | None, nom: str
) -> None:
    """AXE-812 : chaque téléchargement d'un export laisse sa ligne au journal
    d'audit (qui, quel fichier, quand). `identite` est déjà vérifiée par
    `DossierDep`."""
    if identite is not None:
        journal.noter(dossier.id, ACTE_EXPORT, nom, identite.user_id, datetime.now(UTC))


def get_dossier_autorise(dossier_id: str, identite: IdentiteDep, dossiers: DossiersDep) -> Dossier:
    """Accès indiv à un dossier. L'ordre compte : identité (401), droit sur
    ce dossier (403), **puis** existence (404). Inverser laisserait un appelant
    non autorisé distinguer un dossier inexistant d'un dossier interdit."""
    _verifier_acces_dossier(dossier_id, identite)
    dossier = dossiers.obtenir(DossierId(dossier_id))
    if dossier is None:
        raise HTTPException(status_code=404, detail=f"Dossier inconnu : {dossier_id}")
    return dossier


DossierDep = Annotated[Dossier, Depends(get_dossier_autorise)]


def get_dossier_du_portefeuille(
    dossier_id: str, identite: IdentiteDep, dossiers: DossiersDep
) -> Dossier:
    """Accès gestionnaire à un dossier **de son portefeuille**. Un dossier
    d'un autre tenant répond 404, pas 403 : un gestionnaire ne doit pas
    pouvoir sonder l'existence des dossiers d'un autre portefeuille."""
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    dossier = dossiers.obtenir(DossierId(dossier_id))
    if dossier is None or dossier.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"Dossier inconnu : {dossier_id}")
    return dossier


DossierPortefeuilleDep = Annotated[Dossier, Depends(get_dossier_du_portefeuille)]


def get_experts() -> ExpertRepository:
    """Dépendance FastAPI — voir `_engine` (AXE-800)."""
    return PostgresExpertRepository(_engine())


ExpertsDep = Annotated[ExpertRepository, Depends(get_experts)]


def _expert(
    identite: IdentiteAuthentifiee | None, role: str, experts: ExpertRepository
) -> tuple[TenantId, IdentiteAuthentifiee, ExpertActif]:
    """AXE-800 : seul l'expert-comptable habilité, engagement accepté, voit
    le détail des dossiers et y écrit. Le gestionnaire garde les agrégats."""
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    actif = expert_actif(
        role,
        experts.habilitation(tenant_id, identite.email),
        experts.engagement(tenant_id, identite.email),
    )
    return tenant_id, identite, actif


def get_dossier_de_l_expert(
    dossier: DossierPortefeuilleDep,
    identite: IdentiteDep,
    role: RoleMembreDep,
    experts: ExpertsDep,
) -> Dossier:
    """Un dossier du portefeuille, couvert par la lettre de mission de
    l'expert qui le demande (AXE-800)."""
    _tenant, _identite, actif = _expert(identite, role, experts)
    exiger_dossier(actif, dossier.id)
    return dossier


DossierExpertDep = Annotated[Dossier, Depends(get_dossier_de_l_expert)]


def get_journal_ingestion() -> JournalIngestion:
    """Quarantaine d'ingestion, lecture par le gestionnaire (AXE-424)."""
    return PostgresJournalIngestion(_engine())


JournalIngestionDep = Annotated[JournalIngestion, Depends(get_journal_ingestion)]


def get_resolutions_quarantaine() -> ResolutionsRepository:
    return PostgresResolutions(_engine())


ResolutionsDep = Annotated[ResolutionsRepository, Depends(get_resolutions_quarantaine)]


def get_ledger_du_dossier(
    dossier: DossierDep, base: LedgerBaseDep, decisions: DecisionsDep
) -> InMemoryLedgerService:
    return _ledger_avec_decisions(dossier, base, decisions)


LedgerDossierDep = Annotated[InMemoryLedgerService, Depends(get_ledger_du_dossier)]


def get_ledger_comptable(
    dossier: DossierDep, base: LedgerBaseDep, decisions: DecisionsDep
) -> InMemoryLedgerService:
    return _ledger_comptable(dossier, base, decisions)


LedgerComptableDep = Annotated[InMemoryLedgerService, Depends(get_ledger_comptable)]


def get_justificatifs() -> JustificatifRepository:
    """Postgres, rôle web, policies RLS. Les tests surchargent avec
    `InMemoryJustificatifRepository`."""
    return PostgresJustificatifRepository(_engine())


JustificatifsDep = Annotated[JustificatifRepository, Depends(get_justificatifs)]


def get_comptes_bancaires() -> CompteBancaireRepository:
    """Postgres, rôle web (lecture seule), policies RLS. Les tests surchargent
    avec `CompteBancaireMemoire`."""
    return PostgresCompteBancaireRepository(_engine())


ComptesBancairesDep = Annotated[CompteBancaireRepository, Depends(get_comptes_bancaires)]


def get_registre_anomalies() -> InstructionsRepository:
    """Qualifications d'alertes, en base (AXE-814) : elles survivent aux
    redémarrages et se partagent entre workers. `RegistreInstructions` en
    mémoire dans les tests."""
    return PostgresInstructions(_engine())


RegistreAnomaliesDep = Annotated[InstructionsRepository, Depends(get_registre_anomalies)]


def get_signatures_inpi() -> SignatureRepository:
    """Dépendance FastAPI — même persistance que `get_decisions` :
    append-only en Postgres, pour que la preuve survive à un redémarrage.
    `qualifie` reste False tant que le prestataire réel (ADR-004) n'est pas
    branché. Les tests surchargent avec `InMemorySignatureRepository`."""
    return PostgresSignatureRepository(_engine())


SignaturesInpiDep = Annotated[SignatureRepository, Depends(get_signatures_inpi)]


def get_notifications() -> NotificationRepository:
    """Dépendance FastAPI — notifications internes posées par
    `axelcompta.taches`. Les tests surchargent avec
    `InMemoryNotificationRepository`."""
    return PostgresNotificationRepository(_engine())


NotificationsDep = Annotated[NotificationRepository, Depends(get_notifications)]


def get_avenants() -> AvenantRegimeRepository:
    """Dépendance FastAPI — avenants de régime, en lecture seule côté API
    (écrits par les tâches planifiées). Surchargée en mémoire dans les tests."""
    return PostgresAvenantRegimeRepository(_engine())


AvenantsDep = Annotated[AvenantRegimeRepository, Depends(get_avenants)]


def get_exercices() -> ExerciceRepository:
    """Dépendance FastAPI — historique des exercices clos. Surchargée en
    mémoire dans les tests."""
    return PostgresExerciceRepository(_engine())


ExercicesDep = Annotated[ExerciceRepository, Depends(get_exercices)]


def get_affectations() -> AffectationRepository:
    """Dépendance FastAPI — décisions d'affectation du résultat. Surchargée
    en mémoire dans les tests."""
    return PostgresAffectationRepository(_engine())


AffectationsDep = Annotated[AffectationRepository, Depends(get_affectations)]


def get_provisions_cloture() -> ProvisionsClotureRepository:
    """Dépendance FastAPI — estimations CCA/FNP saisies. Surchargée en mémoire
    dans les tests."""
    return PostgresProvisionsClotureRepository(_engine())


ProvisionsDep = Annotated[ProvisionsClotureRepository, Depends(get_provisions_cloture)]


def get_agregats() -> AgregatsRepository:
    """Dépendance FastAPI — agrégats du portefeuille. Surchargée en mémoire
    dans les tests."""
    return PostgresAgregatsRepository(_engine())


AgregatsDep = Annotated[AgregatsRepository, Depends(get_agregats)]


def get_tags() -> TagsRepository:
    """Tags du portefeuille (AXE-829). Postgres, rôle web, RLS par
    portefeuille ; `TagsMemoire` dans les tests."""
    return PostgresTagsRepository(_engine())


TagsDep = Annotated[TagsRepository, Depends(get_tags)]


def get_cache_file_expert() -> CacheFileExpert:
    """Sujets de la file expert gardés par dossier (AXE-824) ; `SansCache`
    dans les tests en mémoire, où rien ne monte les versions."""
    return PostgresCacheFileExpert(_engine())


CacheFileExpertDep = Annotated[CacheFileExpert, Depends(get_cache_file_expert)]


def get_cache_classees() -> CacheFileExpert:
    """Opérations déjà classées gardées par dossier (AXE-824). `SansCache`
    dans les tests en mémoire, où rien ne monte les versions."""
    return cache_operations_classees(_engine())


CacheClasseesDep = Annotated[CacheFileExpert, Depends(get_cache_classees)]


def _trancher(
    dossier: Dossier,
    ecriture_id: str,
    categorie: str,
    base: LedgerService,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
    decide_par: UserId,
    ecrire: EcrireDecisions,
    ia: Mapping[str, PropositionIa],
) -> Ecriture:
    """doc 17 §9 bloc C : la décision humaine, pour de vrai — déclenche le
    `workflow` testé (doc 05 §5), pas un changement d'état côté React seul.
    Extrait de la route (doc 08 §2 : longueur de fonction) plutôt que fait
    inline. `decide_par` est toujours l'identité réelle de l'indiv depuis le
    2026-09-11 (doc 19 §8bis)."""
    ecritures = base.grand_livre(dossier.id)
    ecriture = next((e for e in ecritures if e.id == ecriture_id), None)
    if ecriture is None:
        raise HTTPException(status_code=404, detail="Cette opération est introuvable.")
    if ecriture.id in annulees(ecritures):
        raise HTTPException(status_code=409, detail="Cette opération a déjà été annulée.")
    if (
        decision_en_vigueur(decisions.decision_courante(dossier.id, EcritureId(ecriture_id)))
        is not None
    ):
        raise HTTPException(
            status_code=409,
            detail="Cette opération a déjà été classée. Le choix ne se modifie pas.",
        )
    if not any(ligne.compte == COMPTE_ATTENTE for ligne in ecriture.lignes):
        raise HTTPException(status_code=409, detail="Cette opération n'est pas à classer.")
    decision = _nouvelle_decision(
        dossier, ecriture, categorie, (decisions, propositions), decide_par, ia
    )
    ecrire.ecrire([decision], _reclassements(dossier, base, [(ecriture.id, categorie)]))
    return _ecriture_decidee(dossier, base, decisions, ecriture_id)


def _corriger(
    dossier: Dossier,
    ecriture_id: str,
    categorie: str,
    base: LedgerService,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
    decide_par: UserId,
    ecrire: EcrireDecisions,
    ia: Mapping[str, PropositionIa],
) -> Ecriture:
    """Corriger, c'est enregistrer une nouvelle décision. L'ancienne reste
    (doc 05 §5) : la dernière prévaut, rien n'est modifié en place."""
    ecritures = base.grand_livre(dossier.id)
    ecriture = next((e for e in ecritures if e.id == ecriture_id), None)
    if ecriture is None:
        raise HTTPException(status_code=404, detail="Cette opération est introuvable.")
    if ecriture.id in annulees(ecritures):
        raise HTTPException(status_code=409, detail="Cette opération a déjà été annulée.")
    if decisions.decision_courante(dossier.id, EcritureId(ecriture_id)) is None:
        raise HTTPException(status_code=409, detail="Cette opération n'a pas encore été classée.")
    if not any(ligne.compte == COMPTE_ATTENTE for ligne in ecriture.lignes):
        raise HTTPException(
            status_code=409,
            detail="Cette opération ne se corrige pas par une nouvelle catégorie.",
        )
    decision = _nouvelle_decision(
        dossier, ecriture, categorie, (decisions, propositions), decide_par, ia
    )
    ecrire.ecrire([decision], _reclassements(dossier, base, [(ecriture.id, categorie)]))
    return _ecriture_decidee(dossier, base, decisions, ecriture_id)


def _nouvelle_decision(
    dossier: Dossier,
    ecriture: Ecriture,
    categorie: str,
    depots: tuple[DecisionRepository, PropositionRepository],
    decide_par: UserId,
    ia: Mapping[str, PropositionIa],
) -> DecisionHumaine:
    """La décision à écrire, si la catégorie a un compte. N'écrit rien :
    l'appelant l'écrit avec son OD de reclassement (AXE-852)."""
    decisions, propositions = depots
    proposition = propositions.obtenir(dossier.id, ecriture.id)
    if proposition is None:
        raise HTTPException(
            status_code=500,
            detail="Cette opération n'a pas de proposition d'origine.",
        )
    comptes = charger_compte_par_categorie()
    resoudre_ecriture_a_trancher(
        ecriture, categorie, configuration_de(dossier).comptes_categories_statut(), comptes
    )
    courante = decisions.decision_courante(dossier.id, ecriture.id)
    maintenant = datetime.now(UTC)
    if courante is not None and maintenant <= courante.decide_le:
        maintenant = courante.decide_le + timedelta(microseconds=1)
    return DecisionHumaine(
        dossier_id=dossier.id,
        ecriture_id=ecriture.id,
        categorie=categorie,
        etage_origine=proposition.etage,
        confiance_origine=proposition.confiance,
        decide_par=decide_par,
        decide_le=maintenant,
        contexte=_contexte_avant(
            ecriture,
            (proposition, ia.get(cle_libelle(ecriture.libelle))),
            decision_en_vigueur(courante),
            categorie,
        ),
    )


def _contexte_avant(
    ecriture: Ecriture,
    avis: tuple[ProposedEntry, PropositionIa | None],
    en_vigueur: DecisionHumaine | None,
    categorie: str,
) -> ContexteDecision:
    """Une correction part de la décision en vigueur, pas de la proposition
    d'origine du pipeline. AXE-901 : l'avis de chaque étage est gardé."""
    proposition, ia = avis
    if en_vigueur is None:
        return _contexte_proposition(ecriture, proposition, categorie, ia)
    precedente = (en_vigueur.categorie, Etage.REVUE_HUMAINE.name, 1.0)
    return dataclasses.replace(
        _contexte(ecriture, categorie, precedente, proposition.moyen_paiement),
        avis=avis_etages(proposition, ia),
    )


def _contexte(
    ecriture: Ecriture,
    categorie: str,
    proposee: tuple[str | None, str | None, float | None],
    moyen_paiement: str | None = None,
) -> ContexteDecision:
    """AXE-871 : ce que l'humain avait sous les yeux. `proposee` : (catégorie,
    étage, confiance) proposés à ce moment-là."""
    categorie_proposee, etage, confiance = proposee
    return ContexteDecision(
        libelle=sans_categorie(ecriture.libelle),
        montant_cts=montant_bancaire(ecriture),
        moyen_paiement=moyen_paiement,
        proposee=categorie_proposee,
        etage_propose=etage,
        confiance_proposee=confiance,
        nature=nature_decision(categorie_proposee, categorie),
    )


def _contexte_proposition(
    ecriture: Ecriture,
    proposition: ProposedEntry,
    categorie: str,
    ia: PropositionIa | None = None,
) -> ContexteDecision:
    """AXE-901 : la proposition retenue est celle que la file affichait
    (l'IA quand aucune règle ne s'applique), plus l'avis de chaque étage."""
    return dataclasses.replace(
        _contexte(
            ecriture,
            categorie,
            proposition_affichee(proposition, ia),
            proposition.moyen_paiement,
        ),
        avis=avis_etages(proposition, ia),
    )


def _reclassements(
    dossier: Dossier, base: LedgerService, tranchees: Sequence[tuple[EcritureId, str]]
) -> list[Ecriture]:
    """AXE-420 : l'OD de reclassement de chaque décision, calculée sans rien
    écrire. Aucune si le montant est déjà sur le bon compte. Les OD d'un
    même lot se suivent : chacune part du compte laissé par la précédente.
    L'appelant les écrit avec leurs décisions, tout ou rien (AXE-852)."""
    ecritures = list(base.grand_livre(dossier.id))
    par_id = {e.id: e for e in ecritures}
    periodes = base.periodes_closes(dossier.id)
    calculees: list[Ecriture] = []
    for ecriture_id, categorie in tranchees:
        source = par_id.get(ecriture_id)
        if source is None:
            continue
        reclassement = reclasser(
            source, categorie, ecritures, _comptes(dossier), periodes, dossier.regime_tva
        )
        if reclassement is not None:
            calculees.append(reclassement)
            ecritures.append(reclassement)
        # AXE-889 : un virement ventilé qui quitte le 706 perd sa ventilation.
        liees = annulations_liees(source, ecritures, periodes)
        calculees.extend(liees)
        ecritures.extend(liees)
    return calculees


def _ecriture_decidee(
    dossier: Dossier, base: LedgerService, decisions: DecisionRepository, ecriture_id: str
) -> Ecriture:
    ledger_a_jour = _ledger_avec_decisions(dossier, base, decisions)
    return next(e for e in ledger_a_jour.grand_livre(dossier.id) if e.id == ecriture_id)


def _decision_suivante(
    dossier: Dossier,
    ecriture_id: str,
    categorie: str,
    base: LedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
    decide_par: UserId,
    ecrire: EcrireDecisions,
) -> TransactionVue:
    """Enregistre une décision qui en remplace une déjà en vigueur."""
    courante = decisions.decision_courante(dossier.id, EcritureId(ecriture_id))
    en_vigueur = decision_en_vigueur(courante)
    if en_vigueur is None:
        raise HTTPException(status_code=409, detail="Cette opération n'a pas encore été classée.")
    ecriture = next((e for e in base.grand_livre(dossier.id) if e.id == ecriture_id), None)
    if ecriture is None:
        raise HTTPException(status_code=404, detail=f"Écriture inconnue : {ecriture_id}")
    if categorie != CATEGORIE_ANNULATION:
        resoudre_ecriture_a_trancher(
            ecriture,
            categorie,
            configuration_de(dossier).comptes_categories_statut(),
            charger_compte_par_categorie(),
        )
    decision = DecisionHumaine(
        dossier_id=dossier.id,
        ecriture_id=EcritureId(ecriture_id),
        categorie=categorie,
        etage_origine=en_vigueur.etage_origine,
        confiance_origine=en_vigueur.confiance_origine,
        decide_par=decide_par,
        decide_le=datetime.now(UTC),
        contexte=_contexte(
            ecriture, categorie, (en_vigueur.categorie, Etage.REVUE_HUMAINE.name, 1.0)
        ),
    )
    ecrire.ecrire([decision], _reclassements(dossier, base, [(EcritureId(ecriture_id), categorie)]))
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    ecritures_vues = ledger.grand_livre(dossier.id)
    ecriture_vue = next(e for e in ecritures_vues if e.id == ecriture_id)
    return _transaction_vue(
        ecriture_vue,
        justificatifs.a_un_justificatif(dossier.tenant_id, dossier.id, ecriture_vue.id),
        ecriture_vue.id in annulees(ecritures_vues),
        regime_tva=dossier.regime_tva,
        categorie=categorie,
    )


def _a_trancher_ou_refus(
    ecriture: Ecriture | None, ecriture_id: str, deja_traitees: AbstractSet[EcritureId]
) -> Ecriture:
    """Les refus de `_trancher`, pour une opération d'un lot."""
    if ecriture is None:
        raise HTTPException(status_code=404, detail="Cette opération est introuvable.")
    if ecriture.id in deja_traitees:
        raise HTTPException(status_code=409, detail="Cette opération a déjà été classée.")
    if not any(ligne.compte == COMPTE_ATTENTE for ligne in ecriture.lignes):
        raise HTTPException(status_code=409, detail="Cette opération n'est pas à classer.")
    return ecriture


def _trancher_groupe(
    dossier: Dossier,
    entree: DecisionsGroupeesEntree,
    base: LedgerService,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
    decide_par: UserId,
    ecrire: EcrireDecisions,
    ia: Mapping[str, PropositionIa],
) -> list[Ecriture]:
    """Tout ou rien : une seule opération refusée refuse le lot, avec sa
    raison, et rien n'est écrit."""
    ids = list(dict.fromkeys(entree.ecriture_ids))
    if not ids:
        raise HTTPException(status_code=400, detail="Aucune opération à confirmer.")
    if len(ids) > MAX_DECISIONS_GROUPEES:
        raise HTTPException(
            status_code=400,
            detail=f"Au plus {MAX_DECISIONS_GROUPEES} opérations à la fois.",
        )
    ecritures = base.grand_livre(dossier.id)
    par_id = {e.id: e for e in ecritures}
    deja_traitees = annulees(ecritures) | {
        d.ecriture_id for d in decisions.lister_decisions(dossier.id)
    }
    comptes = charger_compte_par_categorie()
    comptes_statut = configuration_de(dossier).comptes_categories_statut()
    maintenant = datetime.now(UTC)
    a_ecrire: list[DecisionHumaine] = []
    for ecriture_id in ids:
        ecriture = _a_trancher_ou_refus(
            par_id.get(EcritureId(ecriture_id)), ecriture_id, deja_traitees
        )
        proposition = propositions.obtenir(dossier.id, ecriture.id)
        if proposition is None:
            raise HTTPException(
                status_code=500,
                detail="Cette opération n'a pas de proposition d'origine.",
            )
        resoudre_ecriture_a_trancher(ecriture, entree.categorie, comptes_statut, comptes)
        a_ecrire.append(
            DecisionHumaine(
                dossier_id=dossier.id,
                ecriture_id=ecriture.id,
                categorie=entree.categorie,
                etage_origine=proposition.etage,
                confiance_origine=proposition.confiance,
                decide_par=decide_par,
                decide_le=maintenant,
                contexte=_contexte_proposition(
                    ecriture, proposition, entree.categorie, ia.get(cle_libelle(ecriture.libelle))
                ),
            )
        )
    ecrire.ecrire(
        a_ecrire, _reclassements(dossier, base, [(d.ecriture_id, d.categorie) for d in a_ecrire])
    )
    ledger_a_jour = _ledger_avec_decisions(dossier, base, decisions)
    voulues = {decision.ecriture_id for decision in a_ecrire}
    return [e for e in ledger_a_jour.grand_livre(dossier.id) if e.id in voulues]


def _photo_acceptee(fichier: UploadFile) -> bool:
    """Le type MIME d'un fichier choisi sur ordinateur est parfois vide ou
    `application/octet-stream`. L'extension suffit alors. Un texte reste refusé."""
    if fichier.content_type in _TYPES_IMAGE_ACCEPTES:
        return True
    if fichier.content_type not in (None, "", "application/octet-stream"):
        return False
    return Path(fichier.filename or "").suffix.lower() in _EXTENSIONS_IMAGE


def _joindre_justificatif(
    dossier: Dossier,
    ecriture_id: str,
    fichier: UploadFile,
    ledger: InMemoryLedgerService,
    justificatifs: JustificatifRepository,
) -> Ecriture:
    """doc 17 §9 Semaine 3, doc 19 §5.7 : « photo de justificatif au fil de
    l'eau, associée automatiquement à la transaction » — le contenu n'est
    jamais lu (pas d'OCR, doc 17 §8). Extrait de la route (doc 08 §2),
    même logique que `_trancher`.

    Lecture synchrone (`fichier.file.read()`, pas `await fichier.read()`) :
    `fichier.file` est un objet fichier synchrone standard
    (`SpooledTemporaryFile`), pas une coroutine — lecture bloquante, mais un
    JPEG de démo tient en mémoire sans souci."""
    ecriture = next((e for e in ledger.grand_livre(dossier.id) if e.id == ecriture_id), None)
    if ecriture is None:
        raise HTTPException(status_code=404, detail="Cette opération est introuvable.")
    if not _photo_acceptee(fichier):
        raise HTTPException(
            status_code=400, detail="Seules les photos sont acceptées (JPEG, PNG, WebP ou HEIC)."
        )
    contenu = fichier.file.read()
    extension = Path(fichier.filename or "").suffix or ".jpg"
    justificatifs.enregistrer(dossier.tenant_id, dossier.id, ecriture.id, contenu, extension)
    return ecriture


def _configurer_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        # 3000 est l'origine habituelle. 3001 sert quand ce port est déjà pris.
        allow_origins=[ORIGINE_FRONTEND_DEV, "http://localhost:3001"],
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["*"],
        # Lu par le front pour enregistrer un fichier sous le nom choisi par
        # le serveur (FEC : `<SIREN>FEC<AAAAMMJJ>.txt`, nom légal A.47 A-1).
        expose_headers=["Content-Disposition"],
    )


def _configurer_contexte_rls(app: FastAPI) -> None:
    """Pose le contexte RLS (doc 12 §1.1, `axelcompta/core/rls.py`) pour
    toute la durée de la requête — un middleware plutôt qu'une dépendance
    FastAPI classique : l'ordre de résolution des dépendances n'est pas une
    garantie assez forte pour un mécanisme de sécurité (rien ne force
    `DossiersDep`/`LedgerBaseDep` à être résolues après une dépendance de
    contexte). Le middleware, lui, encadre tout le traitement de la requête
    sans exception. Tolérant par construction (`identite_tolerante`, jamais
    de levée) : la décision d'autoriser ou non reste entièrement dans
    `_verifier_acces_dossier` et les dépendances existantes, jamais ici —
    un jeton absent ou invalide pose juste un contexte vide, RLS filtrera
    tout (aucune ligne visible), les routes elles-mêmes répondront 401/403
    comme avant."""

    @app.middleware("http")
    async def poser_contexte_rls(request: Request, call_next: Any) -> Any:
        identite = identite_tolerante(request.headers.get("authorization"))
        # Le compte de test (AXE-822) lit son portefeuille comme un
        # gestionnaire au niveau de la base ; l'API ne lui ouvre que les
        # routes de dossier, une à une (`get_identite`).
        tenant = identite and (identite.tenant_id or identite.lecteur_test_tenant)
        with contexte_identite(
            dossier_id=str(identite.dossier_id) if identite and identite.dossier_id else None,
            tenant_id=str(tenant) if tenant else None,
        ):
            return await call_next(request)


def _agregat_du_dossier(
    dossier: Dossier,
    ligne: LigneAgregat | None,
    base: LedgerService,
    decisions: DecisionRepository,
    provisions: ProvisionsClotureRepository,
    agregats: AgregatsRepository,
) -> AgregatStocke:
    """Le dossier est relu depuis la base ; seul un dossier périmé, ou jamais
    calculé, est recalculé. Si une écriture l'a périmé pendant le calcul, le
    résultat est servi mais pas gardé (voir `AgregatsRepository.enregistrer`)."""
    if ligne is not None and ligne.valeur is not None:
        return ligne.valeur
    valeur = calculer_agregat(dossier, base, decisions, provisions)
    agregats.enregistrer(
        dossier.tenant_id, dossier.id, valeur, None if ligne is None else ligne.version
    )
    return valeur


def _cache_perime(ligne: LigneAgregat | None, garde: SujetsGardes | None) -> bool:
    """Agrégat jamais calculé ou périmé, ou sujets gardés d'une autre version."""
    if ligne is None or ligne.valeur is None:
        return True
    return garde is None or not garde.valables(ligne.version)


def prechauffer_caches(engine: Engine, dossiers: Sequence[Dossier]) -> int:
    """Après la synchro (tâches planifiées, AXE-824) : recalcule les agrégats,
    les sujets de la file expert et les opérations classées des dossiers qui
    ont changé, pour que le premier affichage du matin lise des valeurs
    gardées. Retourne le nombre de dossiers recalculés pour la file."""
    base = PostgresLedgerService(engine)
    decisions = PostgresDecisionRepository(engine)
    provisions = PostgresProvisionsClotureRepository(engine)
    agregats = PostgresAgregatsRepository(engine)
    cache = PostgresCacheFileExpert(engine)
    ids = [dossier.id for dossier in dossiers]
    lignes = agregats.lire(ids)
    gardes = cache.lire(ids)
    a_refaire = [d for d in dossiers if _cache_perime(lignes.get(d.id), gardes.get(d.id))]
    for dossier in a_refaire:
        _agregat_du_dossier(dossier, lignes.get(dossier.id), base, decisions, provisions, agregats)
    sources = (
        base,
        decisions,
        PostgresJustificatifRepository(engine),
        PostgresPropositionRepository(engine),
    )
    _sujets_du_portefeuille(a_refaire, sources, agregats, cache)
    _operations_gardees(
        dossiers,
        base,
        decisions,
        PostgresPropositionRepository(engine),
        agregats,
        cache_operations_classees(engine),
    )
    return len(a_refaire)


def _agregats_portefeuille(
    dossiers: Sequence[Dossier],
    base: LedgerService,
    decisions: DecisionRepository,
    comptes: CompteRepository,
    signatures: SignatureRepository,
    provisions: ProvisionsClotureRepository,
    agregats: AgregatsRepository,
    comptes_bancaires: CompteBancaireRepository,
) -> list[DossierAgregat]:
    """Une lecture des agrégats gardés, une lecture des comptes (Supabase,
    tous les dossiers d'un coup), une des comptes bancaires à choisir, puis
    par dossier ce qui change sans écriture : les preuves de l'exercice et la
    date du jour."""
    ids = [dossier.id for dossier in dossiers]
    lignes = agregats.lire(ids)
    invitations = comptes.statuts(ids)
    preuves = _preuves_exercice(signatures, ids)
    a_choisir = comptes_bancaires.a_choisir(ids)
    tva = _tva_a_declarer(signatures, dossiers, datetime.now(UTC).date())
    resultat: list[DossierAgregat] = []
    for dossier in dossiers:
        invitation = invitations.get(dossier.id)
        resultat.append(
            _agregat(
                _agregat_du_dossier(
                    dossier, lignes.get(dossier.id), base, decisions, provisions, agregats
                ),
                dossier,
                _statut_invitation_vue(invitation.statut) if invitation else None,
                preuves.get(dossier.id, set()),
                a_choisir.get(dossier.id),
            ).model_copy(update=tva.get(dossier.id, {}))
        )
    return resultat


def _enregistrer_route_compte_de_test(app: FastAPI) -> None:
    @app.get("/lecteur-test/dossiers", response_model=list[DossierDeTestVue])
    def dossiers_du_compte_de_test(
        identite: IdentiteDep, dossiers: DossiersDep, base: LedgerBaseDep
    ) -> list[DossierDeTestVue]:
        """AXE-822 : l'écran « Quel dossier ? » du compte de test. Réservé à
        ce compte ; un gestionnaire ou un chauffeur reçoit 403."""
        if identite is None:
            raise HTTPException(status_code=401, detail="Authentification requise.")
        if identite.lecteur_test_tenant is None:
            raise HTTPException(status_code=403, detail="Réservé au compte de test.")
        return [
            DossierDeTestVue(
                dossier_id=d.id,
                nom=d.nom,
                forme_juridique=d.forme_juridique,
                nb_operations=sum(1 for e in base.grand_livre(d.id) if e.journal is Journal.BQ),
            )
            for d in dossiers.lister_par_tenant(identite.lecteur_test_tenant)
        ]


def _tva_a_declarer(
    signatures: SignatureRepository, dossiers: Sequence[Dossier], aujourd_hui: date
) -> dict[DossierId, dict[str, str | None]]:
    """AXE-805, pour tout le portefeuille en une lecture des preuves."""
    par_dossier = {d.id: periodes_du_dossier(d) for d in dossiers}
    types = sorted({type_preuve(p) for periodes in par_dossier.values() for p in periodes})
    if not types:
        return {}
    declarees = signatures.types_presents(list(par_dossier), types)
    resultat: dict[DossierId, dict[str, str | None]] = {}
    for dossier in dossiers:
        periode = prochaine_a_declarer(
            par_dossier[dossier.id], declarees.get(dossier.id, set()), aujourd_hui
        )
        if periode is None:
            continue
        jour = dossier.tva_jour_echeance
        resultat[dossier.id] = {
            "tva_a_declarer": periode.cle,
            "tva_echeance": echeance(periode, jour).isoformat() if jour else None,
        }
    return resultat


def _enregistrer_routes_dossiers(app: FastAPI) -> None:
    @app.get("/dossiers", response_model=list[DossierAgregat])
    def lister_dossiers(
        dossiers: DossiersDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        comptes: ComptesDep,
        signatures: SignaturesInpiDep,
        provisions: ProvisionsDep,
        agregats: AgregatsDep,
        tags: TagsDep,
        comptes_bancaires: ComptesBancairesDep,
        identite: IdentiteDep,
    ) -> list[DossierAgregat]:
        """Vue gestionnaire (doc 19 §2.1) : agrégats des dossiers **de son
        portefeuille** seulement (`tenant_id` du jeton), rien d'autre. Les
        montants viennent de la base (`agregats_dossier`, périmés par des
        triggers) : ouvrir la liste ne reparcourt pas le grand livre de
        chaque dossier."""
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        vues = _agregats_portefeuille(
            dossiers.lister_par_tenant(tenant_id),
            base,
            decisions,
            comptes,
            signatures,
            provisions,
            agregats,
            comptes_bancaires,
        )
        return _avec_tags(vues, etat_du_portefeuille(tags, tenant_id))


def _enregistrer_route_lecture_dossier(app: FastAPI) -> None:
    """La fiche d'un dossier. Le compte de test y laisse une trace (AXE-822)."""

    @app.get("/dossiers/{dossier_id}", response_model=DossierResume)
    def obtenir_dossier(
        request: Request,
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        comptes: ComptesDep,
        signatures: SignaturesInpiDep,
        avenants: AvenantsDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        consultations: ConsultationsDep,
    ) -> DossierResume:
        if identite is not None and identite.lecteur_test_tenant is not None:
            consultations.noter(dossier.id, identite.user_id, datetime.now(UTC))
        resume = _resume(
            dossier,
            ledger,
            comptes,
            signatures,
            _digifactory_branche(request.app),
            _provisions_saisies(dossier, provisions),
        )
        return resume.model_copy(
            update={
                "alerte_regime": alerte_option_ir(dossier),
                "regimes_a_venir": _regimes_a_venir(dossier, avenants.lister(dossier.id)),
                "paie_par_bulletin": configuration_de(dossier).paie_par_bulletin,
            }
        )


def _enregistrer_routes_revue(app: FastAPI) -> None:
    """La file à trancher : sa lecture, avec les propositions à jour, et
    « tout confirmer »."""

    @app.get("/dossiers/{dossier_id}/transactions", response_model=list[TransactionVue])
    def lister_transactions(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        justificatifs: JustificatifsDep,
        decisions: DecisionsDep,
        pipeline: PipelineDep,
        experts: ExpertsDep,
        propositions_ia: PropositionsIaDep,
    ) -> list[TransactionVue]:
        vues = _transactions_dossier(
            dossier,
            ledger,
            justificatifs,
            decisions.lister_decisions(dossier.id),
            pipeline,
            propositions_ia.lister(dossier.id, VERSION_PROMPT),
        )
        return _avec_reclassements_expert(vues, experts.decisions(dossier.id))

    @app.post("/dossiers/{dossier_id}/decisions-groupees", response_model=list[TransactionVue])
    def trancher_en_groupe(
        entree: DecisionsGroupeesEntree,
        dossier: DossierDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        propositions: PropositionsDep,
        justificatifs: JustificatifsDep,
        ecrire: EcrireDecisionsDep,
        identite: IdentiteDep,
        propositions_ia: PropositionsIaDep,
    ) -> list[TransactionVue]:
        """« Tout confirmer » : les mêmes contrôles que pour une décision
        seule, sur chaque opération, avant d'écrire quoi que ce soit ; puis
        toutes les décisions dans une seule transaction."""
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecritures = _trancher_groupe(
            dossier,
            entree,
            base,
            decisions,
            propositions,
            identite.user_id,
            ecrire,
            propositions_ia.lister(dossier.id, VERSION_PROMPT),
        )
        avec_photo = justificatifs.presents(dossier.tenant_id, dossier.id)
        return [_vue_tranchee(dossier, e, e.id in avec_photo, entree.categorie) for e in ecritures]


def _enregistrer_route_correction(app: FastAPI) -> None:
    """Corriger une décision : une nouvelle ligne, jamais une mutation."""

    @app.post(
        "/dossiers/{dossier_id}/transactions/{ecriture_id}/correction",
        response_model=TransactionVue,
    )
    def corriger_transaction(
        ecriture_id: str,
        entree: DecisionEntree,
        dossier: DossierDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        propositions: PropositionsDep,
        justificatifs: JustificatifsDep,
        ecrire: EcrireDecisionsDep,
        identite: IdentiteDep,
        propositions_ia: PropositionsIaDep,
    ) -> TransactionVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecriture = _corriger(
            dossier,
            ecriture_id,
            entree.categorie,
            base,
            decisions,
            propositions,
            identite.user_id,
            ecrire,
            propositions_ia.lister(dossier.id, VERSION_PROMPT),
        )
        return _vue_tranchee(
            dossier,
            ecriture,
            justificatifs.a_un_justificatif(dossier.tenant_id, dossier.id, ecriture.id),
            entree.categorie,
        )


def _enregistrer_routes_transactions(app: FastAPI) -> None:
    @app.post(
        "/dossiers/{dossier_id}/transactions/{ecriture_id}/decision",
        response_model=TransactionVue,
    )
    def trancher_transaction(
        ecriture_id: str,
        entree: DecisionEntree,
        dossier: DossierDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        propositions: PropositionsDep,
        justificatifs: JustificatifsDep,
        ecrire: EcrireDecisionsDep,
        identite: IdentiteDep,
        propositions_ia: PropositionsIaDep,
    ) -> TransactionVue:
        """Indiv qui tranche sa propre écriture (doc 19 §5.6, doc 19 §8bis :
        jeton obligatoire depuis le 2026-09-11) — `DossierDep` refuse déjà
        l'accès à un autre dossier."""
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecriture = _trancher(
            dossier,
            ecriture_id,
            entree.categorie,
            base,
            decisions,
            propositions,
            identite.user_id,
            ecrire,
            propositions_ia.lister(dossier.id, VERSION_PROMPT),
        )
        # `_trancher` refuse une écriture contre-passée : celle-ci ne l'est pas.
        return _vue_tranchee(
            dossier,
            ecriture,
            justificatifs.a_un_justificatif(dossier.tenant_id, dossier.id, ecriture.id),
            entree.categorie,
        )

    @app.post(
        "/dossiers/{dossier_id}/transactions/{ecriture_id}/justificatif",
        response_model=TransactionVue,
    )
    def joindre_justificatif(
        ecriture_id: str,
        fichier: UploadFile,
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        justificatifs: JustificatifsDep,
    ) -> TransactionVue:
        """Justificatif d'une transaction de **son propre dossier** (doc 19
        §5.7) : `DossierDep` refuse tout autre accès, gestionnaire compris."""
        ecriture = _joindre_justificatif(dossier, ecriture_id, fichier, ledger, justificatifs)
        return _transaction_vue(
            ecriture,
            justificatifs.a_un_justificatif(dossier.tenant_id, dossier.id, ecriture.id),
            ecriture.id in annulees(ledger.grand_livre(dossier.id)),
            regime_tva=dossier.regime_tva,
        )


def _enregistrer_routes_annulation(app: FastAPI) -> None:
    """Annuler : une nouvelle décision, l'ancienne reste en historique.
    L'opération redevient à traiter. La correction passe par
    `_enregistrer_route_correction`."""

    @app.post(
        "/dossiers/{dossier_id}/transactions/{ecriture_id}/annulation",
        response_model=TransactionVue,
    )
    def annuler_decision(
        ecriture_id: str,
        dossier: DossierDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        justificatifs: JustificatifsDep,
        ecrire: EcrireDecisionsDep,
        identite: IdentiteDep,
    ) -> TransactionVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        return _decision_suivante(
            dossier,
            ecriture_id,
            CATEGORIE_ANNULATION,
            base,
            decisions,
            justificatifs,
            identite.user_id,
            ecrire,
        )


_ROLES = frozenset({"admin", "membre", "lecture"})
# manuel : bouton sur la fiche. avant_cloture : N jours avant la fin.
# a_traiter : une opération attend depuis N jours (AXE-808).
_DECLENCHEURS = frozenset({"manuel", *DECLENCHEURS_AUTO})
_CANAUX = frozenset({"sms", "mail", "appel"})


class MembrePortefeuille(BaseModel):
    email: str
    role: str
    statut: str  # "invité" tant que le lien n'est pas ouvert, "actif" ensuite


class InvitationMembreEntree(BaseModel):
    email: str
    role: str = "membre"


class ConnexionDossierVue(BaseModel):
    dossier_id: str
    nom: str
    statut: str  # actif | a_renouveler | expire | jamais_connecte
    sante: str  # ok | en_pause | sans_acces | auth_requise | jamais_connecte
    expire_le: str | None
    jours_restants: int | None
    dernier_rafraichissement: str | None
    relance: str  # mode effectif : auto | manuel
    relance_propre: bool  # exception au mode du portefeuille


class ConnexionsBancairesVue(BaseModel):
    """doc 14 §2.2 : l'état des connexions bancaires du portefeuille."""

    relance_portefeuille: str
    compteurs: dict[str, int]
    a_reconnecter: int  # banque qui demande de confirmer la connexion
    dossiers: list[ConnexionDossierVue]


class RelanceEntree(BaseModel):
    mode: str | None  # "auto" | "manuel" ; None pour un dossier : suit le portefeuille


class NomPortefeuille(BaseModel):
    nom: str


class RegleEntree(BaseModel):
    libelle: str
    message: str
    canaux: list[str]
    portee: str = "tous"
    dossier_ids: list[str] = []
    declencheur: str = "manuel"
    jours_avant: int | None = None


class RegleVue(BaseModel):
    id: str
    libelle: str
    message: str
    canaux: list[str]
    portee: str
    dossier_ids: list[str]
    declencheur: str
    jours_avant: int | None
    actif: bool = True


class RegleMaj(BaseModel):
    message: str | None = None
    canaux: list[str] | None = None
    portee: str | None = None
    dossier_ids: list[str] | None = None
    declencheur: str | None = None
    jours_avant: int | None = None
    actif: bool | None = None


class RappelEntree(BaseModel):
    regle_id: str
    dossier_id: str


class RappelVue(BaseModel):
    id: str
    dossier_id: str | None
    regle_id: str | None
    message: str
    canal: str
    cree_le: str


def _role_membre(tenant_id: TenantId, email: str) -> str:
    """Sans ligne, le compte déjà là est admin : les premiers gestionnaires
    existaient avant la table des droits."""
    with _engine().connect() as connexion:
        appliquer_rls(connexion)
        ligne = connexion.execute(
            select(droits_membre.c.role).where(
                droits_membre.c.tenant_id == str(tenant_id),
                droits_membre.c.email == email.lower(),
            )
        ).first()
    return ligne.role if ligne else "admin"


def _statut_membre(comptes: CompteRepository, tenant_id: str, email: str) -> str:
    """« actif » une fois le lien ouvert, « invité » tant qu'il ne l'est pas.
    Un e-mail absent du fournisseur de comptes n'a pas accepté."""
    for membre in comptes.membres(tenant_id):
        if membre.email.lower() == email.lower():
            return "actif" if membre.accepte else "invité"
    return "invité"


def _exiger_admin(identite: IdentiteAuthentifiee, tenant_id: TenantId) -> None:
    if _role_membre(tenant_id, identite.email) != "admin":
        raise HTTPException(status_code=403, detail="Réservé à un administrateur.")


def get_role_membre(identite: IdentiteDep) -> str:
    """Rôle de l'appelant dans son portefeuille. En dépendance pour que la
    suite rapide le surcharge sans ouvrir Postgres."""
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    return _role_membre(tenant_id, identite.email)


RoleMembreDep = Annotated[str, Depends(get_role_membre)]

# AXE-812 (décision du 6 nov.) : MFA native de Supabase. Ces rôles n'ouvrent
# le portefeuille qu'avec un jeton `aal2` (code TOTP vérifié dans la session).
# `expert_comptable` arrive avec AXE-800.
ROLES_MFA_OBLIGATOIRE = frozenset({"admin", "expert_comptable"})
MESSAGE_MFA_REQUISE = "Activez la double authentification pour continuer."
# Ce qu'un compte sans `aal2` peut encore appeler : savoir qu'il doit
# s'enrôler, et tracer sa connexion. L'enrôlement lui-même passe par
# Supabase Auth, pas par cette API.
_ROUTES_SANS_MFA = frozenset({("GET", "/portefeuille/moi"), ("POST", "/session/connexion")})


def get_role_appelant(identite: IdentiteDep) -> str | None:
    """Rôle de l'appelant dans son portefeuille, `None` s'il n'en a pas
    (chauffeur). En dépendance pour que la suite rapide le surcharge."""
    if identite is None or identite.tenant_id is None:
        return None
    return _role_membre(identite.tenant_id, identite.email)


RoleAppelantDep = Annotated[str | None, Depends(get_role_appelant)]


def mfa_requise(role: str | None, identite: IdentiteAuthentifiee | None) -> bool:
    return role in ROLES_MFA_OBLIGATOIRE and identite is not None and identite.aal != "aal2"


def exiger_double_authentification(
    request: Request, identite: IdentiteDep, role: RoleAppelantDep
) -> None:
    """AXE-812 : appliqué à toute l'API. Un admin (ou un expert-comptable)
    connecté sans code n'atteint que `_ROUTES_SANS_MFA` : 403, et l'écran
    l'envoie s'enrôler ou saisir son code."""
    if not mfa_requise(role, identite):
        return
    chemin = getattr(request.scope.get("route"), "path", request.url.path)
    if (request.method, chemin) in _ROUTES_SANS_MFA:
        return
    raise HTTPException(status_code=403, detail=MESSAGE_MFA_REQUISE)


def _exiger_ecriture(role: str, detail: str) -> None:
    """doc 19 §2.1 : Lecture consulte, n'invite pas et ne relance pas."""
    if role in {"lecture", "retire"}:
        raise HTTPException(status_code=403, detail=detail)


def _ecrire_role(tenant_id: TenantId, email: str, role: str) -> None:
    """Upsert : réinviter ou changer le rôle d'un membre déjà présent ne
    bute pas sur la clé primaire."""
    with _engine().begin() as connexion:
        appliquer_rls(connexion)
        connexion.execute(
            pg_insert(droits_membre)
            .values(tenant_id=str(tenant_id), email=email, role=role)
            .on_conflict_do_update(
                index_elements=[droits_membre.c.tenant_id, droits_membre.c.email],
                set_={"role": role},
            )
        )


def get_ecrire_role() -> Callable[[TenantId, str, str], None]:
    """Dépendance : écrire un rôle dans `droits_membre` (Postgres). La suite
    rapide la remplace pour ne pas ouvrir de base."""
    return _ecrire_role


EcrireRoleDep = Annotated[Callable[[TenantId, str, str], None], Depends(get_ecrire_role)]


def _rappel_vue(ligne: Row[Any]) -> RappelVue:
    return RappelVue(
        id=ligne.id,
        dossier_id=ligne.dossier_id,
        regle_id=ligne.regle_id,
        message=ligne.message,
        canal=ligne.canal,
        cree_le=ligne.cree_le.isoformat(),
    )


def _regle_vue(ligne: Row[Any]) -> RegleVue:
    return RegleVue(
        id=ligne.id,
        libelle=ligne.libelle,
        message=ligne.message,
        canaux=list(ligne.canaux),
        portee=ligne.portee,
        dossier_ids=list(ligne.dossier_ids or []),
        declencheur=ligne.declencheur,
        jours_avant=ligne.jours_avant,
        actif=bool(ligne.actif),
    )


def _enregistrer_route_categorisation(app: FastAPI) -> None:
    @app.get("/portefeuille/categorisation", response_model=CategorisationVue)
    def lire_categorisation(
        identite: IdentiteDep,
        etat: Annotated[EtatCategorisation, Depends(get_etat_categorisation)],
        lots_llm: LotsLlmDep,
    ) -> CategorisationVue:
        """AXE-825 : le modèle est-il chargé ? Sinon, la catégorisation est
        dégradée et la synchro ne tourne pas."""
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return CategorisationVue(
            modele_charge=etat.modele_charge,
            raison=etat.raison,
            llm=_activite_llm(tenant_id, lots_llm),
        )


def _activite_llm(tenant_id: TenantId, lots_llm: LotsLlm) -> ActiviteLlmVue | None:
    """Éteint (`AXELCOMPTA_LLM_ACTIF` absent) : pas de ligne. Le coût reste
    interne : la ligne ne dit que le nombre de libellés."""
    if not llm_actif():
        return None
    maintenant = datetime.now(UTC)
    return ActiviteLlmVue(
        libelles=libelles_du_mois(lots_llm.lister(debut_du_mois(maintenant)), tenant_id, maintenant)
    )


def _enregistrer_routes_portefeuille(app: FastAPI) -> None:
    @app.get("/portefeuille", response_model=NomPortefeuille)
    def lire_portefeuille(dossiers: DossiersDep, identite: IdentiteDep) -> NomPortefeuille:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        tenant = dossiers.obtenir_tenant(tenant_id)
        return NomPortefeuille(nom=tenant.nom if tenant else "")

    @app.patch("/portefeuille", response_model=NomPortefeuille)
    def renommer_portefeuille(
        entree: NomPortefeuille, dossiers: DossiersDep, identite: IdentiteDep
    ) -> NomPortefeuille:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        _exiger_admin(identite, tenant_id)
        nom = entree.nom.strip()
        if not nom:
            raise HTTPException(status_code=400, detail="Le nom est vide.")
        dossiers.renommer_tenant(tenant_id, nom)
        return NomPortefeuille(nom=nom)

    @app.post("/dossiers/{dossier_id}/retirer")
    def retirer_dossier(
        dossier: DossierPortefeuilleDep,
        dossiers: DossiersDep,
        identite: IdentiteDep,
    ) -> dict[str, str]:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        _exiger_admin(identite, tenant_id)
        dossiers.retirer(dossier.id)
        return {"dossier_id": dossier.id}

    @app.get("/portefeuille/retires")
    def lister_dossiers_retires(
        dossiers: DossiersDep, identite: IdentiteDep
    ) -> list[dict[str, str]]:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return [
            {"dossier_id": str(dossier.id), "nom": dossier.nom}
            for dossier in dossiers.lister_retires(tenant_id)
        ]

    @app.post("/dossiers/{dossier_id}/restaurer")
    def restaurer_dossier(
        dossier_id: str,
        dossiers: DossiersDep,
        identite: IdentiteDep,
    ) -> dict[str, str]:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        _exiger_admin(identite, tenant_id)
        dossier = dossiers.obtenir(DossierId(dossier_id))
        if dossier is None or dossier.tenant_id != tenant_id or dossier.retire_le is None:
            raise HTTPException(status_code=404, detail="Dossier retiré introuvable.")
        dossiers.restaurer(dossier.id)
        return {"dossier_id": dossier.id}


class TagVue(BaseModel):
    nom: str
    description: str


class ReglageTagsVue(BaseModel):
    """Tags du portefeuille et, par traitement, ceux qui en excluent."""

    tags: list[TagVue]
    traitements: dict[str, str]
    exclusions: dict[str, list[str]]


class NouveauTag(BaseModel):
    nom: str
    description: str = ""


class PoseDeTags(BaseModel):
    """Pose ou retrait en lot depuis la liste Entreprises."""

    dossier_ids: list[str]
    pose: bool = True


class ReglageExclusion(BaseModel):
    tags: list[str]


def _avec_tags(vues: list[DossierAgregat], etat: EtatTags) -> list[DossierAgregat]:
    """AXE-829 : tags de chaque dossier et sortie des compteurs."""
    return [
        vue.model_copy(
            update={
                "tags": sorted(etat.tags_de(DossierId(vue.dossier_id))),
                "exclu_compteurs": etat.exclu(DossierId(vue.dossier_id), "compteurs"),
            }
        )
        for vue in vues
    ]


def _reglage_tags_vue(depot: TagsRepository, tenant_id: TenantId) -> ReglageTagsVue:
    return ReglageTagsVue(
        tags=[TagVue(nom=t.nom, description=t.description) for t in depot.lister_tags(tenant_id)],
        traitements=dict(TRAITEMENTS),
        exclusions={k: sorted(v) for k, v in depot.exclusions(tenant_id).items()},
    )


def _gestionnaire_qui_ecrit(
    identite: IdentiteAuthentifiee | None, role: str
) -> tuple[TenantId, IdentiteAuthentifiee]:
    """Rôle admin ou membre, jamais lecture (AXE-701)."""
    tenant_id, identite_ok = _verifier_acces_gestionnaire(identite)
    _exiger_ecriture(role, "Le rôle lecture ne pose pas de tags.")
    return tenant_id, identite_ok


def _dossiers_du_portefeuille(
    dossiers: DossierRepository, tenant_id: TenantId, ids: Sequence[str]
) -> list[DossierId]:
    trouves = []
    for brut in ids:
        dossier = dossiers.obtenir(DossierId(brut))
        if dossier is None or dossier.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Dossier introuvable.")
        trouves.append(dossier.id)
    return trouves


def _enregistrer_routes_tags(app: FastAPI) -> None:
    @app.get("/tags", response_model=ReglageTagsVue)
    def lire_tags(tags: TagsDep, identite: IdentiteDep) -> ReglageTagsVue:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _reglage_tags_vue(tags, tenant_id)

    @app.post("/tags", response_model=ReglageTagsVue)
    def creer_tag(
        corps: NouveauTag, tags: TagsDep, role: RoleMembreDep, identite: IdentiteDep
    ) -> ReglageTagsVue:
        tenant_id, _identite = _gestionnaire_qui_ecrit(identite, role)
        tags.creer_tag(Tag(tenant_id, nom_de_tag(corps.nom), corps.description.strip()))
        return _reglage_tags_vue(tags, tenant_id)

    @app.post("/tags/{tag}/dossiers", status_code=204)
    def poser_tags(
        tag: str,
        corps: PoseDeTags,
        dossiers: DossiersDep,
        tags: TagsDep,
        role: RoleMembreDep,
        identite: IdentiteDep,
    ) -> None:
        """Pose (ou retire, `pose: false`) un tag sur un ou plusieurs
        dossiers. Chaque geste est un événement daté et signé."""
        tenant_id, identite_ok = _gestionnaire_qui_ecrit(identite, role)
        maintenant = datetime.now(UTC)
        for dossier_id in _dossiers_du_portefeuille(dossiers, tenant_id, corps.dossier_ids):
            geste = tags.poser if corps.pose else tags.retirer
            geste(tenant_id, dossier_id, tag, identite_ok.user_id, maintenant)

    @app.put("/tags/exclusions/{traitement}", response_model=ReglageTagsVue)
    def regler_exclusion(
        traitement: str,
        corps: ReglageExclusion,
        tags: TagsDep,
        role: RoleMembreDep,
        identite: IdentiteDep,
    ) -> ReglageTagsVue:
        tenant_id, identite_ok = _gestionnaire_qui_ecrit(identite, role)
        tags.regler_exclusion(
            tenant_id,
            traitement,
            frozenset(corps.tags),
            identite_ok.user_id,
            datetime.now(UTC),
        )
        return _reglage_tags_vue(tags, tenant_id)


_URGENCE = {"expire": 0, "a_renouveler": 1, "jamais_connecte": 3, "actif": 4}


def _connexion_vue(
    dossier: Dossier, tenant: Tenant | None, releve: ReleveConsentement | None, aujourd_hui: date
) -> ConnexionDossierVue:
    expire_le = releve.expire_le if releve else None
    rafraichi = releve.dernier_rafraichissement if releve else None
    return ConnexionDossierVue(
        dossier_id=dossier.id,
        nom=dossier.nom,
        statut=classer(expire_le, aujourd_hui).value,
        sante=(releve.sante if releve else SanteConnexion.JAMAIS_CONNECTE).value,
        expire_le=expire_le.isoformat() if expire_le else None,
        jours_restants=(expire_le - aujourd_hui).days if expire_le else None,
        dernier_rafraichissement=rafraichi.isoformat() if rafraichi else None,
        relance=mode_effectif(dossier, tenant),
        relance_propre=dossier.relance_consentement is not None,
    )


def _ordre_urgence(vue: ConnexionDossierVue) -> tuple[int, int, str]:
    """Connexion cassée et expirée d'abord, puis les échéances les plus proches."""
    rang = 0 if vue.sante == "auth_requise" else _URGENCE.get(vue.statut, 5)
    return rang, vue.jours_restants if vue.jours_restants is not None else 10_000, vue.nom


def _connexions_bancaires(
    dossiers: tuple[Dossier, ...],
    tenant: Tenant | None,
    releves: dict[DossierId, ReleveConsentement],
    aujourd_hui: date,
) -> ConnexionsBancairesVue:
    vues = sorted(
        (_connexion_vue(d, tenant, releves.get(d.id), aujourd_hui) for d in dossiers),
        key=_ordre_urgence,
    )
    compteurs = {statut: 0 for statut in _URGENCE}
    for vue in vues:
        compteurs[vue.statut] += 1
    return ConnexionsBancairesVue(
        relance_portefeuille=tenant.relance_consentement if tenant else "auto",
        compteurs=compteurs,
        a_reconnecter=sum(1 for vue in vues if vue.sante == "auth_requise"),
        dossiers=vues,
    )


def _enregistrer_routes_connexions(app: FastAPI) -> None:
    @app.get("/portefeuille/connexions-bancaires", response_model=ConnexionsBancairesVue)
    def lire_connexions(
        dossiers: DossiersDep, consentements: ConsentementsDep, identite: IdentiteDep
    ) -> ConnexionsBancairesVue:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        liste = dossiers.lister_par_tenant(tenant_id)
        return _connexions_bancaires(
            liste,
            dossiers.obtenir_tenant(tenant_id),
            consentements.lister([d.id for d in liste]),
            date.today(),
        )

    @app.put("/portefeuille/relance-consentement", response_model=RelanceEntree)
    def regler_relance_portefeuille(
        entree: RelanceEntree, dossiers: DossiersDep, identite: IdentiteDep, role: RoleMembreDep
    ) -> RelanceEntree:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        if role != "admin":
            raise HTTPException(status_code=403, detail="Réservé à un administrateur.")
        if entree.mode not in MODES_RELANCE:
            raise HTTPException(status_code=400, detail="Mode attendu : auto ou manuel.")
        dossiers.regler_relance_tenant(tenant_id, entree.mode)
        return entree

    @app.put("/dossiers/{dossier_id}/relance-consentement", response_model=RelanceEntree)
    def regler_relance_dossier(
        entree: RelanceEntree,
        dossier: DossierPortefeuilleDep,
        dossiers: DossiersDep,
        role: RoleMembreDep,
    ) -> RelanceEntree:
        _exiger_ecriture(role, "La lecture seule ne change pas les relances.")
        if entree.mode is not None and entree.mode not in MODES_RELANCE:
            raise HTTPException(status_code=400, detail="Mode attendu : auto, manuel ou aucun.")
        dossiers.regler_relance_dossier(dossier.id, entree.mode)
        return entree


def _enregistrer_routes_rappels(app: FastAPI) -> None:
    @app.get("/rappels", response_model=list[RappelVue])
    def lister_rappels(identite: IdentiteDep) -> list[RappelVue]:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        with _engine().connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(rappels)
                .where(rappels.c.tenant_id == str(tenant_id))
                .order_by(rappels.c.cree_le.desc())
            ).all()
        return [_rappel_vue(ligne) for ligne in lignes]


def _enregistrer_route_declencher_rappel(app: FastAPI) -> None:
    """Un rappel déclenché depuis la fiche d'une entreprise (AXE-808)."""

    @app.post("/rappels", response_model=RappelVue)
    def declencher_rappel(
        entree: RappelEntree,
        identite: IdentiteDep,
        role: RoleMembreDep,
        envois: EnvoisDep,
        branchements: BranchementsDep,
        file: DemandesJobsDep,
    ) -> RappelVue:
        """Enregistre le rappel, et un envoi par canal branché (AXE-808) que
        le worker envoie. L'appel téléphonique reste à brancher."""
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture seule ne déclenche pas de rappel.")
        with _engine().connect() as connexion:
            appliquer_rls(connexion)
            regle = connexion.execute(
                select(regles_rappel).where(
                    regles_rappel.c.id == entree.regle_id,
                    regles_rappel.c.tenant_id == str(tenant_id),
                )
            ).first()
        if regle is None:
            raise HTTPException(status_code=404, detail="Règle introuvable.")
        vue = RappelVue(
            id=str(uuid.uuid4()),
            dossier_id=entree.dossier_id,
            regle_id=regle.id,
            message=regle.message,
            canal=",".join(regle.canaux),
            cree_le=datetime.now(UTC).isoformat(),
        )
        with _engine().begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(rappels).values(
                    id=vue.id,
                    tenant_id=str(tenant_id),
                    dossier_id=entree.dossier_id,
                    regle_id=regle.id,
                    message=regle.message,
                    canal=vue.canal,
                    cree_le=datetime.now(UTC),
                )
            )
        a_envoyer = envois_du_rappel(
            vue.id,
            tenant_id,
            DossierId(entree.dossier_id),
            regle.message,
            list(regle.canaux),
            list(types_branches(branchements.lister(tenant_id))),
            datetime.now(UTC),
        )
        if a_envoyer:
            envois.creer(a_envoyer)
            file.demander(str(tenant_id), TYPE_RAPPELS)
        return vue


# Posées une fois par portefeuille, par un admin. Le libellé est unique :
# deux ouvertures simultanées de /rappels ne créent pas de doublon.
REGLES_PREFAITES: tuple[dict[str, object], ...] = (
    {
        "libelle": "15 jours avant la clôture",
        "message": "La clôture approche. Relis les pièces de l'exercice.",
        "canaux": ["mail"],
        "portee": "tous",
        "dossier_ids": [],
        "declencheur": "avant_cloture",
        "jours_avant": 15,
    },
    {
        "libelle": "Compte à ouvrir",
        "message": "Ouvre ton compte pour suivre l'exercice.",
        "canaux": ["mail", "sms"],
        "portee": "tous",
        "dossier_ids": [],
        "declencheur": "manuel",
        "jours_avant": None,
    },
    {
        "libelle": "Pièces à compléter",
        "message": "Il reste des pièces à ajouter avant la clôture.",
        "canaux": ["sms"],
        "portee": "tous",
        "dossier_ids": [],
        "declencheur": "manuel",
        "jours_avant": None,
    },
)


def _assurer_regles_prefaites(tenant_id: TenantId) -> None:
    """Crée les règles manquantes. `ON CONFLICT DO NOTHING` : un second
    appel, même concurrent, ne rajoute aucune ligne."""
    with _engine().begin() as connexion:
        appliquer_rls(connexion)
        for modele in REGLES_PREFAITES:
            connexion.execute(
                pg_insert(regles_rappel)
                .values(
                    id=str(uuid.uuid4()),
                    tenant_id=str(tenant_id),
                    libelle=modele["libelle"],
                    message=modele["message"],
                    canaux=modele["canaux"],
                    portee=modele["portee"],
                    dossier_ids=modele["dossier_ids"],
                    declencheur=modele["declencheur"],
                    jours_avant=modele["jours_avant"],
                )
                .on_conflict_do_nothing(constraint="uq_regles_rappel_tenant_libelle")
            )


def lister_regles(identite: IdentiteDep, role: RoleMembreDep) -> list[RegleVue]:
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    # Un membre ou une lecture ne crée rien : il voit la liste telle quelle.
    if role == "admin":
        _assurer_regles_prefaites(tenant_id)
    with _engine().connect() as connexion:
        appliquer_rls(connexion)
        lignes = connexion.execute(
            select(regles_rappel).where(regles_rappel.c.tenant_id == str(tenant_id))
        ).all()
    return [_regle_vue(ligne) for ligne in lignes]


def creer_regle(entree: RegleEntree, identite: IdentiteDep) -> RegleVue:
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    _exiger_admin(identite, tenant_id)
    canaux = [canal for canal in entree.canaux if canal in _CANAUX]
    libelle = entree.libelle.strip()
    message = entree.message.strip()
    if not libelle or not message or not canaux:
        raise HTTPException(status_code=400, detail="Libellé, message et au moins un canal.")
    if entree.declencheur not in _DECLENCHEURS or entree.portee not in {
        "tous",
        "selection",
    }:
        raise HTTPException(status_code=400, detail="Déclencheur ou portée inconnue.")
    if entree.declencheur in DECLENCHEURS_AUTO and not entree.jours_avant:
        raise HTTPException(status_code=400, detail="Indique le nombre de jours.")
    if entree.portee == "selection" and not entree.dossier_ids:
        raise HTTPException(status_code=400, detail="Choisissez au moins une entreprise.")
    vue = RegleVue(
        id=str(uuid.uuid4()),
        libelle=libelle,
        message=message,
        canaux=canaux,
        portee=entree.portee,
        dossier_ids=entree.dossier_ids if entree.portee == "selection" else [],
        declencheur=entree.declencheur,
        jours_avant=entree.jours_avant if entree.declencheur in DECLENCHEURS_AUTO else None,
    )
    try:
        with _engine().begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(regles_rappel).values(
                    id=vue.id,
                    tenant_id=str(tenant_id),
                    libelle=libelle,
                    message=message,
                    canaux=canaux,
                    portee=vue.portee,
                    dossier_ids=vue.dossier_ids,
                    declencheur=vue.declencheur,
                    jours_avant=vue.jours_avant,
                    actif=True,
                )
            )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Une règle porte déjà ce libellé.") from exc
    return vue


def _enregistrer_routes_regles(app: FastAPI) -> None:
    app.get("/regles-rappel", response_model=list[RegleVue])(lister_regles)
    app.post("/regles-rappel", response_model=RegleVue)(creer_regle)

    app.patch("/regles-rappel/{regle_id}", response_model=RegleVue)(modifier_regle)
    app.delete("/regles-rappel/{regle_id}", status_code=204)(supprimer_regle)


def _valeur_message(message: str) -> str:
    propre = message.strip()
    if not propre:
        raise HTTPException(status_code=400, detail="Le message est vide.")
    return propre


def _valeur_canaux(canaux: list[str]) -> list[str]:
    gardes = [canal for canal in canaux if canal in _CANAUX]
    if not gardes:
        raise HTTPException(status_code=400, detail="Au moins un canal.")
    return gardes


def _valeur_portee(portee: str, dossier_ids: list[str]) -> dict[str, object]:
    if portee not in {"tous", "selection"}:
        raise HTTPException(status_code=400, detail="Portée inconnue.")
    if portee == "selection" and not dossier_ids:
        raise HTTPException(status_code=400, detail="Choisissez au moins une entreprise.")
    return {"portee": portee, "dossier_ids": dossier_ids if portee == "selection" else []}


def _valeur_declencheur(declencheur: str, jours_avant: int | None) -> dict[str, object]:
    if declencheur not in _DECLENCHEURS:
        raise HTTPException(status_code=400, detail="Déclencheur inconnu.")
    if declencheur in DECLENCHEURS_AUTO and not jours_avant:
        raise HTTPException(status_code=400, detail="Indique le nombre de jours.")
    jours = jours_avant if declencheur in DECLENCHEURS_AUTO else None
    return {"declencheur": declencheur, "jours_avant": jours}


def _valeurs_regle(entree: RegleMaj) -> dict[str, object]:
    valeurs: dict[str, object] = {}
    if entree.message is not None:
        valeurs["message"] = _valeur_message(entree.message)
    if entree.canaux is not None:
        valeurs["canaux"] = _valeur_canaux(entree.canaux)
    if entree.portee is not None:
        valeurs.update(_valeur_portee(entree.portee, entree.dossier_ids or []))
    if entree.declencheur is not None:
        valeurs.update(_valeur_declencheur(entree.declencheur, entree.jours_avant))
    if entree.actif is not None:
        valeurs["actif"] = entree.actif
    if not valeurs:
        raise HTTPException(status_code=400, detail="Rien à modifier.")
    return valeurs


def modifier_regle(regle_id: str, entree: RegleMaj, identite: IdentiteDep) -> RegleVue:
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    _exiger_admin(identite, tenant_id)
    valeurs = _valeurs_regle(entree)
    with _engine().begin() as connexion:
        appliquer_rls(connexion)
        resultat = connexion.execute(
            update(regles_rappel)
            .where(regles_rappel.c.id == regle_id, regles_rappel.c.tenant_id == str(tenant_id))
            .values(**valeurs)
            .returning(regles_rappel)
        ).first()
    if resultat is None:
        raise HTTPException(status_code=404, detail="Règle introuvable.")
    return _regle_vue(resultat)


def supprimer_regle(regle_id: str, identite: IdentiteDep) -> None:
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    _exiger_admin(identite, tenant_id)
    with _engine().begin() as connexion:
        appliquer_rls(connexion)
        connexion.execute(
            update(rappels)
            .where(rappels.c.regle_id == regle_id, rappels.c.tenant_id == str(tenant_id))
            .values(regle_id=None)
        )
        resultat = connexion.execute(
            delete(regles_rappel).where(
                regles_rappel.c.id == regle_id, regles_rappel.c.tenant_id == str(tenant_id)
            )
        )
    if resultat.rowcount == 0:
        raise HTTPException(status_code=404, detail="Règle introuvable.")


def _enregistrer_routes_membres(app: FastAPI) -> None:
    @app.get("/portefeuille/membres", response_model=list[MembrePortefeuille])
    def lister_membres(comptes: ComptesDep, identite: IdentiteDep) -> list[MembrePortefeuille]:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        vues: list[MembrePortefeuille] = []
        for membre in comptes.membres(str(tenant_id)):
            role = _role_membre(tenant_id, membre.email)
            if role == "retire":
                continue
            vues.append(
                MembrePortefeuille(
                    email=membre.email,
                    role=role,
                    statut="actif" if membre.accepte else "invité",
                )
            )
        return vues

    @app.post("/portefeuille/membres", response_model=MembrePortefeuille)
    def inviter_membre(
        entree: InvitationMembreEntree, comptes: ComptesDep, identite: IdentiteDep
    ) -> MembrePortefeuille:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        _exiger_admin(identite, tenant_id)
        if entree.role not in _ROLES:
            raise HTTPException(status_code=400, detail="Rôle inconnu.")
        email = entree.email.strip().lower()
        # Le droit d'abord : un compte sans ligne est admin (`_role_membre`),
        # il ne doit jamais exister avant son rôle. L'upsert laisse un nouvel
        # essai passer si l'invitation a échoué après.
        _ecrire_role(tenant_id, email, entree.role)
        comptes.inviter_membre(str(tenant_id), email, entree.role)
        return MembrePortefeuille(email=email, role=entree.role, statut="invité")

    @app.patch("/portefeuille/membres", response_model=MembrePortefeuille)
    def changer_role(
        entree: InvitationMembreEntree, comptes: ComptesDep, identite: IdentiteDep
    ) -> MembrePortefeuille:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        _exiger_admin(identite, tenant_id)
        if entree.role not in _ROLES:
            raise HTTPException(status_code=400, detail="Rôle inconnu.")
        email = entree.email.strip().lower()
        _ecrire_role(tenant_id, email, entree.role)
        return MembrePortefeuille(
            email=email, role=entree.role, statut=_statut_membre(comptes, str(tenant_id), email)
        )

    app.delete("/portefeuille/membres", status_code=204)(retirer_membre)


def retirer_membre(
    entree: InvitationMembreEntree, comptes: ComptesDep, identite: IdentiteDep
) -> None:
    """Garde la ligne de droit : sans ligne, `_role_membre` rendrait le compte admin."""
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    _exiger_admin(identite, tenant_id)
    email = entree.email.strip().lower()
    if email == identite.email.lower():
        raise HTTPException(
            status_code=400, detail="Vous ne pouvez pas retirer votre propre accès."
        )
    admins = [
        membre.email
        for membre in comptes.membres(str(tenant_id))
        if _role_membre(tenant_id, membre.email) == "admin"
    ]
    if email in [admin.lower() for admin in admins] and len(admins) <= 1:
        raise HTTPException(status_code=400, detail="Il reste un seul administrateur.")
    _ecrire_role(tenant_id, email, "retire")


def _enregistrer_routes_invitation(app: FastAPI) -> None:
    @app.post("/invitations/en-masse", response_model=InvitationsMasseVue)
    def inviter_en_masse(
        entree: InvitationsMasseEntree,
        dossiers: DossiersDep,
        comptes: ComptesDep,
        identite: IdentiteDep,
        role: RoleMembreDep,
    ) -> InvitationsMasseVue:
        """doc 19 §3.1 : le gestionnaire invite ses chauffeurs depuis une base
        clients, pas seulement un par un. Jusqu'à `MAX_INVITATIONS_PAR_LOT`
        lignes, résultat ligne par ligne."""
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture seule n'invite pas.")
        du_portefeuille = {str(d.id) for d in dossiers.lister_par_tenant(tenant_id)}
        vue = _inviter_en_masse(entree.invitations, du_portefeuille, comptes)
        return vue

    @app.post("/dossiers/{dossier_id}/inviter", response_model=InvitationVue)
    def inviter_chauffeur(
        entree: InvitationEntree,
        dossier: DossierPortefeuilleDep,
        comptes: ComptesDep,
        role: RoleMembreDep,
    ) -> InvitationVue:
        """doc 17 §9 bloc B, doc 19 §3.1 : le gestionnaire invite, jamais
        de self-signup (disable_signup, vérifié 2026-09-07). Envoie un
        vrai e-mail via Supabase Auth — pas un simulateur. Uniquement pour un
        dossier de son propre portefeuille (`DossierPortefeuilleDep`)."""
        _exiger_ecriture(role, "La lecture seule n'invite pas.")
        invitation = comptes.inviter(dossier.id, entree.email)
        return InvitationVue(
            dossier_id=invitation.dossier_id,
            email=invitation.email,
            statut=_statut_invitation_vue(invitation.statut),
        )

    app.post("/dossiers/{dossier_id}/invitation/renvoyer", response_model=InvitationVue)(
        renvoyer_invitation
    )
    app.delete("/dossiers/{dossier_id}/invitation", status_code=204)(annuler_invitation)


def _invitation_vue(invitation: Any) -> InvitationVue:
    return InvitationVue(
        dossier_id=str(invitation.dossier_id),
        email=invitation.email,
        statut=_statut_invitation_vue(invitation.statut),
    )


def renvoyer_invitation(
    dossier: DossierPortefeuilleDep,
    comptes: ComptesDep,
    role: RoleMembreDep,
) -> InvitationVue:
    _exiger_ecriture(role, "La lecture seule n'invite pas.")
    try:
        invitation = comptes.renvoyer(dossier.id)
    except InvitationAbsente as exc:
        raise HTTPException(status_code=404, detail="Aucune invitation en attente.") from exc
    except InvitationFermee as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _invitation_vue(invitation)


def annuler_invitation(
    dossier: DossierPortefeuilleDep,
    comptes: ComptesDep,
    role: RoleMembreDep,
) -> None:
    _exiger_ecriture(role, "La lecture seule n'invite pas.")
    try:
        comptes.annuler(dossier.id)
    except InvitationAbsente as exc:
        raise HTTPException(status_code=404, detail="Aucune invitation en attente.") from exc
    except InvitationFermee as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _inviter_en_masse(
    lignes: list[LigneInvitationEntree],
    dossiers_du_portefeuille: set[str],
    comptes: CompteRepository,
) -> InvitationsMasseVue:
    """Traite chaque ligne indépendamment : une ligne en échec n'empêche pas
    les autres (un fichier de 200 chauffeurs ne doit pas échouer en bloc sur
    une adresse mal saisie). Un dossier hors du portefeuille est déclaré
    « inconnu », comme s'il n'existait pas."""
    sorties: dict[int, str] = {}
    a_inviter: list[tuple[int, LigneInvitationEntree]] = []
    vus: set[str] = set()
    for rang, ligne in enumerate(lignes):
        if ligne.dossier_id not in dossiers_du_portefeuille:
            sorties[rang] = "dossier_inconnu"
        elif not _FORME_EMAIL.match(ligne.email.strip()):
            sorties[rang] = "email_invalide"
        elif ligne.dossier_id in vus:
            sorties[rang] = "doublon_dans_le_lot"
        else:
            vus.add(ligne.dossier_id)
            a_inviter.append((rang, ligne))

    existants = comptes.statuts([DossierId(ligne.dossier_id) for _, ligne in a_inviter])
    for rang, ligne in a_inviter:
        if ligne.dossier_id in existants:
            sorties[rang] = "deja_invite"
            continue
        try:
            comptes.inviter(
                DossierId(ligne.dossier_id), ligne.email.strip(), verifier_existant=False
            )
        except Exception:  # noqa: BLE001 — le détail (adresse) n'est pas renvoyé au client
            sorties[rang] = "erreur"
        else:
            sorties[rang] = "invité"

    vues = [
        LigneInvitationVue(dossier_id=ligne.dossier_id, email=ligne.email, resultat=sorties[rang])
        for rang, ligne in enumerate(lignes)
    ]
    return InvitationsMasseVue(lignes=vues, nb_invitees=sum(v.resultat == "invité" for v in vues))


def _exporter(
    journal: JournalAcces,
    dossier: Dossier,
    identite: IdentiteAuthentifiee | None,
    contenu: bytes | str,
    media_type: str,
    nom_fichier: str,
) -> Response:
    """Le fichier, et sa trace au journal d'audit (AXE-812). Appelé une fois
    le fichier produit : un export refusé ne laisse pas de ligne."""
    _tracer_export(journal, dossier, identite, nom_fichier)
    return _fichier(contenu, media_type, nom_fichier)


def _fichier(contenu: bytes | str, media_type: str, nom_fichier: str) -> Response:
    corps = contenu.encode("utf-8") if isinstance(contenu, str) else contenu
    return Response(
        content=corps,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )


def _enregistrer_routes_pieces_greffe(app: FastAPI) -> None:
    """Bilan et compte de résultat, une page chacun, au nom demandé par l'INPI."""

    @app.get("/dossiers/{dossier_id}/bilan.pdf")
    def telecharger_bilan(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        pdf = extraire_page_2033(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions)), "2033A"
        )
        return _exporter(
            journal_acces,
            dossier,
            identite,
            pdf,
            "application/pdf",
            f"bilan-actif-passif-{dossier.id}.pdf",
        )

    @app.get("/dossiers/{dossier_id}/compte-resultat.pdf")
    def telecharger_compte_resultat(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        pdf = extraire_page_2033(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions)), "2033B"
        )
        return _exporter(
            journal_acces,
            dossier,
            identite,
            pdf,
            "application/pdf",
            f"compte-de-resultat-{dossier.id}.pdf",
        )


def _enregistrer_routes_declarations(app: FastAPI) -> None:
    """Déclaration de résultat selon la colonne de la matrice (doc 06 §7) :
    2065 à l'IS, 2031 à l'IR. L'autre répond 409, jamais un formulaire faux."""

    @app.get("/dossiers/{dossier_id}/cerfa-2065.pdf")
    def telecharger_cerfa(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        if not _colonne(dossier).soumis_is:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{_colonne(dossier).libelle} : la 2065 ne concerne que l'IS, "
                    "l'impôt sur les sociétés."
                ),
            )
        _exiger_dossier_clair(dossier)
        pdf = PdfCerfa2065Renderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _exporter(
            journal_acces, dossier, identite, pdf, "application/pdf", f"cerfa-2065-{dossier.id}.pdf"
        )

    @app.get("/dossiers/{dossier_id}/cerfa-2031.pdf")
    def telecharger_cerfa_2031(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        if _colonne(dossier).soumis_is:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{_colonne(dossier).libelle} : la 2031 ne concerne que l'IR, "
                    "l'impôt sur le revenu."
                ),
            )
        _exiger_dossier_clair(dossier)
        pdf = PdfCerfa2031Renderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _exporter(
            journal_acces, dossier, identite, pdf, "application/pdf", f"cerfa-2031-{dossier.id}.pdf"
        )


def _enregistrer_routes_cloture(app: FastAPI) -> None:
    """Semaine 4 (doc 17 §9) : les renderers de clôture, exposés en
    téléchargement direct — sur le ledger avec décisions humaines appliquées
    (`_construire_liasse`), pas le ledger brut."""

    @app.get("/dossiers/{dossier_id}/liasse.pdf")
    def telecharger_liasse(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        pdf = PdfLiasseSimplifieeRenderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        nom = f"liasse-{dossier.id}.pdf"
        return _exporter(journal_acces, dossier, identite, pdf, "application/pdf", nom)

    @app.get("/dossiers/{dossier_id}/liasse-fiscale.pdf")
    def telecharger_liasse_fiscale(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        _exiger_operations_tranchees(dossier, ledger)
        _exiger_dossier_clair(dossier)
        pdf = PdfLiasseFiscaleRenderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _exporter(
            journal_acces,
            dossier,
            identite,
            pdf,
            "application/pdf",
            f"liasse-fiscale-{dossier.id}.pdf",
        )


def _enregistrer_route_fec(app: FastAPI) -> None:
    """Le FEC (A.47 A-1), tracé au journal d'audit à chaque téléchargement."""

    @app.get("/dossiers/{dossier_id}/fec.txt")
    def telecharger_fec(
        dossier: DossierDep,
        ledger: LedgerComptableDep,
        provisions: ProvisionsDep,
        comptes: ComptesBancairesDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        # Nom légal `<SIREN>FEC<clôture>.txt` (A.47 A-1) quand l'identité est connue.
        nom = (
            nom_fichier_fec(dossier.identite.siren, dossier.fin_exercice())
            if dossier.identite is not None
            else f"fec-{dossier.id}.txt"
        )
        fec = exporter_fec(ecritures, libelles_banques(comptes.lister(dossier.id)))
        return _exporter(journal_acces, dossier, identite, fec, "text/plain; charset=utf-8", nom)


def _soldes_par_compte(ecritures: tuple[Ecriture, ...]) -> dict[str, int]:
    """Solde débiteur de chaque compte de banque, en centimes."""
    soldes: dict[str, int] = {}
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            if est_compte_banque(ligne.compte):
                signe = 1 if ligne.sens is Sens.DEBIT else -1
                soldes[ligne.compte] = soldes.get(ligne.compte, 0) + signe * ligne.montant.centimes
    return soldes


def _vue_compte_bancaire(compte: CompteBancaire, solde_comptable: int) -> CompteBancaireVue:
    banque = compte.solde_banque_cts
    return CompteBancaireVue(
        compte=compte.compte_comptable,
        nom=compte.nom,
        solde_comptable_cts=solde_comptable,
        solde_banque_cts=banque,
        releve_le=compte.solde_releve_le.isoformat() if compte.solde_releve_le else None,
        # Un compte non retenu n'est pas comptabilisé : pas d'écart à montrer.
        ecart_cts=None if banque is None or compte.retenu is not True else solde_comptable - banque,
        retenu=compte.retenu,
    )


def vues_comptes_bancaires(
    comptes: tuple[CompteBancaire, ...], ecritures: tuple[Ecriture, ...]
) -> list[CompteBancaireVue]:
    """Un compte par sous-compte 512x, plus le 512 non ventilé s'il porte
    encore un solde (écritures d'avant AXE-832, ou banque inconnue)."""
    soldes = _soldes_par_compte(ecritures)
    vues = [_vue_compte_bancaire(c, soldes.get(c.compte_comptable, 0)) for c in comptes]
    reste = soldes.get(COMPTE_BANQUE, 0)
    if reste:
        vues.append(
            CompteBancaireVue(
                compte=COMPTE_BANQUE,
                nom=None,
                solde_comptable_cts=reste,
                solde_banque_cts=None,
                releve_le=None,
                ecart_cts=None,
            )
        )
    return vues


def libelles_banques(comptes: tuple[CompteBancaire, ...]) -> dict[str, str]:
    """Libellé FEC de chaque sous-compte : « Banque — <nom du compte> »."""
    return {c.compte_comptable: f"Banque — {c.nom}" for c in comptes if c.nom}


def _enregistrer_routes_comptes_bancaires(app: FastAPI) -> None:
    @app.get("/dossiers/{dossier_id}/comptes-bancaires", response_model=list[CompteBancaireVue])
    def lister_comptes_bancaires(
        dossier: DossierDep, ledger: LedgerDossierDep, comptes: ComptesBancairesDep
    ) -> list[CompteBancaireVue]:
        """AXE-832 : soldes comptable et bancaire de chaque compte, côte à
        côte. Réservé au chauffeur du dossier (doc 19 : le gestionnaire ne
        voit pas de solde)."""
        return vues_comptes_bancaires(comptes.lister(dossier.id), ledger.grand_livre(dossier.id))

    @app.post(
        "/dossiers/{dossier_id}/comptes-bancaires/{compte}/decision",
        response_model=list[CompteBancaireVue],
    )
    def decider_compte_bancaire(
        compte: str,
        corps: DecisionCompteEntree,
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        comptes: ComptesBancairesDep,
        identite: IdentiteDep,
    ) -> list[CompteBancaireVue]:
        """AXE-729 : le dirigeant retient un compte (pro) ou l'écarte
        (personnel). Retenu après coup, son passé arrive à la synchro
        suivante. Un compte qui a déjà des écritures ne s'écarte pas."""
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecritures = ledger.grand_livre(dossier.id)
        try:
            if not corps.retenu:
                verifier_ecartable(_ecritures_sur_le_compte(ecritures, compte))
            comptes.decider(dossier.id, compte, corps.retenu, identite.user_id, datetime.now(UTC))
        except CompteInconnu as erreur:
            raise HTTPException(status_code=404, detail=str(erreur)) from erreur
        except CompteDejaComptabilise as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return vues_comptes_bancaires(comptes.lister(dossier.id), ecritures)


def _ecritures_sur_le_compte(ecritures: tuple[Ecriture, ...], compte: str) -> int:
    """Écritures en vigueur (non contre-passées) qui mouvementent ce sous-compte."""
    exclues = annulees(ecritures)
    return sum(
        1
        for ecriture in ecritures
        if ecriture.id not in exclues and any(ligne.compte == compte for ligne in ecriture.lignes)
    )


def _enregistrer_routes_exports(app: FastAPI) -> None:
    @app.get("/dossiers/{dossier_id}/grand-livre.csv")
    def telecharger_grand_livre(
        dossier: DossierDep,
        ledger: LedgerComptableDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        return _exporter(
            journal_acces,
            dossier,
            identite,
            exporter_grand_livre(ecritures),
            "text/csv",
            f"grand-livre-{dossier.id}.csv",
        )

    @app.get("/dossiers/{dossier_id}/grand-livre.pdf")
    def telecharger_grand_livre_pdf(
        dossier: DossierDep,
        ledger: LedgerComptableDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        pdf = rendre_grand_livre_pdf(ecritures, dossier_id=str(dossier.id))
        return _exporter(
            journal_acces,
            dossier,
            identite,
            pdf,
            "application/pdf",
            f"grand-livre-{dossier.id}.pdf",
        )


def _enregistrer_routes_balance(app: FastAPI) -> None:
    """Balance, en CSV et en PDF, tracée au journal d'audit (AXE-812)."""

    @app.get("/dossiers/{dossier_id}/balance.csv")
    def telecharger_balance(
        dossier: DossierDep,
        ledger: LedgerComptableDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        return _exporter(
            journal_acces,
            dossier,
            identite,
            exporter_balance(ecritures),
            "text/csv",
            f"balance-{dossier.id}.csv",
        )

    @app.get("/dossiers/{dossier_id}/balance.pdf")
    def telecharger_balance_pdf(
        dossier: DossierDep,
        ledger: LedgerComptableDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        pdf = rendre_balance_pdf(ecritures, dossier_id=str(dossier.id))
        return _exporter(
            journal_acces, dossier, identite, pdf, "application/pdf", f"balance-{dossier.id}.pdf"
        )


def _document_greffe_inpi(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    provisions: SaisiesCloture = SANS_SAISIE,
) -> bytes:
    """doc 20 §4 : le PDF non signé (« document de synthèse » de démo, pas
    celui que le Guichet Unique génère réellement — on ne peut pas
    l'appeler sans compte e-procédures)."""
    return PdfDepotInpiRenderer().rendre(_construire_liasse(dossier, ledger, provisions))


def _enregistrer_routes_greffe_inpi(app: FastAPI) -> None:
    """doc 20 §4/§5, Louis 2026-09-11 : signature fictive pour la démo
    (jamais qualifiée RGS, `qualifie=False`), mais une vraie zone de
    signature qui finit le document — pas juste un badge React. Le vrai
    dépôt (appel API + signature qualifiée réelle) reste bloqué sur
    ADR-004 (prestataire, doc 20 §7)."""

    @app.get("/dossiers/{dossier_id}/greffe-inpi.pdf")
    def telecharger_greffe_inpi(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        signatures: SignaturesInpiDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
        journal_acces: JournalAccesDep,
    ) -> Response:
        _exiger_depot_greffe(dossier)
        document_signe = signatures.dernier(dossier.id, TYPE_DOCUMENT_GREFFE_INPI)
        pdf = (
            document_signe.contenu_pdf
            if document_signe is not None
            else _document_greffe_inpi(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        nom = f"greffe-inpi-{dossier.id}.pdf"
        return _exporter(journal_acces, dossier, identite, pdf, "application/pdf", nom)

    @app.post("/dossiers/{dossier_id}/greffe-inpi/signature", response_model=SignatureGreffeVue)
    def signer_greffe_inpi(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        signatures: SignaturesInpiDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
    ) -> SignatureGreffeVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        _exiger_depot_greffe(dossier)
        _exiger_operations_tranchees(dossier, ledger)
        pdf_non_signe = _document_greffe_inpi(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        document = SignatureDemoProvider().signer(pdf_non_signe, identite.user_id)
        signatures.enregistrer(dossier.id, TYPE_DOCUMENT_GREFFE_INPI, document)
        # Preuve greffe enregistrée. La frise n'avance que si clôture et
        # signature de validation sont déjà là (préfixe, workflow/jalons).
        return SignatureGreffeVue(
            dossier_id=dossier.id,
            signe=True,
            signe_le=document.signe_le.isoformat(),
            qualifie=document.qualifie,
        )


class NotificationVue(BaseModel):
    id: str
    type: str
    message: str
    cree_le: str
    lue: bool


class NotificationLueVue(BaseModel):
    id: str
    lue: bool


class NotificationsLuesVue(BaseModel):
    lues: int


# Assez pour une cloche : au-delà, les plus anciennes n'apportent rien,
# l'écran « À traiter » montre déjà tout ce qui attend.
_NOTIFICATIONS_AFFICHEES = 20
# Avant regroupement, pour qu'un rappel récent ne cache pas un autre sujet.
_HISTORIQUE_AVANT_REGROUPEMENT = 200


def _enregistrer_routes_notifications(app: FastAPI) -> None:
    """Cloche de l'espace chauffeur (doc 19 §5.2) : indiv seulement, comme
    le reste de son dossier. Le nombre d'opérations est recalculé ici."""

    @app.get("/dossiers/{dossier_id}/notifications", response_model=list[NotificationVue])
    def lister_notifications(
        dossier: DossierDep,
        notifications: NotificationsDep,
        ledger: LedgerBaseDep,
        decisions: DecisionsDep,
        comptes_bancaires: ComptesBancairesDep,
    ) -> list[NotificationVue]:
        nb = len(ecritures_a_trancher(ledger, decisions, dossier.id))
        visibles = pour_la_cloche(
            notifications.lister(dossier.id, _HISTORIQUE_AVANT_REGROUPEMENT),
            nb,
            _NOTIFICATIONS_AFFICHEES,
            nombre_a_choisir(comptes_bancaires.lister(dossier.id)),
        )
        return [
            NotificationVue(
                id=vue.id,
                type=vue.type,
                message=vue.message,
                cree_le=vue.envoye_le.isoformat(),
                lue=vue.lue,
            )
            for vue in visibles
        ]

    @app.post(
        "/dossiers/{dossier_id}/notifications/{notification_id}/lue",
        response_model=NotificationLueVue,
    )
    def marquer_notification_lue(
        notification_id: str, dossier: DossierDep, notifications: NotificationsDep
    ) -> NotificationLueVue:
        maintenant = datetime.now(UTC).replace(tzinfo=None)
        if not notifications.marquer_lue(dossier.id, notification_id, maintenant):
            raise HTTPException(status_code=404, detail="Notification introuvable.")
        return NotificationLueVue(id=notification_id, lue=True)

    @app.post("/dossiers/{dossier_id}/notifications/lues", response_model=NotificationsLuesVue)
    def marquer_notifications_lues(
        dossier: DossierDep, notifications: NotificationsDep
    ) -> NotificationsLuesVue:
        maintenant = datetime.now(UTC).replace(tzinfo=None)
        return NotificationsLuesVue(lues=notifications.marquer_lues(dossier.id, maintenant))


class ClotureExerciceVue(BaseModel):
    """Ce que la clôture fera, avant que le chauffeur la valide (doc 06 §5)."""

    possible: bool
    raison: str | None = None
    exercice_debut: str
    exercice_fin: str
    nouvel_exercice_debut: str | None = None
    ecritures: list[str] = []
    changements: list[str] = []
    # Texte à accepter tel quel ; renvoyé à l'identique pour valider.
    attestation: str | None = None
    # pas_termine | operations | clos | autre. Le texte seul ne sert pas de drapeau.
    code: str | None = None


class ValidationClotureEntree(BaseModel):
    attestation: str


class ConfigurationDossierVue(BaseModel):
    """Ce que le dirigeant confirme (AXE-730), et ce qui reste à saisir."""

    forme_juridique: str
    formes_proposees: list[str]  # deux quand Sirene ne tranche pas
    regime_imposition: str
    regime_tva: str
    exercice_debut: str
    exercice_fin: str
    a_confirmer: list[str]
    identite_manquante: list[str]  # siege, capital, associes
    raison_blocage: str | None  # ce qui bloque la clôture et la liasse


class ConfirmationConfigurationEntree(BaseModel):
    forme_juridique: str | None = None


def _vue_configuration(dossier: Dossier) -> ConfigurationDossierVue:
    return ConfigurationDossierVue(
        forme_juridique=dossier.forme_juridique,
        formes_proposees=list(formes_proposees(dossier)),
        regime_imposition=dossier.regime_imposition,
        regime_tva=dossier.regime_tva,
        exercice_debut=dossier.exercice_debut.isoformat(),
        exercice_fin=dossier.fin_exercice().isoformat(),
        a_confirmer=list(dossier.a_confirmer),
        identite_manquante=list(identite_manquante(dossier)),
        raison_blocage=raison_ambiguite(dossier),
    )


def _enregistrer_routes_configuration(app: FastAPI) -> None:
    """Le dirigeant voit sa configuration et la confirme (AXE-730). Le
    gestionnaire voit « à confirmer » dans son portefeuille."""

    @app.get("/dossiers/{dossier_id}/configuration", response_model=ConfigurationDossierVue)
    def lire_configuration(dossier: DossierDep) -> ConfigurationDossierVue:
        return _vue_configuration(dossier)

    @app.post(
        "/dossiers/{dossier_id}/configuration/confirmer", response_model=ConfigurationDossierVue
    )
    def confirmer_configuration(
        corps: ConfirmationConfigurationEntree,
        dossier: DossierDep,
        dossiers: DossiersDep,
        identite: IdentiteDep,
    ) -> ConfigurationDossierVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        try:
            confirme = confirmer(dossier, corps.forme_juridique)
        except ConfirmationRefusee as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        dossiers.confirmer_configuration(confirme, identite.user_id, datetime.now(UTC))
        return _vue_configuration(confirme)


class AdresseModele(BaseModel):
    numero: str = ""
    voie: str
    code_postal: str
    commune: str
    pays: str = "France"


class AssocieModele(BaseModel):
    civilite: str
    nom: str
    prenoms: str
    date_naissance: date
    departement_naissance: str = ""
    commune_naissance: str
    pays_naissance: str = "France"
    adresse: AdresseModele
    nb_titres: int
    qualite: str


class IdentiteModele(BaseModel):
    """Siège, capital et associés d'une société (AXE-846), montants en
    centimes. Même forme en lecture et en écriture."""

    denomination: str
    siren: str
    nic: str
    adresse_siege: AdresseModele
    code_ape: str = ""
    activite: str = ""
    email: str = ""
    capital_social_cts: int
    associes: list[AssocieModele]


class IdentiteDossierVue(BaseModel):
    identite: IdentiteModele | None
    forme_juridique: str
    associe_unique: bool  # SASU, EURL : un seul associé
    qualite_par_defaut: str
    siren_connu: str | None  # pour pré-remplir sans le redemander


class PersonneConnueVue(BaseModel):
    nom: str
    prenoms: str
    code_postal: str = ""
    commune: str = ""
    pays: str = "France"


class PreRemplissageVue(BaseModel):
    siren: str
    denomination: str
    nic: str
    adresse_siege: AdresseModele
    code_ape: str
    capital_social_cts: int | None = None
    personnes: list[PersonneConnueVue] = []


def _identite_depuis_modele(modele: IdentiteModele) -> IdentiteEntreprise:
    return IdentiteEntreprise(
        denomination=modele.denomination.strip(),
        siren=modele.siren.replace(" ", ""),
        nic=modele.nic.replace(" ", ""),
        adresse_siege=Adresse(**modele.adresse_siege.model_dump()),
        code_ape=modele.code_ape.strip(),
        activite=modele.activite.strip(),
        email=modele.email.strip(),
        capital_social_cts=modele.capital_social_cts,
        associes=tuple(
            Associe(**{**a.model_dump(), "adresse": Adresse(**a.adresse.model_dump())})
            for a in modele.associes
        ),
    )


def _siren_connu(dossier: Dossier) -> str | None:
    if dossier.identite is not None:
        return dossier.identite.siren
    if dossier.id.startswith("SIREN_"):
        return dossier.id.removeprefix("SIREN_")
    return None


class LigneOuvertureVue(BaseModel):
    compte: str
    debit_cts: int
    credit_cts: int


class AnalyseFecVue(BaseModel):
    """Ce que voit la personne qui reprend le bilan d'ouverture, avant de
    valider (AXE-804). Rien n'est écrit."""

    possible: bool
    siren: str
    cloture: str
    ouverture: str
    nb_lignes: int
    nb_ecritures: int
    total_debit_cts: int
    resultat_cts: int
    solde_banque_cts: int
    capital_cts: int
    comptes_inconnus: list[str]
    refus: list[str]
    alertes: list[str]
    attestation: str  # à renvoyer telle quelle pour valider
    a_nouveaux: list[LigneOuvertureVue]


class OuvertureVue(BaseModel):
    faite: bool
    nom_fichier: str | None = None
    cloture: str | None = None
    role: str | None = None
    auteur: str | None = None
    le: str | None = None
    deficits_euros: int = 0


def get_ouvertures() -> OuverturesRepository:
    """Dépendance FastAPI : bilans d'ouverture repris d'un FEC (AXE-804)."""
    return OuverturesPostgres(_engine())


OuverturesDep = Annotated[OuverturesRepository, Depends(get_ouvertures)]


def _siren_du_dossier(dossier: Dossier) -> str | None:
    if dossier.identite is not None:
        return dossier.identite.siren
    if dossier.siren:
        return dossier.siren
    if dossier.id.startswith("SIREN_"):
        return dossier.id.removeprefix("SIREN_")
    return None


def _vue_identite(dossier: Dossier) -> IdentiteDossierVue:
    actuelle = identite_vers_json(dossier.identite)
    return IdentiteDossierVue(
        identite=IdentiteModele.model_validate(actuelle) if actuelle else None,
        forme_juridique=dossier.forme_juridique,
        associe_unique=dossier.forme_juridique in FORMES_UNIPERSONNELLES,
        qualite_par_defaut=qualite_par_defaut(dossier.forme_juridique),
        siren_connu=_siren_connu(dossier),
    )


LireRegistre = Callable[[str], Mapping[str, object]]
LireFicheOfficielle = Callable[[str], FicheOfficielle | None]


def get_lire_registre() -> LireRegistre:
    """Dépendance FastAPI : Recherche d'entreprises (remplacée en test)."""
    return recherche_entreprises


def get_lire_fiche_officielle() -> LireFicheOfficielle | None:
    """INSEE et RNE quand les clés sont dans le `.env`. `None` sinon.
    Remplacée en test, pour ne jamais appeler les registres réels."""
    from axelcompta.registres_officiels import charger_env, lecteur_depuis_env

    charger_env()
    return lecteur_depuis_env()


def _enregistrer_routes_identite(app: FastAPI) -> None:
    """Le dirigeant saisit le siège, le capital et les associés de sa société
    (AXE-846), pré-remplis depuis le registre public. Le gestionnaire n'y a
    pas accès (doc 19 : il ne voit que des agrégats)."""

    @app.get("/dossiers/{dossier_id}/identite", response_model=IdentiteDossierVue)
    def lire_identite(dossier: DossierDep, identite: IdentiteDep) -> IdentiteDossierVue:
        _verifier_acces_dossier(dossier.id, identite)
        return _vue_identite(dossier)

    @app.get("/dossiers/{dossier_id}/identite/registre", response_model=PreRemplissageVue)
    def lire_registre(
        siren: str,
        dossier: DossierDep,
        identite: IdentiteDep,
        lire: Annotated[LireRegistre, Depends(get_lire_registre)],
        lire_fiche: Annotated[LireFicheOfficielle | None, Depends(get_lire_fiche_officielle)],
    ) -> PreRemplissageVue:
        _verifier_acces_dossier(dossier.id, identite)
        siren = siren.replace(" ", "")
        if not siren_valide(siren):
            raise IdentiteInvalide("Le SIREN doit compter 9 chiffres valides.")
        trouve = pre_remplissage(lire(siren), siren)
        fiche = lire_fiche(siren) if lire_fiche is not None else None
        complet = completer_pre_remplissage(
            trouve,
            siren,
            denomination=fiche.denomination if fiche else None,
            siege=fiche.siege if fiche else None,
            code_ape=fiche.code_naf if fiche else None,
            capital_social_cts=fiche.capital_cts if fiche else None,
            personnes=tuple(
                PersonneConnue(p.nom, p.prenoms, p.code_postal, p.commune, p.pays)
                for p in (fiche.personnes if fiche else ())
            ),
        )
        if complet is None:
            raise HTTPException(
                status_code=404, detail="Aucune société à ce SIREN dans le registre."
            )
        return PreRemplissageVue.model_validate(dataclasses.asdict(complet))

    @app.put("/dossiers/{dossier_id}/identite", response_model=ConfigurationDossierVue)
    def saisir_identite(
        corps: IdentiteModele,
        dossier: DossierDep,
        dossiers: DossiersDep,
        identite: IdentiteDep,
    ) -> ConfigurationDossierVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        saisie = _identite_depuis_modele(corps)
        verifier_identite(saisie, dossier.forme_juridique, date.today())
        dossiers.enregistrer_identite(dossier.id, saisie, identite.user_id, datetime.now(UTC))
        return _vue_configuration(dataclasses.replace(dossier, identite=saisie))


class EcartRegistreVue(BaseModel):
    champ: str
    declare: str
    officiel: str
    phrase: str


class RegistreDossierVue(BaseModel):
    """Ce que disent les registres officiels du dossier (AXE-849)."""

    siren: str | None
    lu_le: str | None
    sources: list[str]
    denomination: str | None
    forme_juridique: str | None
    siege: str | None
    capital_cts: int | None
    dirigeants: list[str]
    cessee: bool | None
    ecarts: list[EcartRegistreVue]


class TrancherEcartEntree(BaseModel):
    retenue: Literal["declaree", "officielle"]


def get_registres() -> RegistresRepository:
    """Dépendance FastAPI : lectures des registres et écarts tranchés."""
    return RegistresPostgres(_engine())


RegistresDep = Annotated[RegistresRepository, Depends(get_registres)]


def _vue_registre(dossier: Dossier, registres: RegistresRepository) -> RegistreDossierVue:
    lue = registres.derniere_lecture(dossier.id)
    fiche = lue[0] if lue else None
    return RegistreDossierVue(
        siren=dossier.siren,
        lu_le=lue[1].isoformat() if lue else None,
        sources=list(fiche.sources) if fiche else [],
        denomination=fiche.denomination if fiche else None,
        forme_juridique=fiche.forme_juridique if fiche else None,
        siege=fiche.siege.sur_une_ligne() if fiche and fiche.siege else None,
        capital_cts=fiche.capital_cts if fiche else None,
        dirigeants=list(fiche.dirigeants) if fiche else [],
        cessee=fiche.cessee if fiche else None,
        ecarts=[
            EcartRegistreVue(
                champ=e.champ, declare=e.declare, officiel=e.officiel, phrase=phrase(e)
            )
            for e in dossier.ecarts_registre
        ],
    )


def _correspondance(brute: str) -> dict[str, str]:
    try:
        lue = json.loads(brute or "{}")
    except json.JSONDecodeError as erreur:
        raise FecRefuse("Correspondance des comptes illisible.") from erreur
    if not isinstance(lue, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in lue.items()
    ):
        raise FecRefuse("Correspondance des comptes illisible.")
    return {k.strip(): v.strip() for k, v in lue.items() if v.strip()}


def _analyser_fec(
    dossier: Dossier,
    contenu: bytes,
    nom_fichier: str,
    correspondance: str,
    ouvertures: OuverturesRepository,
    ledger: LedgerService,
) -> Analyse:
    analyse = analyser_fec(
        contenu,
        nom_fichier,
        dossier.id,
        _siren_du_dossier(dossier),
        dossier.exercice_debut,
        _correspondance(correspondance),
        date.today(),
    )
    deja = ouvertures.obtenir(dossier.id) is not None or any(
        e.id == id_a_nouveaux(dossier.id, dossier.exercice_debut.year)
        for e in ledger.grand_livre(dossier.id)
    )
    if deja:
        refus = (*analyse.refus, str(OuvertureDejaFaite()))
        return dataclasses.replace(analyse, refus=refus, a_nouveaux=None)
    return analyse


def _vue_analyse(analyse: Analyse) -> AnalyseFecVue:
    lignes = analyse.a_nouveaux.lignes if analyse.a_nouveaux else ()
    return AnalyseFecVue(
        possible=analyse.a_nouveaux is not None,
        siren=analyse.siren,
        cloture=analyse.cloture.isoformat(),
        ouverture=analyse.ouverture.isoformat(),
        nb_lignes=analyse.nb_lignes,
        nb_ecritures=analyse.nb_ecritures,
        total_debit_cts=analyse.total_debit,
        resultat_cts=analyse.resultat,
        solde_banque_cts=analyse.solde_banque,
        capital_cts=analyse.capital,
        comptes_inconnus=list(analyse.comptes_inconnus),
        refus=list(analyse.refus),
        alertes=list(analyse.alertes),
        attestation=analyse.attestation,
        a_nouveaux=[
            LigneOuvertureVue(
                compte=ligne.compte,
                debit_cts=ligne.montant.centimes if ligne.sens is Sens.DEBIT else 0,
                credit_cts=ligne.montant.centimes if ligne.sens is Sens.CREDIT else 0,
            )
            for ligne in lignes
        ],
    )


def _enregistrer_routes_registre(app: FastAPI) -> None:
    """Le dirigeant voit ce que disent les registres et tranche chaque écart
    (AXE-849). Tracé au journal d'audit."""

    @app.get("/dossiers/{dossier_id}/registre", response_model=RegistreDossierVue)
    def lire_registre_officiel(
        dossier: DossierDep, registres: RegistresDep, identite: IdentiteDep
    ) -> RegistreDossierVue:
        _verifier_acces_dossier(dossier.id, identite)
        return _vue_registre(dossier, registres)

    @app.post(
        "/dossiers/{dossier_id}/registre/ecarts/{champ}", response_model=ConfigurationDossierVue
    )
    def trancher_ecart(
        champ: str,
        corps: TrancherEcartEntree,
        dossier: DossierDep,
        registres: RegistresDep,
        identite: IdentiteDep,
    ) -> ConfigurationDossierVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecart, reste, forme = trancher(dossier, champ, corps.retenue)
        apres = dataclasses.replace(
            dossier, ecarts_registre=reste, forme_juridique=forme or dossier.forme_juridique
        )
        configuration_de(apres)  # une forme du registre hors matrice est refusée (422)
        tranche = ResolutionEcart(
            dossier.id, ecart, corps.retenue, identite.user_id, datetime.now(UTC)
        )
        registres.resoudre(tranche, reste, forme)
        return _vue_configuration(apres)


def _vue_ouverture(ouverture: OuvertureImportee | None) -> OuvertureVue:
    if ouverture is None:
        return OuvertureVue(faite=False)
    return OuvertureVue(
        faite=True,
        nom_fichier=ouverture.nom_fichier,
        cloture=ouverture.cloture.isoformat(),
        role=ouverture.role,
        auteur=ouverture.auteur_nom,
        le=ouverture.le.isoformat(),
        deficits_euros=ouverture.deficits_euros,
    )


@dataclasses.dataclass(frozen=True, slots=True)
class _Importeur:
    role: str
    par: UserId
    nom: str | None
    motif: str | None


def _importer_fec(
    dossier: Dossier,
    contenu: bytes,
    nom_fichier: str,
    formulaire: tuple[str, str, int],
    importeur: _Importeur,
    depots: tuple[OuverturesRepository, LedgerService],
) -> OuvertureVue:
    """`formulaire` : (correspondance, attestation, déficits en euros). Tout
    refus de l'analyse empêche l'import ; l'attestation doit être celle
    présentée, mot pour mot."""
    correspondance, attestation, deficits = formulaire
    ouvertures, ledger = depots
    analyse = _analyser_fec(dossier, contenu, nom_fichier, correspondance, ouvertures, ledger)
    if analyse.a_nouveaux is None:
        raise FecRefuse(" ".join(analyse.refus) or "Rien à reprendre.")
    if attestation.strip() != analyse.attestation:
        raise FecRefuse("Cochez l'attestation présentée avant de valider.")
    if deficits < 0:
        raise FecRefuse("Les déficits reportables ne peuvent pas être négatifs.")
    ouverture = OuvertureImportee(
        dossier_id=dossier.id,
        nom_fichier=nom_fichier,
        empreinte=analyse.empreinte,
        cloture=analyse.cloture,
        ouverture=analyse.ouverture,
        role=importeur.role,
        par=importeur.par,
        auteur_nom=importeur.nom,
        motif=importeur.motif,
        attestation=analyse.attestation,
        correspondance=_correspondance(correspondance),
        deficits_euros=deficits,
        ecriture_id=analyse.a_nouveaux.id,
        le=datetime.now(UTC),
    )
    ouvertures.importer(ouverture, analyse.a_nouveaux)
    return _vue_ouverture(ouverture)


def _enregistrer_routes_ouverture(app: FastAPI) -> None:
    """Bilan d'ouverture d'une société existante, repris du FEC de l'outil
    précédent (AXE-804) : par le dirigeant, ou par l'expert-comptable
    habilité, jamais par le logiciel seul."""

    @app.get("/dossiers/{dossier_id}/ouverture", response_model=OuvertureVue)
    def lire_ouverture(
        dossier: DossierDep, ouvertures: OuverturesDep, identite: IdentiteDep
    ) -> OuvertureVue:
        _verifier_acces_dossier(dossier.id, identite)
        return _vue_ouverture(ouvertures.obtenir(dossier.id))

    @app.post("/dossiers/{dossier_id}/ouverture/fec/analyse", response_model=AnalyseFecVue)
    async def analyser_ouverture(
        fichier: UploadFile,
        dossier: DossierDep,
        ouvertures: OuverturesDep,
        ledger: LedgerBaseDep,
        identite: IdentiteDep,
        correspondance: Annotated[str, Form()] = "{}",
    ) -> AnalyseFecVue:
        _verifier_acces_dossier(dossier.id, identite)
        contenu = await fichier.read()
        nom = fichier.filename or ""
        return _vue_analyse(
            _analyser_fec(dossier, contenu, nom, correspondance, ouvertures, ledger)
        )

    @app.post("/dossiers/{dossier_id}/ouverture/fec", response_model=OuvertureVue)
    async def importer_ouverture(
        fichier: UploadFile,
        dossier: DossierDep,
        ouvertures: OuverturesDep,
        ledger: LedgerBaseDep,
        identite: IdentiteDep,
        attestation: Annotated[str, Form()],
        correspondance: Annotated[str, Form()] = "{}",
        deficits_euros: Annotated[int, Form()] = 0,
    ) -> OuvertureVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        importeur = _Importeur(ROLE_DIRIGEANT, identite.user_id, None, None)
        return _importer_fec(
            dossier,
            await fichier.read(),
            fichier.filename or "",
            (correspondance, attestation, deficits_euros),
            importeur,
            (ouvertures, ledger),
        )

    _enregistrer_routes_ouverture_expert(app)


def _enregistrer_routes_ouverture_expert(app: FastAPI) -> None:
    @app.get("/expert/dossiers/{dossier_id}/ouverture", response_model=OuvertureVue)
    def lire_ouverture_expert(dossier: DossierExpertDep, ouvertures: OuverturesDep) -> OuvertureVue:
        return _vue_ouverture(ouvertures.obtenir(dossier.id))

    @app.post("/expert/dossiers/{dossier_id}/ouverture/fec/analyse", response_model=AnalyseFecVue)
    async def analyser_ouverture_expert(
        fichier: UploadFile,
        dossier: DossierExpertDep,
        ouvertures: OuverturesDep,
        ledger: LedgerBaseDep,
        correspondance: Annotated[str, Form()] = "{}",
    ) -> AnalyseFecVue:
        contenu = await fichier.read()
        nom = fichier.filename or ""
        return _vue_analyse(
            _analyser_fec(dossier, contenu, nom, correspondance, ouvertures, ledger)
        )

    @app.post("/expert/dossiers/{dossier_id}/ouverture/fec", response_model=OuvertureVue)
    async def importer_ouverture_expert(
        fichier: UploadFile,
        dossier: DossierExpertDep,
        ouvertures: OuverturesDep,
        ledger: LedgerBaseDep,
        identite: IdentiteDep,
        role: RoleMembreDep,
        experts: ExpertsDep,
        attestation: Annotated[str, Form()],
        motif: Annotated[str, Form()],
        correspondance: Annotated[str, Form()] = "{}",
        deficits_euros: Annotated[int, Form()] = 0,
    ) -> OuvertureVue:
        _tenant, identite, actif = _expert(identite, role, experts)
        importeur = _Importeur(
            ROLE_EXPERT, identite.user_id, actif.habilitation.nom, motif_valide(motif)
        )
        return _importer_fec(
            dossier,
            await fichier.read(),
            fichier.filename or "",
            (correspondance, attestation, deficits_euros),
            importeur,
            (ouvertures, ledger),
        )


def _signataire(dossier: Dossier, identite: IdentiteAuthentifiee) -> str:
    if dossier.identite is not None:
        dirigeant = dossier.identite.dirigeant
        return f"{dirigeant.prenoms} {dirigeant.nom}"
    return identite.email


def _preparer_cloture(
    dossier: Dossier,
    ledger: LedgerService,
    decisions: DecisionRepository,
    avenants: AvenantRegimeRepository,
    provisions: SaisiesCloture = SANS_SAISIE,
) -> PassageExercice:
    """Lève `PassageRefuse` (un `Conflit` : 409 avec sa phrase, AXE-839) ;
    l'aperçu la lit pour dire pourquoi, avec son code (AXE-853)."""
    return preparer_passage(
        dossier,
        ledger,
        decisions,
        avenants.lister(dossier.id),
        datetime.now(UTC).date(),
        provisions,
    )


class ProvisionVue(BaseModel):
    nature: str
    compte_charge: str
    centimes: int
    libelle: str


class ProvisionsVue(BaseModel):
    lignes: list[ProvisionVue]


def _lire_provisions(corps: ProvisionsVue) -> tuple[ProvisionCloture, ...]:
    provisions = tuple(
        ProvisionCloture(
            nature=ligne.nature,
            compte_charge=ligne.compte_charge,
            centimes=ligne.centimes,
            libelle=ligne.libelle,
        )
        for ligne in corps.lignes
    )
    for provision in provisions:
        valider_provision(provision)
    return provisions


def _vue_provisions(lignes: tuple[ProvisionCloture, ...]) -> ProvisionsVue:
    return ProvisionsVue(
        lignes=[
            ProvisionVue(
                nature=ligne.nature,
                compte_charge=ligne.compte_charge,
                centimes=ligne.centimes,
                libelle=ligne.libelle,
            )
            for ligne in lignes
        ]
    )


def _enregistrer_routes_provisions(app: FastAPI) -> None:
    """Estimation saisie par le chauffeur (doc 06 §5 point 5). Remplaçable."""

    @app.get("/dossiers/{dossier_id}/provisions-cloture", response_model=ProvisionsVue)
    def lire_provisions(
        dossier: DossierDep, provisions: ProvisionsDep, identite: IdentiteDep
    ) -> ProvisionsVue:
        _verifier_acces_dossier(dossier.id, identite)
        return _vue_provisions(_provisions_saisies(dossier, provisions).provisions)

    @app.put("/dossiers/{dossier_id}/provisions-cloture", response_model=ProvisionsVue)
    def enregistrer_provisions(
        corps: ProvisionsVue,
        dossier: DossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
    ) -> ProvisionsVue:
        _verifier_acces_dossier(dossier.id, identite)
        saisies = _lire_provisions(corps)
        provisions.remplacer(dossier.tenant_id, dossier.id, dossier.fin_exercice().year, saisies)
        return _vue_provisions(saisies)


class ImmobilisationVue(BaseModel):
    id: str
    designation: str
    compte: str
    mise_en_service: str
    base_cts: int
    duree_mois: int
    dotation_exercice_cts: int  # dotation de l'exercice ouvert
    valeur_nette_cts: int  # à la fin de l'exercice ouvert (ou à la cession)
    cede_le: str | None = None
    prix_cession_cts: int | None = None
    plus_ou_moins_value_cts: int | None = None


class BienADeclarerVue(BaseModel):
    """Une opération imputée sur un compte d'immobilisation, pas encore au registre."""

    ecriture_id: str
    date: str
    libelle: str
    compte: str
    base_cts: int
    duree_proposee_mois: int


class RegistreVue(BaseModel):
    immobilisations: list[ImmobilisationVue]
    a_declarer: list[BienADeclarerVue]


class DeclarationEntree(BaseModel):
    ecriture_id: str
    designation: str
    mise_en_service: date
    duree_mois: int


class CessionEntree(BaseModel):
    le: date
    prix_cts: int = 0


def _ligne_immobilisee(ecriture: Ecriture) -> LigneEcriture | None:
    """La ligne d'acquisition d'un bien : compte 2 hors amortissements (28)."""
    return next(
        (
            x
            for x in ecriture.lignes
            if x.compte.startswith("2") and not x.compte.startswith("28") and x.sens is Sens.DEBIT
        ),
        None,
    )


def _vue_immobilisation(dossier: Dossier, immo: Immobilisation) -> ImmobilisationVue:
    debut, fin = dossier.exercice_debut, dossier.fin_exercice()
    return ImmobilisationVue(
        id=immo.id,
        designation=immo.designation,
        compte=immo.compte,
        mise_en_service=immo.mise_en_service.isoformat(),
        base_cts=immo.base_cts,
        duree_mois=immo.duree_mois,
        dotation_exercice_cts=dotation(immo, debut, fin),
        valeur_nette_cts=valeur_nette(immo, fin),
        cede_le=immo.cession.le.isoformat() if immo.cession else None,
        prix_cession_cts=immo.cession.prix_cts if immo.cession else None,
        plus_ou_moins_value_cts=plus_ou_moins_value(immo),
    )


def _registre(
    dossier: Dossier, ledger: InMemoryLedgerService, depot: ProvisionsClotureRepository
) -> RegistreVue:
    fiches = depot.lister_immobilisations(dossier.tenant_id, dossier.id)
    declarees = {f.ecriture_acquisition for f in fiches}
    exclues = annulees(ledger.grand_livre(dossier.id))
    a_declarer = [
        BienADeclarerVue(
            ecriture_id=e.id,
            date=e.date.isoformat(),
            libelle=sans_categorie(e.libelle),
            compte=ligne.compte,
            base_cts=ligne.montant.centimes,
            duree_proposee_mois=DUREES_PROPOSEES.get(ligne.compte, DUREE_PAR_DEFAUT),
        )
        for e in ledger.grand_livre(dossier.id)
        if e.id not in declarees
        and e.id not in exclues
        and (ligne := _ligne_immobilisee(e)) is not None
        and ligne_banque(e) is not None
    ]
    return RegistreVue(
        immobilisations=[_vue_immobilisation(dossier, f) for f in fiches], a_declarer=a_declarer
    )


def _declarer(
    dossier: Dossier, ledger: InMemoryLedgerService, entree: DeclarationEntree
) -> Immobilisation:
    """La fiche d'un bien acquis par une opération : compte et base viennent
    de l'écriture (HT quand la TVA a été séparée), le reste du chauffeur."""
    ecriture = next((e for e in ledger.grand_livre(dossier.id) if e.id == entree.ecriture_id), None)
    ligne = _ligne_immobilisee(ecriture) if ecriture is not None else None
    if ecriture is None or ligne is None:
        raise ImmobilisationInvalide("Cette opération n'est pas l'achat d'un bien à amortir.")
    fiche = Immobilisation(
        id=f"{entree.ecriture_id}:immo",
        designation=entree.designation.strip(),
        compte=ligne.compte,
        mise_en_service=entree.mise_en_service,
        base_cts=ligne.montant.centimes,
        duree_mois=entree.duree_mois,
        ecriture_acquisition=entree.ecriture_id,
    )
    valider(fiche)
    return fiche


def _enregistrer_routes_immobilisations(app: FastAPI) -> None:
    """AXE-802 : registre des immobilisations. Lu par la clôture, qui en tire
    les dotations aux amortissements et la sortie des biens cédés."""

    @app.get("/dossiers/{dossier_id}/immobilisations", response_model=RegistreVue)
    def lire_registre(
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
    ) -> RegistreVue:
        _verifier_acces_dossier(dossier.id, identite)
        return _registre(dossier, ledger, provisions)

    @app.post("/dossiers/{dossier_id}/immobilisations", response_model=RegistreVue)
    def declarer_immobilisation(
        entree: DeclarationEntree,
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
    ) -> RegistreVue:
        _verifier_acces_dossier(dossier.id, identite)
        fiche = _declarer(dossier, ledger, entree)
        provisions.ajouter_immobilisation(dossier.tenant_id, dossier.id, fiche)
        return _registre(dossier, ledger, provisions)

    @app.post(
        "/dossiers/{dossier_id}/immobilisations/{immobilisation_id}/cession",
        response_model=RegistreVue,
    )
    def ceder_immobilisation(
        immobilisation_id: str,
        entree: CessionEntree,
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
    ) -> RegistreVue:
        _verifier_acces_dossier(dossier.id, identite)
        fiches = {f.id: f for f in provisions.lister_immobilisations(dossier.tenant_id, dossier.id)}
        fiche = fiches.get(immobilisation_id)
        if fiche is None:
            raise HTTPException(status_code=404, detail="Ce bien n'est pas au registre.")
        cession = Cession(entree.le, entree.prix_cts)
        valider(dataclasses.replace(fiche, cession=cession))
        provisions.enregistrer_cession(dossier.tenant_id, dossier.id, immobilisation_id, cession)
        return _registre(dossier, ledger, provisions)

    _enregistrer_routes_loa(app)


class ContratLoaEntree(BaseModel):
    loueur: str
    vehicule: str
    debut: date
    duree_mois: int
    loyer_mensuel_cts: int
    premier_loyer_cts: int = 0
    prix_levee_cts: int = 0
    co2_g_km: int | None = None


class ContratLoaVue(ContratLoaEntree):
    id: str
    terme: str
    charge_premier_loyer_exercice_cts: int  # part du premier loyer de l'exercice ouvert
    cca_fin_exercice_cts: int  # 486 à la clôture de l'exercice ouvert
    engagement_restant_cts: int  # hors bilan à la clôture : loyers restants + levée


def _vue_contrat(dossier: Dossier, contrat: ContratLoa) -> ContratLoaVue:
    debut, fin = dossier.exercice_debut, dossier.fin_exercice()
    return ContratLoaVue(
        id=contrat.id,
        loueur=contrat.loueur,
        vehicule=contrat.vehicule,
        debut=contrat.debut,
        duree_mois=contrat.duree_mois,
        loyer_mensuel_cts=contrat.loyer_mensuel_cts,
        premier_loyer_cts=contrat.premier_loyer_cts,
        prix_levee_cts=contrat.prix_levee_cts,
        co2_g_km=contrat.co2_g_km,
        terme=terme(contrat).isoformat(),
        charge_premier_loyer_exercice_cts=charge_premier_loyer(contrat, debut, fin),
        cca_fin_exercice_cts=cca(contrat, fin),
        engagement_restant_cts=engagement_restant(contrat, fin),
    )


def _enregistrer_routes_loa(app: FastAPI) -> None:
    """AXE-803 : contrats de LOA. La clôture en tire l'étalement du premier
    loyer (486) et l'engagement hors bilan. La levée d'option se déclare comme
    un achat, dans le registre des immobilisations."""

    @app.get("/dossiers/{dossier_id}/loa", response_model=list[ContratLoaVue])
    def lire_contrats_loa(
        dossier: DossierDep, provisions: ProvisionsDep, identite: IdentiteDep
    ) -> list[ContratLoaVue]:
        _verifier_acces_dossier(dossier.id, identite)
        contrats = provisions.lister_contrats_loa(dossier.tenant_id, dossier.id)
        return [_vue_contrat(dossier, c) for c in contrats]

    @app.post("/dossiers/{dossier_id}/loa", response_model=list[ContratLoaVue])
    def ajouter_contrat_loa(
        entree: ContratLoaEntree,
        dossier: DossierDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
    ) -> list[ContratLoaVue]:
        _verifier_acces_dossier(dossier.id, identite)
        contrat = ContratLoa(
            id=f"loa-{uuid.uuid4().hex[:12]}",
            loueur=entree.loueur.strip(),
            vehicule=entree.vehicule.strip(),
            debut=entree.debut,
            duree_mois=entree.duree_mois,
            loyer_mensuel_cts=entree.loyer_mensuel_cts,
            premier_loyer_cts=entree.premier_loyer_cts,
            prix_levee_cts=entree.prix_levee_cts,
            co2_g_km=entree.co2_g_km,
        )
        valider_contrat_loa(contrat)
        provisions.ajouter_contrat_loa(dossier.tenant_id, dossier.id, contrat)
        contrats = provisions.lister_contrats_loa(dossier.tenant_id, dossier.id)
        return [_vue_contrat(dossier, c) for c in contrats]


def _prouver_cloture(
    dossier: Dossier, signatures: SignatureRepository, signataire: UserId, quand: datetime
) -> None:
    """La validation du chauffeur est la preuve `cloture`. La frise et
    `cloture_faite` ne lisent que sa présence, pas le PDF."""
    if signatures.dernier(dossier.id, TYPE_DOCUMENT_CLOTURE) is not None:
        return
    signatures.enregistrer(
        dossier.id,
        TYPE_DOCUMENT_CLOTURE,
        DocumentSigne(
            contenu_pdf=b"%PDF-1.4\n",
            signataire=signataire,
            signe_le=quand,
            provider="demo",
            qualifie=False,
        ),
    )


def _passage_cloture(
    dossier: Dossier,
    ledger: LedgerService,
    decisions: DecisionRepository,
    avenants: AvenantRegimeRepository,
    provisions: ProvisionsClotureRepository,
) -> PassageExercice:
    return _preparer_cloture(
        dossier, ledger, decisions, avenants, _provisions_saisies(dossier, provisions)
    )


def _vue_cloture_impossible(refus: PassageRefuse, debut: str, fin: str) -> ClotureExerciceVue:
    return ClotureExerciceVue(
        possible=False,
        raison=str(refus),
        code=refus.code,
        exercice_debut=debut,
        exercice_fin=fin,
    )


def _enregistrer_routes_cloture_exercice(app: FastAPI) -> None:
    """Le chauffeur seul valide la clôture. L'attestation est gardée mot pour mot."""

    @app.get("/dossiers/{dossier_id}/cloture-exercice", response_model=ClotureExerciceVue)
    def apercu_cloture(
        dossier: DossierDep,
        ledger: LedgerBaseDep,
        decisions: DecisionsDep,
        avenants: AvenantsDep,
        provisions: ProvisionsDep,
        identite: IdentiteDep,
    ) -> ClotureExerciceVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        debut, fin = dossier.exercice_debut.isoformat(), dossier.fin_exercice().isoformat()
        try:
            passage = _passage_cloture(dossier, ledger, decisions, avenants, provisions)
        except PassageRefuse as refus:
            return _vue_cloture_impossible(refus, debut, fin)
        return ClotureExerciceVue(
            possible=True,
            exercice_debut=debut,
            exercice_fin=fin,
            nouvel_exercice_debut=passage.apres.exercice_debut.isoformat(),
            ecritures=[e.libelle for e in passage.ecritures],
            changements=list(passage.changements),
            attestation=attestation(dossier, _signataire(dossier, identite)),
        )

    @app.post("/dossiers/{dossier_id}/cloture-exercice", response_model=ClotureExerciceVue)
    def valider_cloture(
        corps: ValidationClotureEntree,
        dossier: DossierDep,
        ledger: LedgerBaseDep,
        decisions: DecisionsDep,
        avenants: AvenantsDep,
        dossiers: DossiersDep,
        exercices: ExercicesDep,
        provisions: ProvisionsDep,
        signatures: SignaturesInpiDep,
        identite: IdentiteDep,
    ) -> ClotureExerciceVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        texte = attestation(dossier, _signataire(dossier, identite))
        if corps.attestation != texte:
            raise HTTPException(
                status_code=422, detail="L'attestation ne correspond pas au texte présenté."
            )
        passage = _passage_cloture(dossier, ledger, decisions, avenants, provisions)
        maintenant = datetime.now(UTC).replace(tzinfo=None)
        executer_passage(passage, ledger, dossiers, exercices, maintenant, identite.user_id, texte)
        _prouver_cloture(dossier, signatures, identite.user_id, datetime.now(UTC))
        return ClotureExerciceVue(
            possible=False,
            raison="L'exercice est clos.",
            code="clos",
            exercice_debut=passage.apres.exercice_debut.isoformat(),
            exercice_fin=passage.apres.fin_exercice().isoformat(),
        )


class ScenarioAffectationVue(BaseModel):
    cle: str
    libelle: str
    dividendes_cts: int
    impot_revenu_cts: int
    prelevements_sociaux_cts: int
    part_soumise_cotisations_cts: int
    net_percu_cts: int
    laisse_en_societe_cts: int
    tresorerie_apres_cts: int


class AffectationVue(BaseModel):
    """Ce que le chauffeur peut faire de son résultat, avant qu'il choisisse."""

    applicable: bool
    raison: str | None = None
    annee_exercice: int | None = None
    resultat_cts: int = 0
    reserve_legale_cts: int = 0
    distribuable_cts: int = 0
    disponible_cts: int = 0
    scenarios: list[ScenarioAffectationVue] = []
    avertissements: list[str] = []


class DecisionAffectationEntree(BaseModel):
    scenario: str  # une des clés proposées, ou "libre"
    dividendes_cts: int


def _avertissements(proposition: PropositionAffectation) -> list[str]:
    situation = proposition.situation
    taux = fiscalite(situation.annee_versement)
    textes = [
        f"Dividendes chiffrés au prélèvement forfaitaire unique de {situation.annee_versement} : "
        f"{taux.pfu_impot_revenu * 100:.1f} % d'impôt et "
        f"{taux.prelevements_sociaux * 100:.1f} % de prélèvements sociaux. L'option pour le "
        "barème progressif dépend de votre foyer : à comparer avant de décider.",
        "C'est vous qui décidez, dans les six mois qui suivent la fin de l'exercice.",
    ]
    if situation.gerant_non_salarie:
        textes.append(
            "Gérant non salarié : la part des dividendes au-delà de 10 % du capital supporte des "
            "cotisations sociales, qui ne sont pas chiffrées ici."
        )
    return textes


def _proposer_affectation(
    dossier: Dossier,
    ledger: LedgerService,
    exercices: ExerciceRepository,
    affectations: AffectationRepository,
) -> PropositionAffectation:
    return proposer(dossier, ledger, exercices, affectations, datetime.now(UTC).date())


def _vue_affectation(proposition: PropositionAffectation) -> AffectationVue:
    situation = proposition.situation
    return AffectationVue(
        applicable=True,
        annee_exercice=proposition.annee_exercice,
        resultat_cts=situation.resultat,
        reserve_legale_cts=proposition.reserve_legale,
        distribuable_cts=distribuable(situation),
        disponible_cts=disponible(situation),
        scenarios=[
            ScenarioAffectationVue(
                cle=sc.cle,
                libelle=sc.libelle,
                dividendes_cts=sc.dividendes,
                impot_revenu_cts=sc.impot_revenu,
                prelevements_sociaux_cts=sc.prelevements_sociaux,
                part_soumise_cotisations_cts=sc.part_soumise_cotisations,
                net_percu_cts=sc.net_percu,
                laisse_en_societe_cts=sc.laisse_en_societe,
                tresorerie_apres_cts=sc.tresorerie_apres,
            )
            for sc in proposition.scenarios
        ],
        avertissements=_avertissements(proposition),
    )


def _enregistrer_routes_affectation(app: FastAPI) -> None:
    """Louis, 2026-09-26 : ce que le chauffeur fait de son résultat, c'est
    lui qui le choisit, sur un écran à lui. On chiffre des scénarios, du
    moins au plus de dividendes ; il retient l'un d'eux ou son propre
    montant, dans les limites du distribuable et de la trésorerie."""

    @app.get("/dossiers/{dossier_id}/affectation", response_model=AffectationVue)
    def apercu_affectation(
        dossier: DossierDep,
        ledger: LedgerBaseDep,
        exercices: ExercicesDep,
        affectations: AffectationsDep,
        identite: IdentiteDep,
    ) -> AffectationVue:
        _verifier_acces_dossier(dossier.id, identite)
        try:
            proposition = _proposer_affectation(dossier, ledger, exercices, affectations)
        except (AffectationImpossible, MillesimeDividendesInconnu) as refus:
            return AffectationVue(applicable=False, raison=str(refus))
        return _vue_affectation(proposition)

    @app.post("/dossiers/{dossier_id}/affectation", response_model=AffectationVue)
    def decider_affectation(
        corps: DecisionAffectationEntree,
        dossier: DossierDep,
        ledger: LedgerBaseDep,
        exercices: ExercicesDep,
        affectations: AffectationsDep,
        identite: IdentiteDep,
    ) -> AffectationVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        proposition = _proposer_affectation(dossier, ledger, exercices, affectations)
        proposes = {sc.cle: sc.dividendes for sc in proposition.scenarios}
        if corps.scenario != "libre" and proposes.get(corps.scenario) != corps.dividendes_cts:
            raise HTTPException(status_code=422, detail="Scénario ou montant inconnu.")
        try:
            decider(
                proposition,
                dossier,
                corps.scenario,
                corps.dividendes_cts,
                ledger,
                affectations,
                datetime.now(UTC).replace(tzinfo=None),
                identite.user_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return AffectationVue(
            applicable=False,
            raison=f"Résultat {proposition.annee_exercice} affecté.",
            annee_exercice=proposition.annee_exercice,
        )


class DividendesVue(BaseModel):
    """Versement des dividendes décidés : retenues à la source et 2777."""

    applicable: bool
    raison: str | None = None
    annee_exercice: int | None = None
    brut_cts: int = 0
    declare: bool = False
    verse_le: str | None = None
    dispense_prelevement: bool = False
    prelevement_forfaitaire_cts: int = 0
    csg_cts: int = 0
    crds_cts: int = 0
    solidarite_cts: int = 0
    total_retenu_cts: int = 0
    net_a_virer_cts: int = 0
    echeance_2777: str | None = None


class DeclarationDividendesEntree(BaseModel):
    verse_le: date
    dispense_prelevement: bool = False


class BulletinEntree(BaseModel):
    mois: str  # AAAA-MM
    brut_cts: int
    cotisations_salariales_cts: int
    cotisations_patronales_cts: int
    prelevement_a_la_source_cts: int = 0


class BulletinVue(BaseModel):
    mois: str
    brut_cts: int
    net_a_payer_cts: int


def _vue_dividendes(decides: DividendesDecides, detail: RetenuesDividendes) -> DividendesVue:
    return DividendesVue(
        applicable=True,
        annee_exercice=decides.annee_exercice,
        brut_cts=decides.brut,
        declare=decides.declare is not None,
        verse_le=detail.verse_le.isoformat(),
        dispense_prelevement=detail.dispense_prelevement,
        prelevement_forfaitaire_cts=detail.prelevement_forfaitaire,
        csg_cts=detail.csg,
        crds_cts=detail.crds,
        solidarite_cts=detail.solidarite,
        total_retenu_cts=detail.total_retenu,
        net_a_virer_cts=detail.net_a_virer,
        echeance_2777=detail.echeance_2777.isoformat(),
    )


def _bulletin_vue(ecriture: Ecriture) -> BulletinVue:
    montant = {ligne.compte: ligne.montant.centimes for ligne in ecriture.lignes}
    return BulletinVue(
        mois=(ecriture.reference_piece or "").removeprefix("BULLETIN-"),
        brut_cts=montant.get("641", 0),
        net_a_payer_cts=montant.get("421", 0),
    )


def _enregistrer_routes_dividendes_paie(app: FastAPI) -> None:
    """Après l'affectation : le versement des dividendes (retenues à la
    source, déclaration 2777). Au chauffeur seul, comme le reste de ses
    comptes."""

    @app.get("/dossiers/{dossier_id}/dividendes", response_model=DividendesVue)
    def apercu_dividendes(
        dossier: DossierDep,
        ledger: LedgerBaseDep,
        exercices: ExercicesDep,
        affectations: AffectationsDep,
        identite: IdentiteDep,
    ) -> DividendesVue:
        _verifier_acces_dossier(dossier.id, identite)
        try:
            decides = dividendes_decides(dossier, ledger, exercices, affectations)
            # Pas encore déclaré : aperçu au taux d'aujourd'hui, sans dispense.
            detail = decides.declare or retenues(decides.brut, datetime.now(UTC).date(), False)
        except (AffectationImpossible, MillesimeDividendesInconnu) as exc:
            return DividendesVue(applicable=False, raison=str(exc))
        return _vue_dividendes(decides, detail)

    @app.post("/dossiers/{dossier_id}/dividendes", response_model=DividendesVue)
    def declarer_dividendes(
        corps: DeclarationDividendesEntree,
        dossier: DossierDep,
        ledger: LedgerBaseDep,
        exercices: ExercicesDep,
        affectations: AffectationsDep,
        identite: IdentiteDep,
    ) -> DividendesVue:
        _verifier_acces_dossier(dossier.id, identite)
        decides = dividendes_decides(dossier, ledger, exercices, affectations)
        detail = declarer_versement(
            decides,
            dossier,
            ledger,
            corps.verse_le,
            corps.dispense_prelevement,
            datetime.now(UTC).date(),
        )
        return _vue_dividendes(dataclasses.replace(decides, declare=detail), detail)


def _enregistrer_routes_paie(app: FastAPI) -> None:
    """Paie du président assimilé salarié, saisie depuis son bulletin :
    AxeLCompta n'établit ni bulletin ni DSN, il les passe en comptabilité."""

    @app.get("/dossiers/{dossier_id}/bulletins", response_model=list[BulletinVue])
    def lister_bulletins(
        dossier: DossierDep, ledger: LedgerBaseDep, identite: IdentiteDep
    ) -> list[BulletinVue]:
        _verifier_acces_dossier(dossier.id, identite)
        return [_bulletin_vue(e) for e in bulletins_enregistres(dossier, ledger)]

    @app.post("/dossiers/{dossier_id}/bulletins", response_model=BulletinVue)
    def saisir_bulletin(
        corps: BulletinEntree, dossier: DossierDep, ledger: LedgerBaseDep, identite: IdentiteDep
    ) -> BulletinVue:
        _verifier_acces_dossier(dossier.id, identite)
        bulletin = Bulletin(
            mois=corps.mois,
            brut=corps.brut_cts,
            cotisations_salariales=corps.cotisations_salariales_cts,
            cotisations_patronales=corps.cotisations_patronales_cts,
            prelevement_a_la_source=corps.prelevement_a_la_source_cts,
        )
        ecriture = enregistrer_bulletin(dossier, ledger, bulletin)
        return _bulletin_vue(ecriture)


def _alerte_vue(alerte: Alerte, etat: str) -> AlerteAnomalieVue:
    return AlerteAnomalieVue(
        id=alerte.id,
        code=alerte.code,
        libelle_ui=alerte.libelle_ui,
        detail=alerte.detail,
        etat=etat,
        libelle_mouvement=alerte.libelle_mouvement,
        montant_centimes=alerte.montant_centimes,
        date=alerte.date.isoformat(),
        moyen_paiement=alerte.moyen_paiement,
    )


def _alertes_du_ledger(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
    moyens: Mapping[EcritureId, str] | None = None,
) -> dict[str, Alerte]:
    """Les alertes d'un ledger déjà construit avec les décisions : qui en a
    déjà un ne le relit pas en base."""
    mouvements = _mouvements_surveilles(dossier, ledger, justificatifs, decisions, moyens)
    return {alerte.id: alerte for alerte in analyser(mouvements, _plancher_carburant())}


@functools.cache
def _plancher_carburant() -> int | None:
    """Le plancher carburant du pack (AXE-837), lu une fois."""
    return plancher_de(CATEGORIE_CARBURANT, charger_regles())


def _alertes_du_dossier(
    dossier: Dossier,
    base: LedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
    propositions: PropositionRepository | None = None,
) -> dict[str, Alerte]:
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    moyens = (
        {
            e: p.moyen_paiement
            for e, p in propositions.lister(dossier.id).items()
            if p.moyen_paiement
        }
        if propositions is not None
        else None
    )
    return _alertes_du_ledger(dossier, ledger, decisions, justificatifs, moyens)


def _enregistrer_route_historique_anomalie(app: FastAPI) -> None:
    @app.get(
        "/dossiers/{dossier_id}/anomalies/{alerte_id}/historique",
        response_model=list[EvenementAnomalieVue],
    )
    def historique_anomalie(
        alerte_id: str, dossier: DossierExpertDep, registre: RegistreAnomaliesDep
    ) -> list[EvenementAnomalieVue]:
        """Chaque changement d'état, avec son auteur et sa date (AXE-814)."""
        return [
            EvenementAnomalieVue(
                etat=e.etat, acteur=e.acteur, commentaire=e.commentaire, le=e.le.isoformat()
            )
            for e in registre.historique(dossier.id, alerte_id)
        ]


def _enregistrer_routes_anomalies(app: FastAPI) -> None:
    @app.get("/dossiers/{dossier_id}/anomalies", response_model=list[AlerteAnomalieVue])
    def lister_anomalies(
        dossier: DossierExpertDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        justificatifs: JustificatifsDep,
        propositions: PropositionsDep,
        registre: RegistreAnomaliesDep,
    ) -> list[AlerteAnomalieVue]:
        alertes = _alertes_du_dossier(dossier, base, decisions, justificatifs, propositions)
        etats = registre.etats(dossier.id)
        return [_alerte_vue(alerte, etats.get(alerte.id, "ouverte")) for alerte in alertes.values()]

    @app.post(
        "/dossiers/{dossier_id}/anomalies/{alerte_id}",
        response_model=AlerteAnomalieVue,
    )
    def instruire_anomalie(
        alerte_id: str,
        entree: InstructionAnomalieEntree,
        dossier: DossierExpertDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        justificatifs: JustificatifsDep,
        propositions: PropositionsDep,
        registre: RegistreAnomaliesDep,
        experts: ExpertsDep,
        identite: IdentiteDep,
        role: RoleMembreDep,
    ) -> AlerteAnomalieVue:
        """L'expert qualifie, avec un motif (AXE-800) : la qualification est
        une décision d'expert, tracée avec son auteur."""
        _, identite, actif = _expert(identite, role, experts)
        # Mettre en instruction n'est pas une décision : le motif y est libre.
        motif = (
            entree.commentaire.strip() or "Mise en instruction"
            if entree.decision == "en_instruction"
            else motif_valide(entree.commentaire)
        )
        alertes = _alertes_du_dossier(dossier, base, decisions, justificatifs, propositions)
        alerte = alertes.get(alerte_id)
        if alerte is None:
            raise HTTPException(status_code=404, detail="Alerte inconnue.")
        etat = registre.instruire(
            dossier.id,
            alerte_id,
            entree.decision,
            # L'auteur se lit dans l'historique (AXE-800) : l'e-mail, pas l'uuid.
            identite.email or identite.user_id,
            motif,
            datetime.now(UTC),
        )
        experts.decider(
            _decision_expert(actif, identite, dossier, alerte.ecriture_id, "qualification", motif),
            [],
        )
        return _alerte_vue(alerte, etat)


_CATEGORIES_TICKET = frozenset({"usage_personnel_suspect", "non_categorise_a_verifier"})


def _categories_d_origine(
    dossier: Dossier, ledger: LedgerService, propositions: PropositionRepository | None
) -> dict[EcritureId, str]:
    """AXE-848 : la catégorie du pipeline à la synchro, lue dans la
    proposition enregistrée. En repli, l'ancien suffixe du libellé (écritures
    d'avant le 9 nov., ou sans proposition)."""
    enregistrees = (
        {e: p.categorie for e, p in propositions.lister(dossier.id).items()}
        if propositions is not None
        else {}
    )
    origines: dict[EcritureId, str] = {}
    for ecriture in ledger.grand_livre(dossier.id):
        categorie = enregistrees.get(ecriture.id) or categorie_du_suffixe(ecriture.libelle)
        if categorie:
            origines[ecriture.id] = categorie
    return origines


def _ticket_necessaire(vue: TransactionVue, categorie: str | None) -> bool:
    if vue.montant_cts >= 0 or vue.a_justificatif or vue.statut == "à trancher":
        return False
    if categorie is None:
        return False
    if categorie == CATEGORIE_RETRAIT_ESPECES:
        # AXE-844 : des espèces dépensées pour l'activité demandent leur ticket.
        return vue.categorie not in (None, CATEGORIE_USAGE_PERSONNEL)
    return categorie in _CATEGORIES_TICKET or categorie.startswith("a_verifier")


def _compte_chiffre(compte: str) -> str | None:
    return compte if compte.isdigit() else None


def _compte_suggere(proposition: str | None) -> str | None:
    if not proposition:
        return None
    compte = charger_compte_par_categorie().get(proposition)
    if compte and not est_compte_banque(compte) and not compte.startswith("445"):
        return compte
    return None


def _lignes_imputation(ecriture: Ecriture) -> list[LigneImputationVue]:
    return [
        LigneImputationVue(
            sens="debit" if ligne.sens is Sens.DEBIT else "credit",
            compte=ligne.compte,
            montant_cts=ligne.montant.centimes,
        )
        for ligne in ecriture.lignes
    ]


def _comptes_expert() -> list[CompteChoix]:
    comptes = sorted(
        {
            compte
            for compte in charger_compte_par_categorie().values()
            if not est_compte_banque(compte) and not compte.startswith("445")
        }
    )
    return [CompteChoix(compte=compte, libelle=libelle_compte(compte)) for compte in comptes]


def _sujet_depuis_vue(
    dossier: Dossier, vue: TransactionVue, categorie_origine: str | None = None
) -> SujetExpertVue | None:
    if vue.statut == "à trancher" and vue.categorie == CATEGORIE_A_PRECISER:
        return _sujet(
            dossier,
            f"trancher:{vue.ecriture_id}",
            "gestionnaire",
            "a_trancher",
            vue.libelle,
            "Retrait d'espèces : le chauffeur ne sait plus à quoi il a servi.",
            vue.montant_cts,
            vue.ecriture_id,
            _compte_chiffre(vue.compte),
            None,
        )
    if vue.statut == "à trancher":
        return _sujet(
            dossier,
            f"trancher:{vue.ecriture_id}",
            "chauffeur",
            "a_trancher",
            vue.libelle,
            "Écriture en attente, côté chauffeur",
            vue.montant_cts,
            vue.ecriture_id,
            _compte_chiffre(vue.compte),
            _compte_suggere(vue.proposition),
        )
    if not _ticket_necessaire(vue, categorie_origine):
        return None
    return _sujet(
        dossier,
        f"ticket:{vue.ecriture_id}",
        "chauffeur",
        "ticket",
        vue.libelle,
        "Ticket manquant pour classer la dépense",
        vue.montant_cts,
        vue.ecriture_id,
        _compte_chiffre(vue.compte),
        _compte_suggere(vue.proposition),
    )


def _sujets_anomalies(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
    registre: InstructionsRepository | None,
    exclues: frozenset[EcritureId],
) -> list[SujetExpertVue]:
    """`registre` à None : toutes les alertes, qualifiées ou non (ce que garde
    le cache de la file, AXE-824 ; l'état se filtre à la lecture)."""
    sujets: list[SujetExpertVue] = []
    alertes = _alertes_du_ledger(dossier, ledger, decisions, justificatifs)
    etats = {} if registre is None else registre.etats(dossier.id)
    ecritures = {e.id: e for e in ledger.grand_livre(dossier.id)}
    for alerte in alertes.values():
        if alerte.ecriture_id in exclues:
            continue
        sujet = _sujet_selon_etat(
            dossier, alerte, etats.get(alerte.id, "ouverte"), ecritures.get(alerte.ecriture_id)
        )
        if sujet is not None:
            sujets.append(sujet)
    return sujets


def est_banque_ou_tva(compte: str) -> bool:
    return compte.startswith("512") or compte.startswith("445")


def _reclassement_personnel(
    dossier: Dossier, alerte: Alerte, ecriture: Ecriture | None
) -> SujetExpertVue | None:
    """Alerte qualifiée « usage personnel » (AXE-814) : le reclassement vers
    455 (108 en EI, matrice des statuts) est **proposé** dans la file, jamais
    écrit. L'expert-comptable ou le chauffeur le valide par une imputation.
    Rien à proposer si l'écriture y est déjà, ou si le statut ne prévoit pas
    de compte (usage personnel signalé sans écriture)."""
    cible = configuration_de(dossier).comptes_categories_statut().get("usage_personnel")
    if cible is None or ecriture is None:
        return None
    actuels = {ligne.compte for ligne in ecriture.lignes if not est_banque_ou_tva(ligne.compte)}
    if cible in actuels:
        return None
    return _sujet(
        dossier,
        f"reclassement:{alerte.id}",
        "gestionnaire",
        "anomalie",
        alerte.libelle_mouvement,
        f"Usage personnel retenu : reclassement proposé en {cible}, à valider.",
        alerte.montant_centimes,
        str(alerte.ecriture_id),
        compte_actuel=min(actuels) if actuels else None,
        compte_suggere=cible,
    )


def _sujet_selon_etat(
    dossier: Dossier, alerte: Alerte, etat: str, ecriture: Ecriture | None
) -> SujetExpertVue | None:
    if etat == "usage_personnel":
        return _reclassement_personnel(dossier, alerte, ecriture)
    if etat not in ("ouverte", "en_instruction"):
        return None
    return _sujet(
        dossier,
        f"{PREFIXE_ANOMALIE}{alerte.id}",
        "gestionnaire",
        "anomalie",
        alerte.libelle_ui,
        alerte.detail,
        alerte.montant_centimes,
        str(alerte.ecriture_id),
    )


PREFIXE_ANOMALIE = "anomalie:"
# Ce que la file expert lit de chaque dossier.
SourcesExpert = tuple[
    LedgerService, DecisionRepository, JustificatifRepository, PropositionRepository
]


def _sujets_ecarts(dossier: Dossier) -> list[SujetExpertVue]:
    """Un écart de registre non tranché, visible dans la file. Calculé à
    l'affichage : le résoudre ne change pas la version des agrégats, donc
    un sujet gardé en cache resterait affiché après la décision."""
    return [
        SujetExpertVue(
            id=f"registre:{dossier.id}:{ecart.champ}",
            dossier_id=str(dossier.id),
            dossier_nom=dossier.nom,
            cote="gestionnaire",
            nature="registre",
            libelle="Le registre officiel dit autre chose",
            detail=phrase_gestionnaire(ecart),
            montant_cts=None,
            ecriture_id=None,
            imputable=False,
        )
        for ecart in dossier.ecarts_registre
    ]


def _sujets_du_portefeuille(
    portefeuille: Sequence[Dossier],
    sources: SourcesExpert,
    agregats: AgregatsRepository,
    cache: CacheFileExpert,
) -> list[SujetExpertVue]:
    """Sujets gardés quand la version du dossier n'a pas bougé, recalculés
    sinon (AXE-824). La version est lue **avant** le calcul : une écriture
    arrivée pendant le calcul la fait monter, le prochain affichage refait."""
    base, decisions, justificatifs, propositions = sources
    ids = [dossier.id for dossier in portefeuille]
    versions = {d: ligne.version for d, ligne in agregats.lire(ids).items()}
    gardes = cache.lire(ids)
    sujets: list[SujetExpertVue] = []
    for dossier in portefeuille:
        version = versions.get(dossier.id, 0)
        garde = gardes.get(dossier.id)
        if garde is not None and garde.valables(version):
            calcules = [SujetExpertVue.model_validate(s) for s in garde.sujets]
        else:
            calcules = _sujets_expert(
                dossier, base, decisions, justificatifs, None, propositions=propositions
            )
            cache.enregistrer(dossier.id, version, [s.model_dump() for s in calcules])
        sujets.extend(calcules)
        sujets.extend(_sujets_ecarts(dossier))
    return sujets


def _sujets_expert(
    dossier: Dossier,
    base: LedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
    registre: InstructionsRepository | None,
    avec_anomalies: bool = True,
    propositions: PropositionRepository | None = None,
) -> list[SujetExpertVue]:
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    exclues = annulees(ledger.grand_livre(dossier.id))
    origines = _categories_d_origine(dossier, ledger, propositions)
    sujets = [
        sujet
        for vue in _avec_categories(
            _vues_dossier(dossier, ledger, justificatifs), decisions.lister_decisions(dossier.id)
        )
        if EcritureId(vue.ecriture_id) not in exclues
        if (sujet := _sujet_depuis_vue(dossier, vue, origines.get(EcritureId(vue.ecriture_id))))
        is not None
    ]
    if avec_anomalies:
        sujets.extend(
            _sujets_anomalies(dossier, ledger, decisions, justificatifs, registre, exclues)
        )
    return sujets


def _sujet(
    dossier: Dossier,
    sujet_id: str,
    cote: Literal["chauffeur", "gestionnaire"],
    nature: Literal["a_trancher", "ticket", "anomalie", "registre"],
    libelle: str,
    detail: str,
    montant_cts: int,
    ecriture_id: str,
    compte_actuel: str | None = None,
    compte_suggere: str | None = None,
) -> SujetExpertVue:
    return SujetExpertVue(
        id=sujet_id,
        dossier_id=str(dossier.id),
        dossier_nom=dossier.nom,
        cote=cote,
        nature=nature,
        libelle=libelle,
        detail=detail,
        montant_cts=montant_cts,
        ecriture_id=ecriture_id,
        imputable=True,
        compte_actuel=compte_actuel,
        compte_suggere=compte_suggere,
    )


def imputer_ecriture(
    entree: ImputationEntree,
    dossiers: DossiersDep,
    base: LedgerBaseDep,
    decisions: DecisionsDep,
    justificatifs: JustificatifsDep,
    registre: RegistreAnomaliesDep,
    propositions: PropositionsDep,
    experts: ExpertsDep,
    role: RoleMembreDep,
    identite: IdentiteDep,
) -> ImputationVue:
    """Pose la contre-passation et la nouvelle écriture. L'originale reste.
    AXE-800 : réservé à l'expert habilité sur ce dossier ; la décision (auteur,
    motif, version de l'engagement) s'écrit avec ses écritures, tout ou rien.
    La réponse dit ce qui a été écrit, et les sujets à jour de ce dossier seul."""
    tenant_id, identite, actif = _expert(identite, role, experts)
    motif = motif_valide(entree.motif)
    dossier = _dossier_de_l_expert(dossiers, tenant_id, actif, entree.dossier_id)
    connus = {ecriture.id: ecriture for ecriture in base.grand_livre(dossier.id)}
    ecriture = connus.get(EcritureId(entree.ecriture_id))
    if ecriture is None:
        raise HTTPException(status_code=404, detail="Écriture inconnue.")
    periodes = base.periodes_closes(dossier.id)
    inverse, nouvelle = preparer_imputation(
        ecriture, entree.compte, set(connus), periodes, dossier.exercice_debut
    )
    # AXE-420 : la décision du chauffeur ne doit pas rester chargée en plus.
    annulations = annuler_reclassements(
        ecriture.id, list(connus.values()), periodes, dossier.exercice_debut
    )
    experts.decider(
        _decision_expert(actif, identite, dossier, ecriture.id, "imputation", motif),
        [inverse, *annulations, nouvelle],
    )
    sujets = _avec_moyens_de_paiement(
        _sujets_expert(
            dossier, base, decisions, justificatifs, registre, propositions=propositions
        ),
        propositions,
    )
    sujets = [*sujets, *_sujets_ecarts(dossier)]
    return ImputationVue(
        ecriture_id=nouvelle.id,
        contrepassation_id=inverse.id,
        lignes=_lignes_imputation(nouvelle),
        sujets=sujets,
    )


def annuler_imputation(
    entree: AnnulationImputationEntree,
    dossiers: DossiersDep,
    base: LedgerBaseDep,
    experts: ExpertsDep,
    role: RoleMembreDep,
    identite: IdentiteDep,
) -> None:
    """Contre-passe la nouvelle écriture et l'inverse posé par l'imputation.
    Le solde revient à l'écriture d'origine. AXE-800 : par l'expert, avec un
    motif, tout ou rien."""
    tenant_id, identite, actif = _expert(identite, role, experts)
    motif = motif_valide(entree.motif)
    dossier = _dossier_de_l_expert(dossiers, tenant_id, actif, entree.dossier_id)
    connus = {ecriture.id: ecriture for ecriture in base.grand_livre(dossier.id)}
    periodes = base.periodes_closes(dossier.id)
    inverses: list[Ecriture] = []
    for identifiant in (entree.ecriture_id, entree.contrepassation_id):
        ecriture = connus.get(EcritureId(identifiant))
        if ecriture is None:
            raise HTTPException(status_code=404, detail="Écriture inconnue.")
        inverse = contrepasser(ecriture, periodes, dossier.exercice_debut)
        if inverse.id not in connus:
            inverses.append(inverse)
            connus[inverse.id] = inverse
    experts.decider(
        _decision_expert(
            actif, identite, dossier, EcritureId(entree.ecriture_id), "annulation", motif
        ),
        inverses,
    )


def _dossier_de_l_expert(
    dossiers: DossierRepository, tenant_id: TenantId, actif: ExpertActif, dossier_id: str
) -> Dossier:
    dossier = dossiers.obtenir(DossierId(dossier_id))
    if dossier is None or dossier.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Dossier inconnu.")
    exiger_dossier(actif, dossier.id)
    return dossier


def _decision_expert(
    actif: ExpertActif,
    identite: IdentiteAuthentifiee,
    dossier: Dossier,
    ecriture_id: EcritureId | None,
    nature: Literal["imputation", "annulation", "qualification"],
    motif: str,
) -> DecisionExpert:
    return DecisionExpert(
        id=uuid.uuid4().hex,
        tenant_id=dossier.tenant_id,
        dossier_id=dossier.id,
        ecriture_id=ecriture_id,
        nature=nature,
        motif=motif,
        auteur=identite.user_id,
        auteur_nom=actif.habilitation.nom,
        version_engagement=actif.engagement.version,
        le=datetime.now(UTC),
    )


def _avec_moyens_de_paiement(
    sujets: list[SujetExpertVue], propositions: PropositionRepository
) -> list[SujetExpertVue]:
    """AXE-855 : le moyen de paiement de chaque sujet lié à une opération,
    en une lecture pour toute la file. Lu à l'affichage, pas gardé dans le
    cache des sujets (AXE-824) : un sujet déjà gardé l'a aussi."""
    ids = [EcritureId(s.ecriture_id) for s in sujets if s.ecriture_id is not None]
    moyens = propositions.moyens_de_paiement(ids)
    return [
        s.model_copy(update={"moyen_paiement": moyens.get(EcritureId(s.ecriture_id))})
        if s.ecriture_id is not None and EcritureId(s.ecriture_id) in moyens
        else s
        for s in sujets
    ]


def _sujets_qualifies(
    sujets: list[SujetExpertVue],
    portefeuille: Sequence[Dossier],
    etat: EtatTags,
    registre: InstructionsRepository,
    sources: SourcesExpert,
) -> list[SujetExpertVue]:
    """Le cache garde toutes les alertes. Tags d'anomalies et qualifications
    s'appliquent à la lecture (AXE-814, AXE-829)."""
    par_dossier = {dossier.id: dossier for dossier in portefeuille}
    concernes = {DossierId(sujet.dossier_id) for sujet in sujets if sujet.nature == "anomalie"}
    etats = {dossier_id: registre.etats(dossier_id) for dossier_id in concernes}
    a_refaire = {
        dossier_id
        for dossier_id, courant in etats.items()
        if "usage_personnel" in courant.values() and not etat.exclu(dossier_id, "anomalies")
    }
    gardes = [sujet for sujet in sujets if _sujet_visible(sujet, etat, etats, a_refaire)]
    for dossier_id in a_refaire:
        gardes.extend(_anomalies_fraiches(par_dossier[dossier_id], registre, sources))
    return gardes


def _sujet_visible(
    sujet: SujetExpertVue,
    etat: EtatTags,
    etats: dict[DossierId, dict[str, str]],
    a_refaire: set[DossierId],
) -> bool:
    if sujet.nature != "anomalie":
        return True
    dossier_id = DossierId(sujet.dossier_id)
    if etat.exclu(dossier_id, "anomalies") or dossier_id in a_refaire:
        return False
    if not sujet.id.startswith(PREFIXE_ANOMALIE):
        return True
    courant = etats[dossier_id].get(sujet.id.removeprefix(PREFIXE_ANOMALIE), "ouverte")
    return courant in ("ouverte", "en_instruction")


def _anomalies_fraiches(
    dossier: Dossier,
    registre: InstructionsRepository,
    sources: SourcesExpert,
) -> list[SujetExpertVue]:
    """Reconstruit les anomalies d'un dossier qualifié en usage personnel :
    le cache ne contient pas la proposition de reclassement."""
    base, decisions, justificatifs, _propositions = sources
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    exclues = annulees(ledger.grand_livre(dossier.id))
    return _sujets_anomalies(dossier, ledger, decisions, justificatifs, registre, exclues)


def _enregistrer_routes_expert(app: FastAPI) -> None:
    @app.get("/expert/file", response_model=FileExpertVue)
    def lire_file_expert(
        dossiers: DossiersDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        justificatifs: JustificatifsDep,
        registre: RegistreAnomaliesDep,
        tags: TagsDep,
        agregats: AgregatsDep,
        cache: CacheFileExpertDep,
        propositions: PropositionsDep,
        experts: ExpertsDep,
        role: RoleMembreDep,
        identite: IdentiteDep,
    ) -> FileExpertVue:
        """File de l'expert-comptable. Seuls les dossiers changés sont
        recalculés (AXE-824). Un tag peut exclure un dossier du mode expert
        ou de ses anomalies (AXE-829). AXE-800 : réservée à l'expert habilité,
        sur les dossiers de sa lettre de mission."""
        tenant_id, _identite, actif = _expert(identite, role, experts)
        etat = etat_du_portefeuille(tags, tenant_id)
        portefeuille = tuple(
            d
            for d in dossiers.lister_par_tenant(tenant_id)
            if not etat.exclu(d.id, "expert") and actif.couvre(d.id)
        )
        sources = (base, decisions, justificatifs, propositions)
        sujets = _avec_moyens_de_paiement(
            _sujets_qualifies(
                _sujets_du_portefeuille(portefeuille, sources, agregats, cache),
                portefeuille,
                etat,
                registre,
                sources,
            ),
            propositions,
        )
        presents = {sujet.dossier_id for sujet in sujets}
        return FileExpertVue(
            sujets=sujets,
            comptes=_comptes_expert(),
            tags_par_dossier={
                str(d): sorted(t) for d, t in etat.par_dossier.items() if str(d) in presents and t
            },
        )

    app.post("/expert/imputations", response_model=ImputationVue)(imputer_ecriture)
    app.post("/expert/imputations/annuler", status_code=204)(annuler_imputation)
    _enregistrer_routes_classees(app)
    _enregistrer_route_verdict(app)


PAR_PAGE_CLASSEES = 50


class OperationClasseeVue(BaseModel):
    dossier_id: str
    dossier_nom: str
    ecriture_id: str
    date: str
    libelle: str
    montant_cts: int
    compte: str
    categorie: str | None
    origine: str
    confiance: float | None
    statut: str
    sens: str
    verdict: str | None
    tva_estimee_cts: int | None = None
    tva_relevee_cts: int | None = None


class CompteursClasseesVue(BaseModel):
    auto: int
    chauffeur: int
    expert: int
    justes: int
    fausses: int


class OperationsClasseesVue(BaseModel):
    operations: list[OperationClasseeVue]
    total: int
    page: int
    pages: int
    compteurs: CompteursClasseesVue
    categories: list[str]


class VerdictEntree(BaseModel):
    dossier_id: str
    ecriture_id: str
    verdict: Literal["juste", "faux"]


def _operations_du_dossier(
    dossier: Dossier,
    base: LedgerService,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
) -> list[OperationClassee]:
    """Une lecture par source et par dossier : grand livre, décisions,
    propositions. Aucune proposition recalculée. Le verdict n'est pas ici :
    il se pose à la lecture, sans périmer ce calcul."""
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    en_vigueur: dict[EcritureId, str] = {}
    for decision in decisions.lister_decisions(dossier.id):
        if decision.categorie == CATEGORIE_ANNULATION:
            en_vigueur.pop(decision.ecriture_id, None)
        else:
            en_vigueur[decision.ecriture_id] = decision.categorie
    return classer_operations(
        ledger.grand_livre(dossier.id),
        propositions.lister(dossier.id),
        en_vigueur,
        {},
        dossier.regime_tva,
    )


def _vue_classee(operation: OperationClassee, noms: dict[DossierId, str]) -> OperationClasseeVue:
    return OperationClasseeVue(
        dossier_id=str(operation.dossier_id),
        dossier_nom=noms.get(operation.dossier_id, str(operation.dossier_id)),
        ecriture_id=str(operation.ecriture_id),
        date=operation.date.isoformat(),
        libelle=operation.libelle,
        montant_cts=operation.montant_cts,
        compte=operation.compte,
        categorie=operation.categorie,
        origine=operation.origine,
        confiance=operation.confiance,
        statut=operation.statut,
        sens=operation.sens,
        verdict=operation.verdict,
        tva_estimee_cts=operation.tva_estimee_cts,
        tva_relevee_cts=operation.tva_relevee_cts,
    )


def _page_classees(
    operations: list[OperationClassee], filtres: Filtres, tri: str, page: int
) -> tuple[list[OperationClassee], int, int]:
    """(tranche de la page, total filtré, nombre de pages)."""
    gardees = trier((o for o in operations if filtres.garde(o)), tri)
    pages = max(1, -(-len(gardees) // PAR_PAGE_CLASSEES))
    courante = min(max(1, page), pages)
    debut = (courante - 1) * PAR_PAGE_CLASSEES
    return gardees[debut : debut + PAR_PAGE_CLASSEES], len(gardees), pages


def _operations_gardees(
    portefeuille: Sequence[Dossier],
    base: LedgerService,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
    agregats: AgregatsRepository,
    cache: CacheFileExpert,
) -> list[OperationClassee]:
    """Gardées tant que la version du dossier n'a pas bougé (AXE-824).
    La version est lue avant le calcul : une écriture arrivée pendant le
    calcul la fait monter, le prochain affichage refait."""
    ids = [dossier.id for dossier in portefeuille]
    versions = {dossier_id: ligne.version for dossier_id, ligne in agregats.lire(ids).items()}
    gardes = cache.lire(ids)
    operations: list[OperationClassee] = []
    for dossier in portefeuille:
        version = versions.get(dossier.id, 0)
        garde = gardes.get(dossier.id)
        if garde is not None and garde.valables(version, VERSION_CLASSEES):
            operations.extend(_operation_depuis_json(ligne) for ligne in garde.sujets)
            continue
        calcules = _operations_du_dossier(dossier, base, decisions, propositions)
        cache.enregistrer(
            dossier.id, version, [_operation_json(operation) for operation in calcules]
        )
        operations.extend(calcules)
    return operations


def _poser_verdicts(
    operations: list[OperationClassee],
    verdicts: VerdictsRepository,
    dossier_ids: Sequence[DossierId],
) -> list[OperationClassee]:
    """Le verdict change sans écriture : une lecture, pas un recalcul."""
    par_dossier = verdicts.derniers_de(dossier_ids)
    return [
        dataclasses.replace(
            operation,
            verdict=par_dossier.get(operation.dossier_id, {}).get(operation.ecriture_id),
        )
        for operation in operations
    ]


def _operation_json(operation: OperationClassee) -> dict[str, Any]:
    return {
        "dossier_id": str(operation.dossier_id),
        "ecriture_id": str(operation.ecriture_id),
        "date": operation.date.isoformat(),
        "libelle": operation.libelle,
        "montant_cts": operation.montant_cts,
        "compte": operation.compte,
        "categorie": operation.categorie,
        "origine": operation.origine,
        "confiance": operation.confiance,
        "statut": operation.statut,
        "tva_estimee_cts": operation.tva_estimee_cts,
        "tva_relevee_cts": operation.tva_relevee_cts,
    }


def _operation_depuis_json(ligne: dict[str, Any]) -> OperationClassee:
    confiance = ligne["confiance"]
    return OperationClassee(
        dossier_id=DossierId(str(ligne["dossier_id"])),
        ecriture_id=EcritureId(str(ligne["ecriture_id"])),
        date=date.fromisoformat(str(ligne["date"])),
        libelle=str(ligne["libelle"]),
        montant_cts=int(ligne["montant_cts"]),
        compte=str(ligne["compte"]),
        categorie=None if ligne["categorie"] is None else str(ligne["categorie"]),
        origine=str(ligne["origine"]),
        confiance=None if confiance is None else float(confiance),
        statut=cast(Statut, str(ligne["statut"])),
        tva_estimee_cts=None
        if ligne.get("tva_estimee_cts") is None
        else int(ligne["tva_estimee_cts"]),
        tva_relevee_cts=None
        if ligne.get("tva_relevee_cts") is None
        else int(ligne["tva_relevee_cts"]),
    )


def _enregistrer_routes_classees(app: FastAPI) -> None:
    @app.get("/expert/classees", response_model=OperationsClasseesVue)
    def lire_classees(  # noqa: PLR0913 — un paramètre par filtre de l'URL
        dossiers: DossiersDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        propositions: PropositionsDep,
        verdicts: VerdictsDep,
        agregats: AgregatsDep,
        cache: CacheClasseesDep,
        experts: ExpertsDep,
        role: RoleMembreDep,
        identite: IdentiteDep,
        statut: Statut | None = None,
        origine: str | None = None,
        categorie: str | None = None,
        tranche: str | None = None,
        sens: str | None = None,
        dossier: str | None = None,
        tri: str = "recentes",
        page: int = 1,
    ) -> OperationsClasseesVue:
        """Opérations déjà classées du portefeuille (AXE-823), filtrées et
        paginées côté serveur. Seuls les dossiers dont la version a bougé
        sont recalculés (AXE-824). Les compteurs portent sur tout le
        portefeuille. Les verdicts sont relus à chaque affichage."""
        tenant_id, _identite, actif = _expert(identite, role, experts)
        portefeuille = [
            d
            for d in dossiers.lister_par_tenant(tenant_id)
            if dossier in (None, str(d.id)) and actif.couvre(d.id)
        ]
        noms = {d.id: d.nom for d in portefeuille}
        operations = _poser_verdicts(
            _operations_gardees(portefeuille, base, decisions, propositions, agregats, cache),
            verdicts,
            [d.id for d in portefeuille],
        )
        filtres = Filtres(statut, origine, categorie, tranche, sens)
        tranche_page, total, pages = _page_classees(operations, filtres, tri, page)
        compteurs = compter(operations)
        return OperationsClasseesVue(
            operations=[_vue_classee(o, noms) for o in tranche_page],
            total=total,
            page=min(max(1, page), pages),
            pages=pages,
            compteurs=CompteursClasseesVue(**dataclasses.asdict(compteurs)),
            categories=sorted({o.categorie for o in operations if o.categorie}),
        )


def _enregistrer_route_verdict(app: FastAPI) -> None:
    @app.post("/expert/classees/verdict", status_code=204)
    def noter_verdict(
        entree: VerdictEntree,
        dossiers: DossiersDep,
        verdicts: VerdictsDep,
        experts: ExpertsDep,
        role: RoleMembreDep,
        identite: IdentiteDep,
    ) -> None:
        """« Juste » ou « faux », sans écriture. « Faux » ne corrige rien :
        l'imputation reste un geste à part (mode expert)."""
        tenant_id, identite_ok, actif = _expert(identite, role, experts)
        dossier = _dossier_de_l_expert(dossiers, tenant_id, actif, entree.dossier_id)
        verdicts.noter(
            dossier.id,
            EcritureId(entree.ecriture_id),
            entree.verdict,
            identite_ok.user_id,
            datetime.now(UTC),
        )


class EntreeQuarantaineVue(BaseModel):
    id: str
    motif: str
    libelle_motif: str
    date: str | None
    libelle: str | None
    montant_cts: int | None
    resoluble: bool
    decision: str | None
    resolue_par: str | None
    resolue_le: str | None


class ResolutionEntree(BaseModel):
    decision: Literal["accepter", "ignorer"]


def _entree_vue(
    dossier: Dossier, entree: EntreeQuarantaine, resolution: Resolution | None
) -> EntreeQuarantaineVue:
    famille = famille_du_motif(entree.motif)
    try:
        transaction = normaliser_payload(dict(entree.payload), dossier.id)
    except ValueError:
        transaction = None
    return EntreeQuarantaineVue(
        id=entree.id,
        motif=famille,
        libelle_motif=LIBELLES_MOTIF.get(famille, "Ligne bancaire illisible"),
        date=transaction.date.isoformat() if transaction else None,
        libelle=transaction.libelle if transaction else None,
        montant_cts=transaction.montant_cts if transaction else None,
        resoluble=famille in LIBELLES_MOTIF,
        decision=resolution.decision if resolution else None,
        resolue_par=resolution.par if resolution else None,
        resolue_le=resolution.le.isoformat() if resolution else None,
    )


def _resoudre_quarantaine(
    dossier: Dossier,
    entree: EntreeQuarantaine,
    decision: Literal["accepter", "ignorer"],
    base: LedgerService,
    resolutions: ResolutionsRepository,
    par: str,
) -> Resolution:
    """La résolution d'abord (une seule par entrée, l'unicité tranche deux
    clics simultanés), puis les écritures."""
    ecritures = base.grand_livre(dossier.id)
    origine_id = id_ecriture(dossier, entree.source, entree.transaction_id or "")
    a_ecrire = ecritures_de_resolution(
        entree,
        decision,
        origine_id,
        ecritures,
        lambda payload, d: normaliser_payload(dict(payload), d),
        base.periodes_closes(dossier.id),
    )
    resolution = Resolution(
        dossier.id, entree.id, decision, tuple(e.id for e in a_ecrire), par, datetime.now(UTC)
    )
    resolutions.enregistrer(resolution)
    for ecriture in a_ecrire:
        base.enregistrer(ecriture)
    return resolution


def _enregistrer_routes_quarantaine(app: FastAPI) -> None:
    @app.get("/dossiers/{dossier_id}/quarantaine", response_model=list[EntreeQuarantaineVue])
    def lister_quarantaine(
        dossier: DossierExpertDep,
        journal: JournalIngestionDep,
        resolutions: ResolutionsDep,
    ) -> list[EntreeQuarantaineVue]:
        """Opérations bancaires que la synchro n'a pas pu écrire seule (AXE-424)."""
        resolues = resolutions.lister(dossier.id)
        return [
            _entree_vue(dossier, entree, resolues.get(entree.id))
            for entree in journal.lister_quarantaine(dossier.id)
        ]

    @app.post("/dossiers/{dossier_id}/quarantaine/{entree_id}", response_model=EntreeQuarantaineVue)
    def resoudre_quarantaine(
        entree_id: str,
        corps: ResolutionEntree,
        dossier: DossierExpertDep,
        journal: JournalIngestionDep,
        resolutions: ResolutionsDep,
        base: LedgerBaseDep,
        role: RoleMembreDep,
        identite: IdentiteDep,
    ) -> EntreeQuarantaineVue:
        """Accepter passe le nouveau montant (ou l'opération datée d'un
        exercice clos) ; ignorer laisse le grand livre tel quel."""
        _, identite_ok = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture ne traite pas une opération bancaire.")
        entree = next(
            (e for e in journal.lister_quarantaine(dossier.id) if e.id == entree_id), None
        )
        if entree is None:
            raise HTTPException(status_code=404, detail="Opération introuvable.")
        try:
            resolution = _resoudre_quarantaine(
                dossier,
                entree,
                corps.decision,
                base,
                resolutions,
                identite_ok.email or identite_ok.user_id,
            )
        except ResolutionRefusee as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _entree_vue(dossier, entree, resolution)


def get_contacts_proposes() -> ContactsProposesRepository:
    return PostgresContactsProposes(_engine())


ContactsProposesDep = Annotated[ContactsProposesRepository, Depends(get_contacts_proposes)]


def get_demandes_jobs() -> DemandesDeJobs:
    """Le gestionnaire dépose et suit ses demandes ; le worker les exécute."""
    return FilePostgres(_engine())


DemandesJobsDep = Annotated[DemandesDeJobs, Depends(get_demandes_jobs)]


def get_envois() -> EnvoisRepository:
    """Intégrations d'envoi et envois des rappels (AXE-808)."""
    return PostgresEnvois(_engine())


EnvoisDep = Annotated[EnvoisRepository, Depends(get_envois)]


def get_branchements() -> BranchementsRepository:
    """Intégrations du portefeuille, plusieurs par type (AXE-872)."""
    return PostgresBranchements(_engine())


BranchementsDep = Annotated[BranchementsRepository, Depends(get_branchements)]


class IntegrationsEnvoiVue(BaseModel):
    """Canal branché → date du dernier réglage. Jamais un identifiant."""

    canaux: dict[str, str]


class BranchementEntree(BaseModel):
    type: str
    fournisseur: str
    nom: str
    parametres: dict[str, str]


class BranchementModification(BaseModel):
    """Champs absents : inchangés. `parametres` remplace tous les identifiants."""

    nom: str | None = None
    parametres: dict[str, str] | None = None
    par_defaut: bool | None = None
    actif: bool | None = None


class BranchementVue(BaseModel):
    """Jamais un jeton, une clé ou un mot de passe. `secrets` ne porte que
    les noms des champs déjà chiffrés."""

    id: str
    type: str
    fournisseur: str
    nom: str
    par_defaut: bool
    actif: bool
    maj_le: str | None
    champs: dict[str, str] = {}
    secrets: list[str] = []


class EssaiVue(BaseModel):
    statut: str  # ok | echec | indisponible
    message: str


class FicheWebhookVue(BaseModel):
    """Valeurs à reporter dans le formulaire Rollee. Le secret est chiffré
    au repos ; il ne sort qu'ici, pour l'admin qui relie ce compte."""

    url: str
    secret: str
    methode: str
    evenements: list[str]
    joignable: bool


class ChoixDossierEntree(BaseModel):
    """`None` : le dossier revient au branchement par défaut."""

    branchement_id: str | None


class ChoixDossierVue(BaseModel):
    """Type → branchement choisi pour ce dossier (absent : celui par défaut)."""

    choix: dict[str, str]


class EnvoiVue(BaseModel):
    canal: str
    statut: str
    tentatives: int
    raison: str | None
    le: str | None
    branchement: str | None = None  # nom du branchement par lequel il est parti


class DesinscriptionVue(BaseModel):
    message: str


def _vue_branchement(b: Branchement) -> BranchementVue:
    champs, secrets = lecture_publique(b)
    return BranchementVue(
        id=b.id,
        type=b.type,
        fournisseur=b.fournisseur,
        nom=b.nom,
        par_defaut=b.par_defaut,
        actif=b.actif,
        maj_le=b.maj_le.isoformat() if b.maj_le else None,
        champs=champs,
        secrets=list(secrets),
    )


def _admin_du_portefeuille(
    identite: IdentiteAuthentifiee | None, role: str
) -> tuple[TenantId, str]:
    tenant_id, identite = _verifier_acces_gestionnaire(identite)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Réservé à un administrateur.")
    return tenant_id, str(identite.user_id)


def _enregistrer_routes_branchements(app: FastAPI) -> None:
    """AXE-872 : plusieurs intégrations de chaque type, une par défaut. Les
    identifiants sont chiffrés, et ne reviennent jamais à l'écran."""

    @app.get("/portefeuille/integrations", response_model=list[BranchementVue])
    def lister_branchements(
        identite: IdentiteDep, branchements: BranchementsDep
    ) -> list[BranchementVue]:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return [_vue_branchement(b) for b in branchements.lister(tenant_id)]

    @app.post("/portefeuille/integrations", response_model=list[BranchementVue])
    def ajouter_branchement(
        entree: BranchementEntree,
        identite: IdentiteDep,
        role: RoleMembreDep,
        branchements: BranchementsDep,
    ) -> list[BranchementVue]:
        tenant_id, par = _admin_du_portefeuille(identite, role)
        existants = branchements.lister(tenant_id)
        cree = nouveau(
            existants, tenant_id, entree.type, entree.fournisseur, entree.nom, entree.parametres
        )
        branchements.enregistrer([cree], par, datetime.now(UTC))
        return [_vue_branchement(b) for b in branchements.lister(tenant_id)]

    @app.patch("/portefeuille/integrations/{branchement_id}", response_model=list[BranchementVue])
    def modifier_branchement(
        branchement_id: str,
        entree: BranchementModification,
        identite: IdentiteDep,
        role: RoleMembreDep,
        branchements: BranchementsDep,
    ) -> list[BranchementVue]:
        tenant_id, par = _admin_du_portefeuille(identite, role)
        modification = Modification(
            nom=entree.nom,
            parametres=entree.parametres,
            par_defaut=entree.par_defaut,
            actif=entree.actif,
        )
        a_enregistrer = modifier(branchements.lister(tenant_id), branchement_id, modification)
        branchements.enregistrer(a_enregistrer, par, datetime.now(UTC))
        return [_vue_branchement(b) for b in branchements.lister(tenant_id)]


def _enregistrer_route_tester_branchement(app: FastAPI) -> None:
    """AXE-872 : « Tester » contacte le fournisseur sans rien envoyer."""

    @app.post("/portefeuille/integrations/{branchement_id}/tester", response_model=EssaiVue)
    def tester_un_branchement(
        branchement_id: str,
        identite: IdentiteDep,
        role: RoleMembreDep,
        branchements: BranchementsDep,
    ) -> EssaiVue:
        tenant_id, par = _admin_du_portefeuille(identite, role)
        branchement = next(
            (b for b in branchements.lister(tenant_id) if b.id == branchement_id), None
        )
        if branchement is None:
            raise BranchementIntrouvable(f"Branchement inconnu : {branchement_id}")
        essai = tester_branchement(
            branchement, garder_parametre(branchements, branchement, "jeton", par)
        )
        return EssaiVue(statut=essai.statut, message=essai.message)


def _enregistrer_route_fiche_webhook(app: FastAPI) -> None:
    """AXE-820 : le popup « Relier » donne l'adresse et le secret de ce compte."""

    @app.post("/portefeuille/integrations/{branchement_id}/webhook", response_model=FicheWebhookVue)
    def preparer_fiche_webhook(
        branchement_id: str,
        request: Request,
        identite: IdentiteDep,
        role: RoleMembreDep,
        branchements: BranchementsDep,
    ) -> FicheWebhookVue:
        tenant_id, _par = _admin_du_portefeuille(identite, role)
        branchement = next(
            (b for b in branchements.lister(tenant_id) if b.id == branchement_id), None
        )
        if branchement is None or branchement.type != "rollee":
            raise BranchementIntrouvable(f"Branchement Rollee inconnu : {branchement_id}")
        fiche = preparer_webhook(branchements, branchement, str(request.base_url))
        return FicheWebhookVue(
            url=fiche.url,
            secret=fiche.secret,
            methode=fiche.methode,
            evenements=list(fiche.evenements),
            joignable=fiche.joignable,
        )


def _enregistrer_routes_branchements_dossier(app: FastAPI) -> None:
    """AXE-872 : le branchement qu'un dossier utilise, type par type."""

    @app.get("/dossiers/{dossier_id}/integrations", response_model=ChoixDossierVue)
    def lire_choix_dossier(
        dossier: DossierPortefeuilleDep, branchements: BranchementsDep
    ) -> ChoixDossierVue:
        return ChoixDossierVue(choix=branchements.choix_du_dossier(dossier.tenant_id, dossier.id))

    @app.put("/dossiers/{dossier_id}/integrations/{type_}", response_model=ChoixDossierVue)
    def choisir_pour_le_dossier(
        type_: str,
        entree: ChoixDossierEntree,
        dossier: DossierPortefeuilleDep,
        identite: IdentiteDep,
        role: RoleMembreDep,
        branchements: BranchementsDep,
    ) -> ChoixDossierVue:
        tenant_id, _par = _admin_du_portefeuille(identite, role)
        verifier_choix(branchements.lister(tenant_id), type_, entree.branchement_id)
        branchements.choisir_pour_dossier(tenant_id, dossier.id, type_, entree.branchement_id)
        return ChoixDossierVue(choix=branchements.choix_du_dossier(tenant_id, dossier.id))


def get_services_rollee() -> ServicesRollee:
    """AXE-819 : branchement Rollee du dossier et comptes reliés."""
    return ServicesRollee(PostgresBranchements(_engine()), PostgresComptesRollee(_engine()))


ServicesRolleeDep = Annotated[ServicesRollee, Depends(get_services_rollee)]


class PlateformeVue(BaseModel):
    nom: str
    etat: str  # connecte | en_cours | a_reconnecter
    relie_le: str | None


class PlateformesVue(BaseModel):
    """Côté chauffeur : ses comptes reliés, et ce que le gestionnaire attend."""

    comptes: list[PlateformeVue]
    manquantes: list[str]
    erreur: str | None = None


class SessionRolleeVue(BaseModel):
    lien: str
    expire_le: str | None


class SyntheseRolleeVue(BaseModel):
    """Côté gestionnaire (doc 19) : des nombres, jamais un montant."""

    reliees: int
    attendues: int
    a_reconnecter: int
    manquantes: list[str]
    versements_a_verifier: int = 0  # AXE-891 : un nombre, sans montant


def _vue_plateformes(
    comptes: list[CompteRelie], dossier: Dossier, erreur: str | None
) -> PlateformesVue:
    resume = synthese(comptes, dossier.plateformes, charger_plateformes())
    return PlateformesVue(
        comptes=[
            PlateformeVue(
                nom=c.nom,
                etat=c.etat,
                relie_le=c.relie_le.isoformat() if c.relie_le else None,
            )
            for c in comptes
        ],
        manquantes=list(resume.manquantes),
        erreur=erreur,
    )


def _enregistrer_routes_plateformes(app: FastAPI) -> None:
    """AXE-819 : le chauffeur relie Uber, Bolt… dans Rollee Connect depuis
    son espace ; le gestionnaire n'en voit qu'une synthèse."""

    @app.get("/dossiers/{dossier_id}/plateformes", response_model=PlateformesVue)
    def lire_plateformes(dossier: DossierDep, services: ServicesRolleeDep) -> PlateformesVue:
        """Relit les comptes chez Rollee. Rollee injoignable : la dernière
        liste connue, avec la raison."""
        try:
            comptes = asyncio.run(relire_comptes(services, dossier))
        except RolleeNonBranche as exc:
            return _vue_plateformes(services.comptes.comptes(dossier.id), dossier, str(exc))
        except Exception as exc:  # noqa: BLE001 — Rollee en panne n'empêche pas l'écran
            message = f"Rollee ne répond pas pour le moment ({type(exc).__name__})."
            return _vue_plateformes(services.comptes.comptes(dossier.id), dossier, message)
        return _vue_plateformes(comptes, dossier, None)

    @app.post("/dossiers/{dossier_id}/plateformes/session", response_model=SessionRolleeVue)
    def ouvrir_session_rollee(dossier: DossierDep, services: ServicesRolleeDep) -> SessionRolleeVue:
        """Un lien Rollee Connect de 30 minutes. Le user Rollee est créé à la
        première demande, avec le seul identifiant du dossier."""
        session = asyncio.run(ouvrir_session(services, dossier))
        return SessionRolleeVue(lien=session.lien, expire_le=session.expire_le)

    @app.get("/dossiers/{dossier_id}/plateformes/synthese", response_model=SyntheseRolleeVue)
    def synthese_plateformes(
        dossier: DossierPortefeuilleDep, services: ServicesRolleeDep, settlements: SettlementsDep
    ) -> SyntheseRolleeVue:
        """Ce qui est connu en base, sans appeler Rollee."""
        resume = synthese(
            services.comptes.comptes(dossier.id), dossier.plateformes, charger_plateformes()
        )
        return SyntheseRolleeVue(
            reliees=resume.reliees,
            attendues=resume.attendues,
            a_reconnecter=resume.a_reconnecter,
            manquantes=list(resume.manquantes),
            versements_a_verifier=len(a_verifier(settlements.lister(dossier.id))),
        )


def get_reception_rollee() -> DepotReception:
    """AXE-820 : la route publique du webhook, sans identité."""
    return ReceptionPostgres(_engine())


ReceptionRolleeDep = Annotated[DepotReception, Depends(get_reception_rollee)]
_STATUT_RECEPTION = {"inconnu": 404, "refuse": 401, "illisible": 400}


def _enregistrer_route_webhook_rollee(app: FastAPI) -> None:
    @app.post("/webhooks/rollee/{branchement_id}", status_code=200)
    async def webhook_rollee(
        branchement_id: str, request: Request, depot: ReceptionRolleeDep
    ) -> dict[str, str]:
        """Public : la signature `X-Signature` (HMAC SHA-512, secret du
        branchement) fait foi. Répond tout de suite ; la file traite."""
        corps = await request.body()
        signature = request.headers.get("X-Signature")
        issue = await run_in_threadpool(
            recevoir, depot, branchement_id, corps, signature, datetime.now(UTC)
        )
        if issue in _STATUT_RECEPTION:
            raise HTTPException(status_code=_STATUT_RECEPTION[issue], detail=issue)
        return {"statut": issue}


def get_settlements() -> SettlementsRepository:
    """AXE-821 : relevés de revenus des plateformes et leur rapprochement."""
    return PostgresSettlements(_engine())


SettlementsDep = Annotated[SettlementsRepository, Depends(get_settlements)]


class VersementPlateformeVue(BaseModel):
    """Côté chauffeur seulement (doc 19 : le gestionnaire ne voit pas de montant)."""

    plateforme: str
    du: str
    au: str
    brut_cts: int
    commission_cts: int
    verse_cts: int
    etat: str  # en_attente_banque | reconcilie | a_classer | a_verifier
    motif: str | None


def _enregistrer_route_versements(app: FastAPI) -> None:
    @app.get(
        "/dossiers/{dossier_id}/versements-plateformes",
        response_model=list[VersementPlateformeVue],
    )
    def lire_versements(
        dossier: DossierDep, settlements: SettlementsDep
    ) -> list[VersementPlateformeVue]:
        """Les 20 dernières périodes : brut, commission, versé, et où en est
        le rapprochement avec la banque."""
        return [_vue_versement(s) for s in reversed(settlements.lister(dossier.id)[-20:])]

    @app.get(
        "/dossiers/{dossier_id}/versements-plateformes/a-verifier",
        response_model=list[VersementPlateformeVue],
    )
    def lire_versements_a_verifier(
        dossier: DossierDep, settlements: SettlementsDep
    ) -> list[VersementPlateformeVue]:
        """AXE-891 : tous les relevés « à vérifier », même anciens, pour
        « À traiter ». Ils y restent tant qu'ils sont dans cet état."""
        return [_vue_versement(s) for s in reversed(a_verifier(settlements.lister(dossier.id)))]


def _vue_versement(s: SettlementStocke) -> VersementPlateformeVue:
    return VersementPlateformeVue(
        plateforme=s.settlement.platform,
        du=s.settlement.period_start.isoformat(),
        au=s.settlement.period_end.isoformat(),
        brut_cts=s.settlement.gross_earnings_cts,
        commission_cts=s.settlement.commission_cts,
        verse_cts=s.settlement.net_payout_cts,
        etat=s.etat,
        motif=s.motif,
    )


def get_liens_rollee() -> LiensRollee:
    """AXE-911 : liens dossier ↔ user Rollee, leur historique, la file à choisir."""
    return PostgresLiensRollee(_engine())


LiensRolleeDep = Annotated[LiensRollee, Depends(get_liens_rollee)]
ACTE_LIEN_ROLLEE = "lien_rollee"


def get_annuaire_rollee() -> AnnuaireRollee:
    """AXE-919 : les users Rollee du portefeuille, cherchés par leur nom."""
    return PostgresAnnuaireRollee(_engine())


AnnuaireRolleeDep = Annotated[AnnuaireRollee, Depends(get_annuaire_rollee)]


class CandidatRolleeVue(BaseModel):
    dossier_id: str
    nom: str
    raisons: list[str]


class AChoisirRolleeVue(BaseModel):
    """Nom en clair depuis AXE-919 (décision du 14/11), plateformes, fin
    d'IBAN. Jamais un montant."""

    rollee_user_id: str
    etat: str  # a_choisir | non_trouve
    nom: str
    initiales: str
    plateformes: list[str]
    iban_fin: str | None
    candidats: list[CandidatRolleeVue]


class RolleePortefeuilleVue(BaseModel):
    # relie_auto | relie_gestionnaire | relie_chauffeur | a_choisir | non_relie
    etats: dict[str, str]
    a_choisir: list[AChoisirRolleeVue]


class LienRolleeVue(BaseModel):
    origine: str
    comment: str
    relie_le: str


class LienRetireVue(BaseModel):
    comment: str
    relie_le: str
    retire_le: str
    retire_par: str
    motif: str


class FicheRolleeVue(BaseModel):
    lien: LienRolleeVue | None
    historique: list[LienRetireVue]
    versements_a_contrepasser: int  # ce que « délier » changerait, en nombre


class ChoixRolleeEntree(BaseModel):
    rollee_user_id: str
    dossier_id: str | None  # None : « aucun de ces comptes »


class FicheAnnuaireVue(BaseModel):
    """AXE-919 : un user Rollee cherché par son nom. Jamais un montant."""

    rollee_user_id: str
    nom: str
    plateformes: list[str]
    compte: str  # le compte Rollee du portefeuille (« Serenity Mobilité »)
    email_masque: str | None
    relie_a: str | None  # nom de l'entreprise déjà reliée, s'il y en a une


class LierRolleeEntree(BaseModel):
    rollee_user_id: str


class DelierRolleeEntree(BaseModel):
    motif: str


class DelierRolleeVue(BaseModel):
    versements_contrepasses: int


_ETAT_PAR_ORIGINE = {
    "auto": "relie_auto",
    "manuel": "relie_gestionnaire",
    "cree": "relie_chauffeur",
}


def _vue_lien(lien: Lien) -> LienRolleeVue:
    return LienRolleeVue(
        origine=lien.origine, comment=lien.comment, relie_le=lien.relie_le.isoformat()
    )


def _rollee_du_portefeuille(
    tenant_id: TenantId, dossiers: DossierRepository, liens: LiensRollee
) -> RolleePortefeuilleVue:
    du_tenant = dossiers.lister_par_tenant(tenant_id)
    noms = {str(d.id): d.nom for d in du_tenant}
    etats = {str(d.id): "non_relie" for d in du_tenant}
    attente = [a for a in liens.a_choisir(tenant_id) if a.etat != "ecarte"]
    for a in attente:
        for c in a.candidats:
            if c.dossier_id in etats:
                etats[c.dossier_id] = "a_choisir"
    for lien in liens.liens(tenant_id):
        etats[str(lien.dossier_id)] = _ETAT_PAR_ORIGINE[lien.origine]
    return RolleePortefeuilleVue(
        etats=etats,
        a_choisir=[
            AChoisirRolleeVue(
                rollee_user_id=a.rollee_user_id,
                etat=a.etat,
                nom=a.apercu.nom,
                initiales=a.apercu.initiales,
                plateformes=list(a.apercu.plateformes),
                iban_fin=a.apercu.iban_fin,
                candidats=[
                    CandidatRolleeVue(
                        dossier_id=c.dossier_id, nom=noms[c.dossier_id], raisons=list(c.raisons)
                    )
                    for c in a.candidats
                    if c.dossier_id in noms
                ],
            )
            for a in attente
        ],
    )


def _choisir_rollee(
    entree: ChoixRolleeEntree,
    tenant_id: TenantId,
    identite: IdentiteAuthentifiee,
    dossiers: DossierRepository,
    liens: LiensRollee,
    journal: JournalAcces,
) -> None:
    attente = next(
        (a for a in liens.a_choisir(tenant_id) if a.rollee_user_id == entree.rollee_user_id), None
    )
    if attente is None:
        raise HTTPException(status_code=404, detail="Ce compte Rollee n'attend pas de choix.")
    maintenant = datetime.now(UTC)
    if entree.dossier_id is None:
        liens.ecarter(attente.rollee_user_id, maintenant)
        return
    dossier = dossiers.obtenir(DossierId(entree.dossier_id))
    if dossier is None or dossier.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Dossier introuvable.")
    try:
        liens.lier(lien_manuel(dossier.id, attente, identite.email, maintenant))
    except LienDejaPris as exc:
        raise HTTPException(
            status_code=409,
            detail="Cette entreprise ou ce compte Rollee est déjà relié : retirez d'abord le lien.",
        ) from exc
    liens.retirer_a_choisir(attente.rollee_user_id)
    journal.noter(
        dossier.id,
        ACTE_LIEN_ROLLEE,
        f"choisi:{attente.rollee_user_id}",
        identite.user_id,
        maintenant,
    )


def _delier_rollee(
    dossier: Dossier,
    motif: str,
    identite: IdentiteAuthentifiee,
    depots: tuple[LiensRollee, ServicesRollee, SettlementsRepository, LedgerService],
    journal: JournalAcces,
) -> int:
    """Retire le lien, garde l'historique, contre-passe les ventilations de
    l'ancien user. Les comptes de l'ancien user ne sont plus relus."""
    liens, services, settlements, ledger = depots
    maintenant = datetime.now(UTC)
    comptes = frozenset(c.account_id for c in services.comptes.comptes(dossier.id))
    lien = liens.delier(dossier.id, identite.email, motif, maintenant)
    if lien is None:
        raise HTTPException(status_code=404, detail="Cette entreprise n'a pas de lien Rollee.")
    services.comptes.remplacer_comptes(dossier.id, [])
    inverses, delies = delier_revenus(
        settlements.lister(dossier.id),
        comptes,
        ledger.grand_livre(dossier.id),
        ledger.periodes_closes(dossier.id),
        dossier.exercice_debut,
        maintenant,
    )
    for inverse in inverses:
        ledger.enregistrer(inverse)
    settlements.enregistrer(delies)
    journal.noter(
        dossier.id, ACTE_LIEN_ROLLEE, f"retire:{lien.rollee_user_id}", identite.user_id, maintenant
    )
    return len(inverses)


def _fiche_rollee(
    dossier: Dossier, liens: LiensRollee, settlements: SettlementsRepository
) -> FicheRolleeVue:
    lien = liens.lien(dossier.id)
    return FicheRolleeVue(
        lien=_vue_lien(lien) if lien else None,
        historique=[
            LienRetireVue(
                comment=r.lien.comment,
                relie_le=r.lien.relie_le.isoformat(),
                retire_le=r.retire_le.isoformat(),
                retire_par=r.retire_par,
                motif=r.motif,
            )
            for r in liens.historique(dossier.id)
        ],
        versements_a_contrepasser=sum(
            1 for s in settlements.lister(dossier.id) if s.etat == "reconcilie"
        ),
    )


def _enregistrer_routes_rapprochement_rollee(app: FastAPI) -> None:
    """AXE-918 : le bouton « Rapprocher Rollee » et son suivi."""

    @app.post("/portefeuille/rollee/rapprocher", response_model=SynchronisationVue)
    def rapprocher_rollee(
        demandes: DemandesJobsDep, role: RoleMembreDep, identite: IdentiteDep
    ) -> SynchronisationVue | None:
        """AXE-918 : relie les users Rollee sans attendre la nuit. Le worker lit
        tous les comptes Rollee, pose les liens sûrs et remplit la file. Un
        passage en attente ou en cours est rendu sans en lancer un second."""
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture seule ne lance pas de rapprochement.")
        return _synchronisation_vue(demandes.demander(tenant_id, TYPE_RAPPROCHEMENT_ROLLEE))

    @app.get("/portefeuille/rollee/rapprochement", response_model=SynchronisationVue | None)
    def lire_rapprochement_rollee(
        demandes: DemandesJobsDep, identite: IdentiteDep
    ) -> SynchronisationVue | None:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _synchronisation_vue(demandes.dernier(tenant_id, TYPE_RAPPROCHEMENT_ROLLEE))


def _annuaire_rollee(
    tenant_id: TenantId,
    requete: str,
    annuaire: AnnuaireRollee,
    liens: LiensRollee,
    dossiers: DossierRepository,
    branchements: BranchementsRepository,
) -> list[FicheAnnuaireVue]:
    noms_dossiers = {str(d.id): d.nom for d in dossiers.lister_par_tenant(tenant_id)}
    relies = {
        x.rollee_user_id: noms_dossiers.get(str(x.dossier_id)) for x in liens.liens(tenant_id)
    }
    comptes = {b.id: b.nom for b in branchements.lister(tenant_id)}
    return [
        FicheAnnuaireVue(
            rollee_user_id=f.rollee_user_id,
            nom=f.nom,
            plateformes=list(f.plateformes),
            compte=comptes.get(f.branchement_id, "Rollee"),
            email_masque=f.email_masque,
            relie_a=relies.get(f.rollee_user_id),
        )
        for f in chercher(annuaire.fiches(tenant_id), requete)
    ]


def _lier_depuis_annuaire(
    dossier: Dossier,
    rollee_user_id: str,
    identite: IdentiteAuthentifiee,
    depots: tuple[AnnuaireRollee, LiensRollee],
    journal: JournalAcces,
) -> None:
    annuaire, liens = depots
    fiche = annuaire.fiche(dossier.tenant_id, rollee_user_id)
    if fiche is None:
        raise HTTPException(
            status_code=404,
            detail="Ce compte Rollee n'est pas dans l'annuaire : lancez « Rapprocher Rollee ».",
        )
    maintenant = datetime.now(UTC)
    lien = Lien(
        dossier.id,
        fiche.rollee_user_id,
        fiche.branchement_id,
        "manuel",
        maintenant,
        None,
        identite.email,
    )
    try:
        liens.lier(lien)
    except LienDejaPris as exc:
        raise HTTPException(
            status_code=409,
            detail="Cette entreprise ou ce compte Rollee est déjà relié : retirez d'abord le lien.",
        ) from exc
    liens.retirer_a_choisir(fiche.rollee_user_id)
    journal.noter(
        dossier.id, ACTE_LIEN_ROLLEE, f"choisi:{fiche.rollee_user_id}", identite.user_id, maintenant
    )


def _enregistrer_routes_annuaire_rollee(app: FastAPI) -> None:
    """AXE-919 : chercher un user Rollee par son nom et le relier à l'entreprise."""

    @app.get("/portefeuille/rollee/annuaire", response_model=list[FicheAnnuaireVue])
    def chercher_rollee(
        q: str,
        identite: IdentiteDep,
        annuaire: AnnuaireRolleeDep,
        liens: LiensRolleeDep,
        dossiers: DossiersDep,
        branchements: BranchementsDep,
    ) -> list[FicheAnnuaireVue]:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _annuaire_rollee(tenant_id, q, annuaire, liens, dossiers, branchements)

    @app.post("/dossiers/{dossier_id}/rollee/lier", status_code=204)
    def lier_rollee(
        entree: LierRolleeEntree,
        dossier: DossierPortefeuilleDep,
        identite: IdentiteDep,
        role: RoleMembreDep,
        annuaire: AnnuaireRolleeDep,
        liens: LiensRolleeDep,
        journal: JournalAccesDep,
    ) -> None:
        _tenant_id, identite_ok = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture seule ne relie pas de compte Rollee.")
        _lier_depuis_annuaire(
            dossier, entree.rollee_user_id, identite_ok, (annuaire, liens), journal
        )


def _enregistrer_routes_liens_rollee(app: FastAPI) -> None:
    """AXE-911 : le gestionnaire choisit, voit et corrige le lien Rollee."""

    @app.get("/portefeuille/rollee", response_model=RolleePortefeuilleVue)
    def lire_rollee_portefeuille(
        identite: IdentiteDep, dossiers: DossiersDep, liens: LiensRolleeDep
    ) -> RolleePortefeuilleVue:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _rollee_du_portefeuille(tenant_id, dossiers, liens)

    @app.post("/portefeuille/rollee/choix", status_code=204)
    def choisir_rollee(
        entree: ChoixRolleeEntree,
        identite: IdentiteDep,
        role: RoleMembreDep,
        dossiers: DossiersDep,
        liens: LiensRolleeDep,
        journal: JournalAccesDep,
    ) -> None:
        tenant_id, identite_ok = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture seule ne relie pas de compte Rollee.")
        _choisir_rollee(entree, tenant_id, identite_ok, dossiers, liens, journal)

    @app.get("/dossiers/{dossier_id}/rollee", response_model=FicheRolleeVue)
    def lire_lien_rollee(
        dossier: DossierPortefeuilleDep, liens: LiensRolleeDep, settlements: SettlementsDep
    ) -> FicheRolleeVue:
        return _fiche_rollee(dossier, liens, settlements)

    @app.post("/dossiers/{dossier_id}/rollee/delier", response_model=DelierRolleeVue)
    def delier_rollee(
        entree: DelierRolleeEntree,
        dossier: DossierPortefeuilleDep,
        identite: IdentiteDep,
        role: RoleMembreDep,
        depots: Annotated[
            tuple[LiensRollee, ServicesRollee, SettlementsRepository, LedgerService],
            Depends(_depots_delier),
        ],
        journal: JournalAccesDep,
    ) -> DelierRolleeVue:
        _tenant_id, identite_ok = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture seule ne retire pas de lien.")
        motif = entree.motif.strip()
        if not motif:
            raise HTTPException(status_code=400, detail="Dites pourquoi le lien est retiré.")
        contrepasses = _delier_rollee(dossier, motif[:200], identite_ok, depots, journal)
        return DelierRolleeVue(versements_contrepasses=contrepasses)


def _depots_delier(
    liens: LiensRolleeDep,
    services: ServicesRolleeDep,
    settlements: SettlementsDep,
    ledger: LedgerBaseDep,
) -> tuple[LiensRollee, ServicesRollee, SettlementsRepository, LedgerService]:
    return liens, services, settlements, ledger


def _enregistrer_routes_integrations(app: FastAPI) -> None:
    """Branchements, envois et plateformes Rollee (AXE-872, AXE-808, AXE-819)."""
    _enregistrer_routes_branchements(app)
    _enregistrer_route_tester_branchement(app)
    _enregistrer_route_fiche_webhook(app)
    _enregistrer_routes_branchements_dossier(app)
    _enregistrer_routes_envoi(app)
    _enregistrer_routes_plateformes(app)
    _enregistrer_route_webhook_rollee(app)
    _enregistrer_route_versements(app)
    _enregistrer_routes_liens_rollee(app)
    _enregistrer_routes_annuaire_rollee(app)
    _enregistrer_routes_rapprochement_rollee(app)


def _enregistrer_routes_envoi(app: FastAPI) -> None:
    """AXE-808 : suivre les envois, se désinscrire. Les canaux branchés se
    lisent ici pour les écrans qui n'ont besoin que de savoir « branché »."""

    @app.get("/portefeuille/integrations/envoi", response_model=IntegrationsEnvoiVue)
    def lire_integrations_envoi(
        identite: IdentiteDep, branchements: BranchementsDep
    ) -> IntegrationsEnvoiVue:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        branches = types_branches(branchements.lister(tenant_id))
        return IntegrationsEnvoiVue(
            canaux={t: le.isoformat() for t, le in branches.items() if t in ("mail", "sms")}
        )

    @app.get("/dossiers/{dossier_id}/envois", response_model=list[EnvoiVue])
    def lire_envois(
        dossier: DossierPortefeuilleDep, envois: EnvoisDep, branchements: BranchementsDep
    ) -> list[EnvoiVue]:
        """Suivi des rappels envoyés à cette entreprise : un statut, pas un contenu."""
        noms = {b.id: b.nom for b in branchements.lister(dossier.tenant_id)}
        return [
            EnvoiVue(
                canal=e.canal,
                statut=e.statut,
                tentatives=e.tentatives,
                raison=e.raison,
                le=e.maj_le.isoformat() if e.maj_le else None,
                branchement=noms.get(e.branchement_id or ""),
            )
            for e in envois.du_dossier(dossier.id, 50)
        ]

    @app.get("/desinscription", response_model=DesinscriptionVue)
    def se_desinscrire(d: str, c: str, j: str, envois: EnvoisDep) -> DesinscriptionVue:
        """Lien public, en bas de chaque rappel : sa signature suffit."""
        if c not in ("mail", "sms") or not desinscription_valide(d, c, j):
            raise HTTPException(status_code=404, detail="Ce lien n'est pas valable.")
        envois.desinscrire(DossierId(d), c)
        canal = "par e-mail" if c == "mail" else "par SMS"
        return DesinscriptionVue(message=f"Vous ne recevrez plus de rappels {canal}.")


class NouveauChauffeurVue(BaseModel):
    contact_nr: str
    nom: str
    siren: str | None
    forme: str | None
    exercice_debut: str | None
    code_naf: str | None
    avertissements: list[str]
    cessee: bool
    decision: str | None  # None : à valider ; "ajouter" : création en attente


class DecisionContactsEntree(BaseModel):
    contact_nrs: list[str]
    decision: Literal["ajouter", "ignorer", "reprendre"]


class SynchronisationVue(BaseModel):
    statut: str  # en_attente | en_cours | fait | echec
    resultat: str | None
    erreur: str | None
    demandee_le: str | None
    terminee_le: str | None


def _synchronisation_vue(job: Job | None) -> SynchronisationVue | None:
    if job is None:
        return None
    return SynchronisationVue(
        statut=job.statut,
        resultat=job.resultat,
        erreur=job.derniere_erreur if job.statut == "echec" else None,
        demandee_le=job.cree_le.isoformat() if job.cree_le else None,
        terminee_le=job.termine_le.isoformat() if job.termine_le else None,
    )


class LigneImportVue(BaseModel):
    numero: int
    dossier_id: str | None
    nom: str | None
    erreurs: list[str]
    avertissements: list[str]


class RapportImportVue(BaseModel):
    """AXE-809 : ligne par ligne, avant toute création."""

    lignes: list[LigneImportVue]
    a_creer: int
    en_erreur: int
    creation: SynchronisationVue | None = None


def _rapport_import(
    tenant_id: TenantId,
    contenu: bytes,
    dossiers: DossierRepository,
    sirene: bool,
) -> tuple[RapportImportVue, list[dict[str, str]]]:
    lignes = lire_csv(contenu)
    existants = [d.id for d in dossiers.lister_par_tenant(tenant_id)]
    resultat = rapport_import(tenant_id, lignes, existants, fiche_sirene if sirene else None)
    vue = RapportImportVue(
        lignes=[
            LigneImportVue(
                numero=ligne.numero,
                dossier_id=ligne.dossier.id if ligne.dossier else None,
                nom=ligne.dossier.nom if ligne.dossier else None,
                erreurs=list(ligne.erreurs),
                avertissements=list(ligne.avertissements),
            )
            for ligne in resultat.lignes
        ],
        a_creer=len(resultat.valides),
        en_erreur=resultat.en_erreur,
    )
    return vue, lignes


def _enregistrer_routes_import_dossiers(app: FastAPI) -> None:
    """AXE-809 : créer les dossiers d'un portefeuille depuis un fichier CSV."""

    @app.get("/portefeuille/import-dossiers/modele.csv")
    def modele_import(identite: IdentiteDep) -> Response:
        _verifier_acces_gestionnaire(identite)
        return _fichier(MODELE_CSV, "text/csv; charset=utf-8", "modele-dossiers.csv")

    @app.post("/portefeuille/import-dossiers/rapport", response_model=RapportImportVue)
    async def rapport_import_dossiers(
        fichier: UploadFile, identite: IdentiteDep, dossiers: DossiersDep, sirene: bool = False
    ) -> RapportImportVue:
        """Rien n'est écrit. `sirene` interroge Sirene ligne par ligne (plus lent)."""
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _rapport_import(tenant_id, await fichier.read(), dossiers, sirene)[0]

    @app.post("/portefeuille/import-dossiers", response_model=RapportImportVue)
    async def importer_dossiers(
        fichier: UploadFile,
        identite: IdentiteDep,
        role: RoleMembreDep,
        dossiers: DossiersDep,
        demandes: DemandesJobsDep,
    ) -> RapportImportVue:
        """Admin. Les lignes valides sont créées par le worker, en un lot ;
        les lignes en erreur ne le sont pas."""
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        if role != "admin":
            raise HTTPException(status_code=403, detail="Réservé à un administrateur.")
        en_cours = demandes.dernier(str(tenant_id), TYPE_IMPORT_DOSSIERS)
        if en_cours is not None and en_cours.actif:
            raise HTTPException(status_code=409, detail="Un import est déjà en cours.")
        vue, lignes = _rapport_import(tenant_id, await fichier.read(), dossiers, False)
        if vue.a_creer == 0:
            return vue
        job = demandes.demander(
            str(tenant_id), TYPE_IMPORT_DOSSIERS, json.dumps({"lignes": lignes})
        )
        return vue.model_copy(update={"creation": _synchronisation_vue(job)})

    @app.get("/portefeuille/import-dossiers", response_model=SynchronisationVue | None)
    def suivre_import(
        demandes: DemandesJobsDep, identite: IdentiteDep
    ) -> SynchronisationVue | None:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _synchronisation_vue(demandes.dernier(str(tenant_id), TYPE_IMPORT_DOSSIERS))


def _nouveaux_chauffeurs(
    tenant_id: TenantId, contacts: ContactsProposesRepository
) -> list[NouveauChauffeurVue]:
    decisions = contacts.decisions(tenant_id)
    return [
        NouveauChauffeurVue(
            contact_nr=p.contact_nr,
            nom=p.nom,
            siren=p.siren,
            forme=p.forme,
            exercice_debut=p.exercice_debut.isoformat() if p.exercice_debut else None,
            code_naf=p.code_naf,
            avertissements=list(p.avertissements),
            cessee=p.cessee,
            decision=None
            if decisions.get(p.contact_nr) == "reprendre"
            else decisions.get(p.contact_nr),
        )
        for p in contacts.propositions(tenant_id)
    ]


def _enregistrer_routes_synchronisation(app: FastAPI) -> None:
    @app.get("/portefeuille/nouveaux-chauffeurs", response_model=list[NouveauChauffeurVue])
    def lister_nouveaux_chauffeurs(
        contacts: ContactsProposesDep, identite: IdentiteDep
    ) -> list[NouveauChauffeurVue]:
        """Contacts Digifactory sans dossier, préparés depuis Sirene (AXE-845)."""
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _nouveaux_chauffeurs(tenant_id, contacts)

    @app.post("/portefeuille/nouveaux-chauffeurs", response_model=list[NouveauChauffeurVue])
    def decider_nouveaux_chauffeurs(
        corps: DecisionContactsEntree,
        contacts: ContactsProposesDep,
        demandes: DemandesJobsDep,
        role: RoleMembreDep,
        identite: IdentiteDep,
    ) -> list[NouveauChauffeurVue]:
        """« Ajouter » : le dossier est créé par la synchro qui suit (demandée
        ici). « Ignorer » le retire de la liste ; « reprendre » l'y remet."""
        tenant_id, identite_ok = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture n'ajoute pas de chauffeur.")
        proposes = {p.contact_nr for p in contacts.propositions(tenant_id)}
        inconnus = set(corps.contact_nrs) - proposes
        if inconnus:
            raise HTTPException(status_code=404, detail="Contact inconnu.")
        maintenant = datetime.now(UTC)
        for numero in corps.contact_nrs:
            contacts.decider(
                tenant_id,
                numero,
                corps.decision,
                identite_ok.email or identite_ok.user_id,
                maintenant,
            )
        if corps.decision == "ajouter":
            demandes.demander(tenant_id, TYPE_SYNCHRO)
        return _nouveaux_chauffeurs(tenant_id, contacts)

    @app.post("/portefeuille/synchroniser", response_model=SynchronisationVue)
    def synchroniser(
        demandes: DemandesJobsDep, role: RoleMembreDep, identite: IdentiteDep
    ) -> SynchronisationVue | None:
        """Lance la synchro tout de suite. Pendant qu'une synchro est en
        attente ou en cours, rend celle-ci sans en lancer une seconde."""
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        _exiger_ecriture(role, "La lecture ne lance pas de synchronisation.")
        return _synchronisation_vue(demandes.demander(tenant_id, TYPE_SYNCHRO))

    @app.get("/portefeuille/synchronisation", response_model=SynchronisationVue | None)
    def lire_synchronisation(
        demandes: DemandesJobsDep, identite: IdentiteDep
    ) -> SynchronisationVue | None:
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        return _synchronisation_vue(demandes.dernier(tenant_id, TYPE_SYNCHRO))


class MoiVue(BaseModel):
    """AXE-812 : ce que l'écran doit savoir de la session gestionnaire."""

    email: str
    role: str
    mfa_requise: bool  # le rôle l'exige et la session n'a pas encore de code
    aal: str


class ReinitialisationMfaVue(BaseModel):
    facteurs_retires: int


class ActeAccesVue(BaseModel):
    type: str  # "export" | "consultation" | "connexion"
    reference: str
    par_vous: bool
    le: str


def _adresse_et_agent(request: Request) -> str:
    """IP et navigateur de la connexion, bornés : une trace, pas un relevé."""
    ip = request.client.host if request.client else "?"
    agent = (request.headers.get("user-agent") or "?")[:160]
    return f"{ip} · {agent}"


def _enregistrer_routes_securite(app: FastAPI) -> None:
    """AXE-812 : double authentification et traces d'accès."""

    @app.get("/portefeuille/moi", response_model=MoiVue)
    def moi(identite: IdentiteDep, role: RoleAppelantDep) -> MoiVue:
        """Accessible sans code : l'écran y apprend qu'il doit s'enrôler."""
        _tenant_id, identite = _verifier_acces_gestionnaire(identite)
        return MoiVue(
            email=identite.email,
            role=role or "admin",
            mfa_requise=mfa_requise(role, identite),
            aal=identite.aal,
        )

    @app.post("/session/connexion", status_code=204)
    def tracer_connexion(
        request: Request,
        identite: IdentiteDep,
        portefeuille: JournalPortefeuilleDep,
        journal_acces: JournalAccesDep,
    ) -> None:
        """Appelé par l'écran juste après une connexion réussie. Une
        connexion échouée n'arrive jamais ici : elle se lit dans les journaux
        de Supabase Auth."""
        if identite is None:
            raise HTTPException(status_code=401, detail="Authentification requise.")
        maintenant, trace = datetime.now(UTC), _adresse_et_agent(request)
        if identite.tenant_id is not None:
            portefeuille.noter(
                identite.tenant_id, ACTE_CONNEXION_MEMBRE, trace, identite.user_id, maintenant
            )
        if identite.dossier_id is not None:
            journal_acces.noter(
                identite.dossier_id, ACTE_CONNEXION, trace, identite.user_id, maintenant
            )


def _enregistrer_routes_mfa_et_acces(app: FastAPI) -> None:
    """AXE-812 : réinitialiser la double authentification d'un membre ;
    relire les accès à un dossier."""

    @app.post(
        "/portefeuille/membres/{email}/mfa/reinitialiser", response_model=ReinitialisationMfaVue
    )
    def reinitialiser_mfa(
        email: str,
        identite: IdentiteDep,
        role: RoleMembreDep,
        comptes: ComptesDep,
        portefeuille: JournalPortefeuilleDep,
    ) -> ReinitialisationMfaVue:
        """Par un autre admin seulement, tracé. Le membre enrôlera un nouveau
        facteur à sa prochaine connexion (pas de codes de secours natifs)."""
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        if role != "admin":
            raise HTTPException(status_code=403, detail="Réservé à un administrateur.")
        if email.strip().lower() == identite.email.lower():
            raise HTTPException(
                status_code=409, detail="Un autre administrateur doit réinitialiser la vôtre."
            )
        retires = comptes.reinitialiser_mfa(str(tenant_id), email.strip())
        portefeuille.noter(
            tenant_id,
            ACTE_MFA_REINITIALISEE,
            email.strip().lower(),
            identite.user_id,
            datetime.now(UTC),
        )
        return ReinitialisationMfaVue(facteurs_retires=retires)

    @app.get("/dossiers/{dossier_id}/acces", response_model=list[ActeAccesVue])
    def lire_acces(
        dossier: DossierDep, identite: IdentiteDep, journal_acces: JournalAccesDep
    ) -> list[ActeAccesVue]:
        """Le dirigeant voit qui a consulté ou exporté son dossier."""
        moi = identite.user_id if identite else None
        return [
            ActeAccesVue(
                type=acte.type_acte,
                reference=acte.reference,
                par_vous=acte.acteur == moi,
                le=acte.le.isoformat(),
            )
            for acte in journal_acces.lister(dossier.id, ACTES_VISIBLES_DU_DIRIGEANT)
        ]


class HabilitationEntree(BaseModel):
    email: str
    nom: str
    cabinet: str
    numero_ordre: str
    lettre_mission: str
    date_lettre: date
    dossiers: list[str]


class HabilitationVue(BaseModel):
    email: str
    nom: str
    cabinet: str
    numero_ordre: str
    lettre_mission: str
    date_lettre: str
    dossiers: list[str]


class EngagementVue(BaseModel):
    """Ce que l'écran de l'expert affiche avant de lui ouvrir le mode expert."""

    version: str
    texte: str
    accepte: bool
    habilitation: HabilitationVue | None


class AcceptationEntree(BaseModel):
    version: str
    texte: str


def _habilitation_vue(h: Habilitation) -> HabilitationVue:
    return HabilitationVue(
        email=h.email,
        nom=h.nom,
        cabinet=h.cabinet,
        numero_ordre=h.numero_ordre,
        lettre_mission=h.lettre_mission,
        date_lettre=h.date_lettre.isoformat(),
        dossiers=[str(d) for d in h.dossiers],
    )


def _champs_obligatoires(entree: HabilitationEntree) -> None:
    champs = (entree.email, entree.nom, entree.cabinet, entree.numero_ordre, entree.lettre_mission)
    if any(not champ.strip() for champ in champs) or not entree.dossiers:
        raise HTTPException(
            status_code=422,
            detail="Nom, cabinet, numéro d'Ordre, lettre de mission et dossiers sont obligatoires.",
        )


def _enregistrer_routes_expert_comptable(app: FastAPI) -> None:
    """AXE-800 : un admin habilite l'expert ; l'expert accepte l'engagement."""

    @app.post("/portefeuille/experts", response_model=HabilitationVue)
    def habiliter_expert(
        entree: HabilitationEntree,
        identite: IdentiteDep,
        role: RoleMembreDep,
        dossiers: DossiersDep,
        comptes: ComptesDep,
        experts: ExpertsDep,
        ecrire_role: EcrireRoleDep,
    ) -> HabilitationVue:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        if role != "admin":
            raise HTTPException(status_code=403, detail="Réservé à un administrateur.")
        _champs_obligatoires(entree)
        du_portefeuille = {d.id for d in dossiers.lister_par_tenant(tenant_id)}
        couverts = tuple(DossierId(d) for d in dict.fromkeys(entree.dossiers))
        if not set(couverts) <= du_portefeuille:
            raise HTTPException(status_code=404, detail="Un dossier n'est pas du portefeuille.")
        email = entree.email.strip().lower()
        ecrire_role(tenant_id, email, ROLE_EXPERT)
        if all(m.email.lower() != email for m in comptes.membres(str(tenant_id))):
            comptes.inviter_membre(str(tenant_id), email, ROLE_EXPERT)
        habilitation = Habilitation(
            tenant_id=tenant_id,
            email=email,
            nom=entree.nom.strip(),
            cabinet=entree.cabinet.strip(),
            numero_ordre=entree.numero_ordre.strip(),
            lettre_mission=entree.lettre_mission.strip(),
            date_lettre=entree.date_lettre,
            dossiers=couverts,
            accordee_par=identite.user_id,
            accordee_le=datetime.now(UTC),
        )
        experts.habiliter(habilitation)
        return _habilitation_vue(habilitation)


def _enregistrer_routes_engagement(app: FastAPI) -> None:
    """AXE-800 : l'expert lit puis accepte l'engagement de responsabilité."""

    @app.get("/expert/engagement", response_model=EngagementVue)
    def lire_engagement(identite: IdentiteDep, experts: ExpertsDep) -> EngagementVue:
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        habilitation = experts.habilitation(tenant_id, identite.email)
        engagement = experts.engagement(tenant_id, identite.email)
        return EngagementVue(
            version=VERSION_ENGAGEMENT,
            texte=TEXTE_ENGAGEMENT,
            accepte=engagement is not None and engagement.version == VERSION_ENGAGEMENT,
            habilitation=_habilitation_vue(habilitation) if habilitation else None,
        )

    @app.post("/expert/engagement", response_model=EngagementVue)
    def accepter_engagement(
        entree: AcceptationEntree,
        request: Request,
        identite: IdentiteDep,
        role: RoleMembreDep,
        experts: ExpertsDep,
    ) -> EngagementVue:
        """Le texte est gardé mot pour mot, avec la date et l'adresse."""
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        habilitation = experts.habilitation(tenant_id, identite.email)
        if role != ROLE_EXPERT or habilitation is None:
            raise HTTPException(status_code=403, detail="Réservé à l'expert-comptable habilité.")
        verifier_engagement(entree.texte, entree.version)
        adresse = request.client.host if request.client else "?"
        agent = (request.headers.get("user-agent") or "?")[:160]
        experts.accepter(
            Engagement(
                tenant_id=tenant_id,
                email=identite.email,
                version=entree.version,
                texte=entree.texte,
                adresse=f"{adresse} · {agent}",
                acteur=identite.user_id,
                accepte_le=datetime.now(UTC),
            )
        )
        return EngagementVue(
            version=VERSION_ENGAGEMENT,
            texte=TEXTE_ENGAGEMENT,
            accepte=True,
            habilitation=_habilitation_vue(habilitation),
        )


class LigneCa3Vue(BaseModel):
    numero: str
    libelle: str
    centimes: int


class PeriodeTvaVue(BaseModel):
    cle: str
    debut: str
    fin: str
    echeance: str | None
    lignes: list[LigneCa3Vue]
    due_cts: int
    credit_cts: int
    declaree: bool
    a_traiter: int


class TvaVue(BaseModel):
    """AXE-805 : l'écran « Ma TVA » du chauffeur."""

    periodicite: str | None
    jour_echeance: int | None
    periodes: list[PeriodeTvaVue]


class ParametresTvaEntree(BaseModel):
    periodicite: str
    jour_echeance: int


class DeclarationTvaEntree(BaseModel):
    deposee_le: date


def _etats_tva(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    base: LedgerService,
    decisions: DecisionRepository,
    signatures: SignatureRepository,
) -> tuple[EtatPeriode, ...]:
    ecritures = ledger.grand_livre(dossier.id)
    dates = {e.id: e.date for e in ecritures}
    a_traiter = [dates[i] for i in ecritures_a_trancher(base, decisions, dossier.id) if i in dates]
    types = [type_preuve(p) for p in periodes_du_dossier(dossier)]
    declarees = signatures.types_presents([dossier.id], types).get(dossier.id, set())
    return etats_tva(dossier, ecritures, a_traiter, declarees)


def _tva_vue(dossier: Dossier, etats: Sequence[EtatPeriode]) -> TvaVue:
    return TvaVue(
        periodicite=dossier.tva_periodicite,
        jour_echeance=dossier.tva_jour_echeance,
        periodes=[
            PeriodeTvaVue(
                cle=e.ca3.periode.cle,
                debut=e.ca3.periode.debut.isoformat(),
                fin=e.ca3.periode.fin.isoformat(),
                echeance=e.echeance.isoformat() if e.echeance else None,
                lignes=[
                    LigneCa3Vue(numero=ligne.numero, libelle=ligne.libelle, centimes=ligne.centimes)
                    for ligne in e.ca3.lignes
                ],
                due_cts=e.ca3.due,
                credit_cts=e.ca3.credit,
                declaree=e.declaree,
                a_traiter=e.a_traiter,
            )
            for e in etats
        ],
    )


def _declarer_tva(
    dossier: Dossier,
    etat: EtatPeriode,
    ledger: InMemoryLedgerService,
    base: LedgerService,
    signatures: SignatureRepository,
    preuve: DocumentSigne,
) -> None:
    """L'écriture de liquidation d'abord, puis la preuve : une preuve sans
    écriture serait fausse ; une écriture sans preuve se complète en
    redéclarant (l'écriture déjà passée n'est pas réécrite)."""
    ecritures = ledger.grand_livre(dossier.id)
    liquidation = ecriture_liquidation(dossier.id, ecritures, etat.ca3)
    deja = {e.id for e in base.grand_livre(dossier.id)}
    if liquidation is not None and liquidation.id not in deja:
        base.enregistrer(liquidation)
    signatures.enregistrer(dossier.id, type_preuve(etat.ca3.periode), preuve)


def _enregistrer_routes_tva(app: FastAPI) -> None:
    """AXE-805 : la CA3 de chaque période, ses paramètres, sa déclaration."""

    @app.get("/dossiers/{dossier_id}/tva", response_model=TvaVue)
    def lire_tva(
        dossier: DossierDep,
        ledger: LedgerComptableDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        signatures: SignaturesInpiDep,
    ) -> TvaVue:
        return _tva_vue(dossier, _etats_tva(dossier, ledger, base, decisions, signatures))

    @app.put("/dossiers/{dossier_id}/tva/parametres", response_model=TvaVue)
    def parametrer_tva(
        entree: ParametresTvaEntree,
        dossier: DossierDep,
        dossiers: DossiersDep,
        ledger: LedgerComptableDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        signatures: SignaturesInpiDep,
        identite: IdentiteDep,
    ) -> TvaVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        periodicite = verifier_parametres(entree.periodicite, entree.jour_echeance)
        dossiers.parametrer_tva(
            dossier.id, periodicite, entree.jour_echeance, identite.user_id, datetime.now(UTC)
        )
        a_jour = dataclasses.replace(
            dossier, tva_periodicite=periodicite, tva_jour_echeance=entree.jour_echeance
        )
        return _tva_vue(a_jour, _etats_tva(a_jour, ledger, base, decisions, signatures))


def _enregistrer_route_declaration_tva(app: FastAPI) -> None:
    """AXE-805 : le chauffeur déclare avoir déposé la CA3 d'une période."""

    @app.post("/dossiers/{dossier_id}/tva/{cle}/declaration", response_model=TvaVue)
    def declarer_tva(
        cle: str,
        entree: DeclarationTvaEntree,
        dossier: DossierDep,
        ledger: LedgerComptableDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        signatures: SignaturesInpiDep,
        identite: IdentiteDep,
    ) -> TvaVue:
        """Le chauffeur déclare avoir déposé la CA3 sur impots.gouv : la
        liquidation s'écrit et la preuve est gardée (date de dépôt)."""
        identite = _verifier_acces_dossier(dossier.id, identite)
        etats = _etats_tva(dossier, ledger, base, decisions, signatures)
        etat = next((e for e in etats if e.ca3.periode.cle == cle), None)
        if etat is None:
            raise HTTPException(status_code=404, detail="Période de TVA inconnue.")
        if etat.declaree:
            raise HTTPException(status_code=409, detail="Cette période est déjà déclarée.")
        if entree.deposee_le < etat.ca3.periode.fin:
            raise HTTPException(
                status_code=422, detail="La déclaration se dépose après la fin de la période."
            )
        preuve = DocumentSigne(
            contenu_pdf=f"CA3 {cle} déposée le {entree.deposee_le.isoformat()}".encode(),
            signataire=identite.user_id,
            signe_le=datetime.combine(entree.deposee_le, datetime.min.time(), UTC),
            provider="declaration",
            qualifie=False,
        )
        _declarer_tva(dossier, etat, ledger, base, signatures, preuve)
        return _tva_vue(dossier, _etats_tva(dossier, ledger, base, decisions, signatures))


def _enregistrer_routes_societe(app: FastAPI) -> None:
    """Identité, registres officiels et bilan d'ouverture (AXE-846, 849, 804)."""
    _enregistrer_routes_identite(app)
    _enregistrer_routes_registre(app)
    _enregistrer_routes_ouverture(app)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AxeLCompta — API",
        version="0.0.1",
        dependencies=[Depends(exiger_double_authentification)],
    )
    from axelcompta.api.observabilite import brancher

    brancher(app)
    app.state.digifactory_branche = True
    _configurer_cors(app)
    brancher_erreurs(app)
    _configurer_contexte_rls(app)
    _enregistrer_routes_dossiers(app)
    _enregistrer_route_lecture_dossier(app)
    _enregistrer_routes_import_dossiers(app)
    _enregistrer_routes_securite(app)
    _enregistrer_routes_mfa_et_acces(app)
    _enregistrer_route_compte_de_test(app)
    _enregistrer_routes_expert_comptable(app)
    _enregistrer_routes_engagement(app)
    _enregistrer_routes_tva(app)
    _enregistrer_route_declaration_tva(app)
    _enregistrer_routes_integrations(app)
    _enregistrer_routes_transactions(app)
    _enregistrer_route_correction(app)
    _enregistrer_routes_annulation(app)
    _enregistrer_routes_anomalies(app)
    _enregistrer_route_historique_anomalie(app)
    _enregistrer_routes_expert(app)
    _enregistrer_routes_quarantaine(app)
    _enregistrer_routes_synchronisation(app)
    _enregistrer_routes_tags(app)
    _enregistrer_routes_revue(app)
    _enregistrer_routes_portefeuille(app)
    _enregistrer_route_categorisation(app)
    _enregistrer_routes_connexions(app)
    _enregistrer_routes_rappels(app)
    _enregistrer_route_declencher_rappel(app)
    _enregistrer_routes_regles(app)
    _enregistrer_routes_membres(app)
    _enregistrer_routes_invitation(app)
    _enregistrer_routes_cloture(app)
    _enregistrer_route_fec(app)
    _enregistrer_routes_exports(app)
    _enregistrer_routes_balance(app)
    _enregistrer_routes_comptes_bancaires(app)
    _enregistrer_routes_provisions(app)
    _enregistrer_routes_immobilisations(app)
    _enregistrer_routes_declarations(app)
    _enregistrer_routes_pieces_greffe(app)
    _enregistrer_routes_greffe_inpi(app)
    _enregistrer_routes_notifications(app)
    _enregistrer_routes_cloture_exercice(app)
    _enregistrer_routes_configuration(app)
    _enregistrer_routes_societe(app)
    _enregistrer_routes_affectation(app)
    _enregistrer_routes_dividendes_paie(app)
    _enregistrer_routes_paie(app)
    return app


app = create_app()
