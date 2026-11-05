"""API FastAPI dédiée à la démo produit (doc 17 §9, doc 19) — sert les 3
chauffeurs type au frontend Next.js.

Distincte de `axelcompta.api.app`, le point d'entrée HTTP : celui-ci
délègue ici tant que les routes n'ont pas chacune leur façade. Ceci est
une composition root comme `demo_chauffeurs_type.py` (doc 18), pas
soumise aux mêmes contraintes de dépendance qu'un module métier — elle
peut importer n'importe quoi directement, y compris une autre composition
root.

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

import dataclasses
import re
import uuid
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
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
from axelcompta.anomaly.instruction import RegistreInstructions, TransitionRefusee
from axelcompta.anomaly.models import Alerte, MouvementSurveille
from axelcompta.anomaly.service import analyser
from axelcompta.categorize.appris import (
    OperationTranchee,
    libelle_sans_categorie,
    propositions_apprises,
)
from axelcompta.categorize.ml_fallback import (
    ModeleMlIndisponible,
    charger_calibration,
    charger_modele,
)
from axelcompta.categorize.models import Etage
from axelcompta.categorize.rules_and_ml import CATEGORIE_PAR_DEFAUT, RulesAndMlPipeline
from axelcompta.closing.affectation import (
    MillesimeDividendesInconnu,
    disponible,
    distribuable,
    fiscalite,
)
from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.cloture_fiscale import chiffre_affaires_ht
from axelcompta.closing.dividendes import RetenuesDividendes, retenues
from axelcompta.closing.models import LiassePivot, ParametresCloture, ProvisionCloture
from axelcompta.closing.paie import Bulletin, BulletinIncoherent
from axelcompta.closing.provisions import ProvisionInvalide, valider_provision
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, EcritureId, TenantId, TransactionId, UserId
from axelcompta.core.rls import appliquer_rls, contexte_identite
from axelcompta.demo_auth import (
    IdentiteAuthentifiee,
    identite_chauffeur_optionnelle,
    identite_tolerante,
)
from axelcompta.demo_comptes import (
    CompteDejaInviteError,
    CompteRepository,
    InvitationAbsente,
    InvitationFermee,
    StatutInvitation,
    SupabaseCompteRepository,
    SupabaseConfig,
)
from axelcompta.demo_jalons import JALONS_EXERCICE, etape_depuis_preuves
from axelcompta.demo_justificatifs import JustificatifRepository
from axelcompta.documents.postgres import PostgresJustificatifRepository
from axelcompta.documents.preparer import JustificatifRefuse
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
from axelcompta.ingestion.consentement import ReleveConsentement, SanteConnexion, classer
from axelcompta.ingestion.consentement_postgres import PostgresConsentementRepository
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.contrepassation import annulees, contrepasser
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie, charger_regles
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
from axelcompta.tenants.exercices import ExerciceRepository
from axelcompta.tenants.exercices_postgres import PostgresExerciceRepository
from axelcompta.tenants.franchise_tva import MillesimeInconnu, suivre_franchise
from axelcompta.tenants.models import MODES_RELANCE, Dossier, Tenant
from axelcompta.tenants.orm import droits_membre, rappels, regles_rappel
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.provisions_cloture import ProvisionsClotureRepository
from axelcompta.tenants.provisions_cloture_postgres import PostgresProvisionsClotureRepository
from axelcompta.tenants.repository import DossierRepository
from axelcompta.tenants.statuts import (
    ColonneMatrice,
    FormeJuridique,
    RegimeTva,
    charger_matrice,
    configuration_de,
)
from axelcompta.workflow.decisions import (
    CATEGORIE_ANNULATION,
    DecisionHumaine,
    DecisionRepository,
    decision_en_vigueur,
)
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.expert import ImputationRefusee, preparer_imputation
from axelcompta.workflow.notifications import (
    NotificationRepository,
    ecritures_a_trancher,
    pour_la_cloche,
)
from axelcompta.workflow.notifications_postgres import PostgresNotificationRepository
from axelcompta.workflow.propositions import PropositionRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.relances_consentement import mode_effectif
from axelcompta.workflow.revue import (
    CategorieInconnueError,
    appliquer_decisions,
    resoudre_ecriture_a_trancher,
)
from axelcompta.workflow.signature import DocumentSigne, SignatureRepository
from axelcompta.workflow.signature_demo import SignatureDemoProvider
from axelcompta.workflow.signature_postgres import PostgresSignatureRepository

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


class AlerteAnomalieVue(BaseModel):
    id: str
    code: str
    libelle_ui: str
    detail: str
    etat: str
    libelle_mouvement: str
    montant_centimes: int
    date: str


class InstructionAnomalieEntree(BaseModel):
    decision: Literal["en_instruction", "justifiee", "usage_personnel", "faux_positif"]
    commentaire: str = ""


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
    origine_proposition: str | None = None  # "appris" | "regle" | "modele"
    confiance_proposition: float | None = None
    # Décision humaine en vigueur. None : classée par une règle, ou pas encore.
    categorie: str | None = None


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
    nature: Literal["a_trancher", "ticket", "anomalie"]
    libelle: str
    detail: str
    montant_cts: int | None
    ecriture_id: str | None
    imputable: bool
    compte_actuel: str | None = None
    compte_suggere: str | None = None


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


class FileExpertVue(BaseModel):
    sujets: list[SujetExpertVue]
    comptes: list[CompteChoix]


class ImputationEntree(BaseModel):
    dossier_id: str
    ecriture_id: str
    compte: str


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
    """Le ledger persisté, avec les décisions humaines ré-appliquées par-dessus
    (doc 17 §9 bloc A/C). Les écritures d'origine ne sont jamais modifiées en
    base (append-only, doc 06 §1) : une décision est une couche séparée."""
    resultat = InMemoryLedgerService()
    for ecriture in appliquer_decisions(
        base.grand_livre(dossier.id),
        decisions.lister_decisions(dossier.id),
        configuration_de(dossier).comptes_categories_statut(),
        charger_compte_par_categorie(),
    ):
        resultat.enregistrer(ecriture)
    return resultat


def _statut_invitation_vue(statut: StatutInvitation) -> str:
    return {StatutInvitation.INVITE: "invité", StatutInvitation.ACTIF: "actif"}[statut]


def _construire_liasse(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    provisions: tuple[ProvisionCloture, ...] = (),
) -> LiassePivot:
    """Semaine 4 (doc 17 §9) : même appel que `_resume` (clôture) et que les
    exports de `demo_chauffeurs_type._executer_un_chauffeur`, mais sur le
    ledger **avec les décisions humaines déjà appliquées**
    (`_ledger_avec_decisions`) : une transaction tranchée en 455/108 doit
    sortir de la liasse téléchargée, pas seulement du dashboard."""
    return ClotureSimplifieeService(ledger).cloturer(
        dossier.id,
        exercice=str(dossier.exercice_debut.year),
        parametres=_parametres(dossier, provisions),
    )


def _parametres(
    dossier: Dossier, provisions: tuple[ProvisionCloture, ...] = ()
) -> ParametresCloture:
    """Bornes déclarées de l'exercice et identité du dossier : ce qui fait
    passer la clôture du bilan simplifié à la liasse fiscale complète."""
    return ParametresCloture(
        exercice_debut=dossier.exercice_debut,
        exercice_fin=dossier.fin_exercice(),
        forme_juridique=dossier.forme_juridique,
        identite=dossier.identite,
        soumis_is=_colonne(dossier).soumis_is,
        associes=_colonne(dossier).associes,
        provisions=provisions,
    )


def _provisions_saisies(
    dossier: Dossier, depot: ProvisionsClotureRepository
) -> tuple[ProvisionCloture, ...]:
    return depot.lister(dossier.tenant_id, dossier.id, dossier.fin_exercice().year)


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
    provisions: tuple[ProvisionCloture, ...] = (),
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
    provisions: tuple[ProvisionCloture, ...] = (),
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
    return [_transaction_vue(e, e.id in avec_photo, e.id in exclues) for e in ecritures]


def _transactions_dossier(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    justificatifs: JustificatifRepository,
    decisions: tuple[DecisionHumaine, ...] = (),
    pipeline: RulesAndMlPipeline | None = None,
) -> list[TransactionVue]:
    """Extrait de la route (doc 08 §2 : longueur de fonction)."""
    vues = _avec_categories(_vues_dossier(dossier, ledger, justificatifs), decisions)
    return _avec_propositions(dossier, vues, decisions, pipeline)


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


_ORIGINE_PAR_ETAGE = {Etage.REGLE: "regle", Etage.ML: "modele"}


def _avec_propositions(
    dossier: Dossier,
    vues: list[TransactionVue],
    decisions: tuple[DecisionHumaine, ...],
    pipeline: RulesAndMlPipeline | None,
) -> list[TransactionVue]:
    """Une proposition par opération à trancher : d'abord une opération
    semblable que l'indiv a déjà tranchée (dernière décision de chaque
    écriture), sinon le pipeline actuel. Rien si le modèle s'abstient."""
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
            dossier.id,
            [
                NormalizedTransaction(
                    id=TransactionId(vue.ecriture_id),
                    dossier_id=dossier.id,
                    date=date.fromisoformat(vue.date),
                    montant_cts=vue.montant_cts,
                    libelle=libelle,
                    source_provider="lecture",
                    raw_payload={},
                )
                for vue, (libelle, _) in zip(a_trancher, requetes, strict=True)
            ],
        )
        if pipeline is not None
        else [None] * len(a_trancher)
    )
    mises_a_jour: dict[str, dict[str, object]] = {}
    for vue, apprise, actuelle in zip(a_trancher, apprises, actuelles, strict=True):
        if apprise is not None:
            mises_a_jour[vue.ecriture_id] = {
                "proposition": apprise.categorie,
                "origine_proposition": "appris",
                "confiance_proposition": round(apprise.similarite, 2),
            }
        elif actuelle is not None and actuelle.categorie != CATEGORIE_PAR_DEFAUT:
            mises_a_jour[vue.ecriture_id] = {
                "proposition": actuelle.categorie,
                "origine_proposition": _ORIGINE_PAR_ETAGE.get(actuelle.etage),
                "confiance_proposition": round(actuelle.confiance, 2),
            }
    return [
        vue.model_copy(update=mises_a_jour[vue.ecriture_id])
        if vue.ecriture_id in mises_a_jour
        else vue
        for vue in vues
    ]


def _nb_a_trancher(ecritures: tuple[Ecriture, ...] | list[Ecriture]) -> int:
    exclues = annulees(ecritures)
    return sum(
        1
        for e in ecritures
        if e.id not in exclues and any(ligne.compte == COMPTE_ATTENTE for ligne in e.lignes)
    )


def _montant_512(ecriture: Ecriture) -> int:
    """Le sens de la ligne 512 donne le montant signé façon relevé bancaire
    (doc 11 §1 : « chiffres irréprochables »), pas le montant absolu."""
    for ligne in ecriture.lignes:
        if ligne.compte == "512":
            signe = 1 if ligne.sens is Sens.DEBIT else -1
            return signe * ligne.montant.centimes
    return 0


def _compte_affiche(ecriture: Ecriture) -> str:
    """Une écriture de settlement a plusieurs comptes en contrepartie du 512
    (706/622/44566/44571) — pas un seul compte à afficher tel quel."""
    autres = [ligne.compte for ligne in ecriture.lignes if ligne.compte != "512"]
    return autres[0] if len(autres) == 1 else "règlement plateforme"


def _vue_tranchee(ecriture: Ecriture, a_justificatif: bool, categorie: str) -> TransactionVue:
    """Réponse d'une décision ou d'une correction : la catégorie vient d'être posée."""
    return _transaction_vue(ecriture, a_justificatif, annulee=False).model_copy(
        update={"categorie": categorie}
    )


def _transaction_vue(ecriture: Ecriture, a_justificatif: bool, annulee: bool) -> TransactionVue:
    a_trancher = not annulee and any(ligne.compte == COMPTE_ATTENTE for ligne in ecriture.lignes)
    return TransactionVue(
        ecriture_id=ecriture.id,
        date=ecriture.date.isoformat(),
        libelle=ecriture.libelle,
        montant_cts=_montant_512(ecriture),
        compte=_compte_affiche(ecriture),
        statut="à trancher" if a_trancher else "validé",
        a_justificatif=a_justificatif,
    )


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
    autres = [ligne.compte for ligne in ecriture.lignes if ligne.compte != "512"]
    if len(autres) != 1 or not categorie:
        return None
    return MouvementSurveille(
        dossier_id=dossier.id,
        ecriture_id=ecriture.id,
        date=ecriture.date,
        libelle=ecriture.libelle,
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
) -> tuple[MouvementSurveille, ...]:
    """Sorties catégorisées, hors écritures contre-passées. Plafond 10 000."""
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
        autres = [ligne.compte for ligne in ecriture.lignes if ligne.compte != "512"]
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
            mouvements.append(mouvement)
    return tuple(mouvements)


_ENGINE_DEMO: Engine | None = None


def _engine() -> Engine:
    """Engine Postgres partagé, construit **à la première requête réelle**,
    pas à l'import du module : importer `demo_api` (pour ses tests, par
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


def get_propositions() -> PropositionRepository:
    """Dépendance FastAPI — ce que le pipeline avait proposé par écriture."""
    return PostgresPropositionRepository(_engine())


_PIPELINE: RulesAndMlPipeline | None = None


def get_pipeline() -> RulesAndMlPipeline:
    """Dépendance FastAPI — règles du pack et modèle chargés une fois par
    processus. Sans modèle sur le poste (fichier gitignoré), les règles
    seules : l'étage ML s'abstient, rien ne plante (doc 08 §5)."""
    global _PIPELINE
    if _PIPELINE is None:
        try:
            modele = charger_modele()
        except ModeleMlIndisponible:
            modele = None
        _PIPELINE = RulesAndMlPipeline(
            regles=charger_regles(),
            modele=modele,
            calibration=charger_calibration() if modele is not None else None,
        )
    return _PIPELINE


DecisionsDep = Annotated[DecisionRepository, Depends(get_decisions)]
DossiersDep = Annotated[DossierRepository, Depends(get_dossiers)]
LedgerBaseDep = Annotated[LedgerService, Depends(get_ledger)]
PropositionsDep = Annotated[PropositionRepository, Depends(get_propositions)]
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

IdentiteDep = Annotated[IdentiteAuthentifiee | None, Depends(identite_chauffeur_optionnelle)]


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


def get_ledger_du_dossier(
    dossier: DossierDep, base: LedgerBaseDep, decisions: DecisionsDep
) -> InMemoryLedgerService:
    return _ledger_avec_decisions(dossier, base, decisions)


LedgerDossierDep = Annotated[InMemoryLedgerService, Depends(get_ledger_du_dossier)]


def get_justificatifs() -> JustificatifRepository:
    """Postgres, rôle web, policies RLS. Les tests surchargent avec
    `InMemoryJustificatifRepository`."""
    return PostgresJustificatifRepository(_engine())


JustificatifsDep = Annotated[JustificatifRepository, Depends(get_justificatifs)]

_REGISTRE_ANOMALIES = RegistreInstructions()


def get_registre_anomalies() -> RegistreInstructions:
    """Qualifications d'alertes, en mémoire de process. Les tests passent
    une instance neuve."""
    return _REGISTRE_ANOMALIES


RegistreAnomaliesDep = Annotated[RegistreInstructions, Depends(get_registre_anomalies)]


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


def _trancher(
    dossier: Dossier,
    ecriture_id: str,
    categorie: str,
    base: LedgerService,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
    decide_par: UserId,
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
    _enregistrer_decision(dossier, ecriture, categorie, decisions, propositions, decide_par)
    return _ecriture_decidee(dossier, base, decisions, ecriture_id)


def _corriger(
    dossier: Dossier,
    ecriture_id: str,
    categorie: str,
    base: LedgerService,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
    decide_par: UserId,
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
    _enregistrer_decision(dossier, ecriture, categorie, decisions, propositions, decide_par)
    return _ecriture_decidee(dossier, base, decisions, ecriture_id)


def _enregistrer_decision(
    dossier: Dossier,
    ecriture: Ecriture,
    categorie: str,
    decisions: DecisionRepository,
    propositions: PropositionRepository,
    decide_par: UserId,
) -> None:
    """Pose la décision si la catégorie a un compte. N'écrit rien sinon."""
    proposition = propositions.obtenir(dossier.id, ecriture.id)
    if proposition is None:
        raise HTTPException(
            status_code=500,
            detail="Cette opération n'a pas de proposition d'origine.",
        )
    comptes = charger_compte_par_categorie()
    try:
        resoudre_ecriture_a_trancher(
            ecriture, categorie, configuration_de(dossier).comptes_categories_statut(), comptes
        )
    except CategorieInconnueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    courante = decisions.decision_courante(dossier.id, ecriture.id)
    maintenant = datetime.now(UTC)
    if courante is not None and maintenant <= courante.decide_le:
        maintenant = courante.decide_le + timedelta(microseconds=1)
    decisions.enregistrer_decision(
        DecisionHumaine(
            dossier_id=dossier.id,
            ecriture_id=ecriture.id,
            categorie=categorie,
            etage_origine=proposition.etage,
            confiance_origine=proposition.confiance,
            decide_par=decide_par,
            decide_le=maintenant,
        )
    )


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
) -> TransactionVue:
    """Enregistre une décision qui en remplace une déjà en vigueur."""
    courante = decisions.decision_courante(dossier.id, EcritureId(ecriture_id))
    en_vigueur = decision_en_vigueur(courante)
    if en_vigueur is None:
        raise HTTPException(status_code=409, detail="Cette opération n'a pas encore été classée.")
    if categorie != CATEGORIE_ANNULATION:
        ecritures = base.grand_livre(dossier.id)
        ecriture = next((e for e in ecritures if e.id == ecriture_id), None)
        if ecriture is None:
            raise HTTPException(status_code=404, detail=f"Écriture inconnue : {ecriture_id}")
        try:
            resoudre_ecriture_a_trancher(
                ecriture,
                categorie,
                configuration_de(dossier).comptes_categories_statut(),
                charger_compte_par_categorie(),
            )
        except CategorieInconnueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    decisions.enregistrer_decision(
        DecisionHumaine(
            dossier_id=dossier.id,
            ecriture_id=EcritureId(ecriture_id),
            categorie=categorie,
            etage_origine=en_vigueur.etage_origine,
            confiance_origine=en_vigueur.confiance_origine,
            decide_par=decide_par,
            decide_le=datetime.now(UTC),
        )
    )
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    ecritures_vues = ledger.grand_livre(dossier.id)
    ecriture_vue = next(e for e in ecritures_vues if e.id == ecriture_id)
    return _transaction_vue(
        ecriture_vue,
        justificatifs.a_un_justificatif(dossier.tenant_id, dossier.id, ecriture_vue.id),
        ecriture_vue.id in annulees(ecritures_vues),
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
        try:
            resoudre_ecriture_a_trancher(ecriture, entree.categorie, comptes_statut, comptes)
        except CategorieInconnueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        a_ecrire.append(
            DecisionHumaine(
                dossier_id=dossier.id,
                ecriture_id=ecriture.id,
                categorie=entree.categorie,
                etage_origine=proposition.etage,
                confiance_origine=proposition.confiance,
                decide_par=decide_par,
                decide_le=maintenant,
            )
        )
    decisions.enregistrer_decisions(a_ecrire)
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
    try:
        justificatifs.enregistrer(dossier.tenant_id, dossier.id, ecriture.id, contenu, extension)
    except JustificatifRefuse as erreur:
        raise HTTPException(status_code=400, detail=str(erreur)) from erreur
    return ecriture


def _configurer_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ORIGINE_FRONTEND_DEV],
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
        with contexte_identite(
            dossier_id=str(identite.dossier_id) if identite and identite.dossier_id else None,
            tenant_id=str(identite.tenant_id) if identite and identite.tenant_id else None,
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


def _agregats_portefeuille(
    dossiers: Sequence[Dossier],
    base: LedgerService,
    decisions: DecisionRepository,
    comptes: CompteRepository,
    signatures: SignatureRepository,
    provisions: ProvisionsClotureRepository,
    agregats: AgregatsRepository,
) -> list[DossierAgregat]:
    """Une lecture des agrégats gardés, une lecture des comptes (Supabase,
    tous les dossiers d'un coup), puis par dossier ce qui change sans
    écriture : les preuves de l'exercice et la date du jour."""
    ids = [dossier.id for dossier in dossiers]
    lignes = agregats.lire(ids)
    invitations = comptes.statuts(ids)
    preuves = _preuves_exercice(signatures, ids)
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
            )
        )
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
        identite: IdentiteDep,
    ) -> list[DossierAgregat]:
        """Vue gestionnaire (doc 19 §2.1) : agrégats des dossiers **de son
        portefeuille** seulement (`tenant_id` du jeton), rien d'autre. Les
        montants viennent de la base (`agregats_dossier`, périmés par des
        triggers) : ouvrir la liste ne reparcourt pas le grand livre de
        chaque dossier."""
        tenant_id, identite = _verifier_acces_gestionnaire(identite)
        return _agregats_portefeuille(
            dossiers.lister_par_tenant(tenant_id),
            base,
            decisions,
            comptes,
            signatures,
            provisions,
            agregats,
        )

    @app.get("/dossiers/{dossier_id}", response_model=DossierResume)
    def obtenir_dossier(
        request: Request,
        dossier: DossierDep,
        ledger: LedgerDossierDep,
        comptes: ComptesDep,
        signatures: SignaturesInpiDep,
        avenants: AvenantsDep,
        provisions: ProvisionsDep,
    ) -> DossierResume:
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
    ) -> list[TransactionVue]:
        return _transactions_dossier(
            dossier, ledger, justificatifs, decisions.lister_decisions(dossier.id), pipeline
        )

    @app.post("/dossiers/{dossier_id}/decisions-groupees", response_model=list[TransactionVue])
    def trancher_en_groupe(
        entree: DecisionsGroupeesEntree,
        dossier: DossierDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        propositions: PropositionsDep,
        justificatifs: JustificatifsDep,
        identite: IdentiteDep,
    ) -> list[TransactionVue]:
        """« Tout confirmer » : les mêmes contrôles que pour une décision
        seule, sur chaque opération, avant d'écrire quoi que ce soit ; puis
        toutes les décisions dans une seule transaction."""
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecritures = _trancher_groupe(
            dossier, entree, base, decisions, propositions, identite.user_id
        )
        avec_photo = justificatifs.presents(dossier.tenant_id, dossier.id)
        return [_vue_tranchee(e, e.id in avec_photo, entree.categorie) for e in ecritures]


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
        identite: IdentiteDep,
    ) -> TransactionVue:
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecriture = _corriger(
            dossier, ecriture_id, entree.categorie, base, decisions, propositions, identite.user_id
        )
        return _vue_tranchee(
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
        identite: IdentiteDep,
    ) -> TransactionVue:
        """Indiv qui tranche sa propre écriture (doc 19 §5.6, doc 19 §8bis :
        jeton obligatoire depuis le 2026-09-11) — `DossierDep` refuse déjà
        l'accès à un autre dossier."""
        identite = _verifier_acces_dossier(dossier.id, identite)
        ecriture = _trancher(
            dossier, ecriture_id, entree.categorie, base, decisions, propositions, identite.user_id
        )
        # `_trancher` refuse une écriture contre-passée : celle-ci ne l'est pas.
        return _vue_tranchee(
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
        )


_ROLES = frozenset({"admin", "membre", "lecture"})
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

    @app.post("/rappels", response_model=RappelVue)
    def declencher_rappel(
        entree: RappelEntree, identite: IdentiteDep, role: RoleMembreDep
    ) -> RappelVue:
        """Enregistre un envoi à partir d'une règle. Le canal n'est pas
        branché : SMS, e-mail et appel restent à connecter."""
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
    if entree.declencheur not in {"manuel", "avant_cloture"} or entree.portee not in {
        "tous",
        "selection",
    }:
        raise HTTPException(status_code=400, detail="Déclencheur ou portée inconnue.")
    if entree.declencheur == "avant_cloture" and not entree.jours_avant:
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
        jours_avant=entree.jours_avant if entree.declencheur == "avant_cloture" else None,
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
    if declencheur not in {"manuel", "avant_cloture"}:
        raise HTTPException(status_code=400, detail="Déclencheur inconnu.")
    if declencheur == "avant_cloture" and not jours_avant:
        raise HTTPException(status_code=400, detail="Indique le nombre de jours.")
    jours = jours_avant if declencheur == "avant_cloture" else None
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
        try:
            comptes.inviter_membre(str(tenant_id), email, entree.role)
        except CompteDejaInviteError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        try:
            invitation = comptes.inviter(dossier.id, entree.email)
        except CompteDejaInviteError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        pdf = extraire_page_2033(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions)), "2033A"
        )
        return _fichier(pdf, "application/pdf", f"bilan-actif-passif-{dossier.id}.pdf")

    @app.get("/dossiers/{dossier_id}/compte-resultat.pdf")
    def telecharger_compte_resultat(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        pdf = extraire_page_2033(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions)), "2033B"
        )
        return _fichier(pdf, "application/pdf", f"compte-de-resultat-{dossier.id}.pdf")


def _enregistrer_routes_declarations(app: FastAPI) -> None:
    """Déclaration de résultat selon la colonne de la matrice (doc 06 §7) :
    2065 à l'IS, 2031 à l'IR. L'autre répond 409, jamais un formulaire faux."""

    @app.get("/dossiers/{dossier_id}/cerfa-2065.pdf")
    def telecharger_cerfa(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        if not _colonne(dossier).soumis_is:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{_colonne(dossier).libelle} : la 2065 ne concerne que l'IS, "
                    "l'impôt sur les sociétés."
                ),
            )
        pdf = PdfCerfa2065Renderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _fichier(pdf, "application/pdf", f"cerfa-2065-{dossier.id}.pdf")

    @app.get("/dossiers/{dossier_id}/cerfa-2031.pdf")
    def telecharger_cerfa_2031(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        if _colonne(dossier).soumis_is:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{_colonne(dossier).libelle} : la 2031 ne concerne que l'IR, "
                    "l'impôt sur le revenu."
                ),
            )
        pdf = PdfCerfa2031Renderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _fichier(pdf, "application/pdf", f"cerfa-2031-{dossier.id}.pdf")


def _enregistrer_routes_cloture(app: FastAPI) -> None:
    """Semaine 4 (doc 17 §9) : les renderers de clôture, exposés en
    téléchargement direct — sur le ledger avec décisions humaines appliquées
    (`_construire_liasse`), pas le ledger brut."""

    @app.get("/dossiers/{dossier_id}/liasse.pdf")
    def telecharger_liasse(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        pdf = PdfLiasseSimplifieeRenderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _fichier(pdf, "application/pdf", f"liasse-{dossier.id}.pdf")

    @app.get("/dossiers/{dossier_id}/liasse-fiscale.pdf")
    def telecharger_liasse_fiscale(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        _exiger_operations_tranchees(dossier, ledger)
        pdf = PdfLiasseFiscaleRenderer().rendre(
            _construire_liasse(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _fichier(pdf, "application/pdf", f"liasse-fiscale-{dossier.id}.pdf")

    @app.get("/dossiers/{dossier_id}/fec.txt")
    def telecharger_fec(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
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
        return _fichier(exporter_fec(ecritures), "text/plain; charset=utf-8", nom)


def _enregistrer_routes_exports(app: FastAPI) -> None:
    @app.get("/dossiers/{dossier_id}/grand-livre.csv")
    def telecharger_grand_livre(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        return _fichier(
            exporter_grand_livre(ecritures), "text/csv", f"grand-livre-{dossier.id}.csv"
        )

    @app.get("/dossiers/{dossier_id}/grand-livre.pdf")
    def telecharger_grand_livre_pdf(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        pdf = rendre_grand_livre_pdf(ecritures, dossier_id=str(dossier.id))
        return _fichier(pdf, "application/pdf", f"grand-livre-{dossier.id}.pdf")

    @app.get("/dossiers/{dossier_id}/balance.csv")
    def telecharger_balance(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        return _fichier(exporter_balance(ecritures), "text/csv", f"balance-{dossier.id}.csv")

    @app.get("/dossiers/{dossier_id}/balance.pdf")
    def telecharger_balance_pdf(
        dossier: DossierDep, ledger: LedgerDossierDep, provisions: ProvisionsDep
    ) -> Response:
        ecritures = _ecritures_avec_cloture(
            dossier, ledger, _provisions_saisies(dossier, provisions)
        )
        pdf = rendre_balance_pdf(ecritures, dossier_id=str(dossier.id))
        return _fichier(pdf, "application/pdf", f"balance-{dossier.id}.pdf")


def _document_greffe_inpi(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    provisions: tuple[ProvisionCloture, ...] = (),
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
    ) -> Response:
        _exiger_depot_greffe(dossier)
        document_signe = signatures.dernier(dossier.id, TYPE_DOCUMENT_GREFFE_INPI)
        pdf = (
            document_signe.contenu_pdf
            if document_signe is not None
            else _document_greffe_inpi(dossier, ledger, _provisions_saisies(dossier, provisions))
        )
        return _fichier(pdf, "application/pdf", f"greffe-inpi-{dossier.id}.pdf")

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
        # signature de validation sont déjà là (préfixe, demo_jalons).
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
    ) -> list[NotificationVue]:
        nb = len(ecritures_a_trancher(ledger, decisions, dossier.id))
        visibles = pour_la_cloche(
            notifications.lister(dossier.id, _HISTORIQUE_AVANT_REGROUPEMENT),
            nb,
            _NOTIFICATIONS_AFFICHEES,
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
    provisions: tuple[ProvisionCloture, ...] = (),
) -> PassageExercice:
    try:
        return preparer_passage(
            dossier,
            ledger,
            decisions,
            avenants.lister(dossier.id),
            datetime.now(UTC).date(),
            provisions,
        )
    except PassageRefuse as exc:
        erreur = HTTPException(status_code=409, detail=str(exc))
        erreur.code_metier = exc.code  # type: ignore[attr-defined]
        raise erreur from exc


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
    try:
        for provision in provisions:
            valider_provision(provision)
    except ProvisionInvalide as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
        return _vue_provisions(_provisions_saisies(dossier, provisions))

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


def _vue_cloture_impossible(refus: HTTPException, debut: str, fin: str) -> ClotureExerciceVue:
    return ClotureExerciceVue(
        possible=False,
        raison=str(refus.detail),
        code=getattr(refus, "code_metier", None),
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
        except HTTPException as refus:
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
    try:
        return proposer(dossier, ledger, exercices, affectations, datetime.now(UTC).date())
    except (AffectationImpossible, MillesimeDividendesInconnu) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
        except HTTPException as refus:
            return AffectationVue(applicable=False, raison=str(refus.detail))
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
        try:
            decides = dividendes_decides(dossier, ledger, exercices, affectations)
            detail = declarer_versement(
                decides,
                dossier,
                ledger,
                corps.verse_le,
                corps.dispense_prelevement,
                datetime.now(UTC).date(),
            )
        except (AffectationImpossible, MillesimeDividendesInconnu) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        try:
            ecriture = enregistrer_bulletin(dossier, ledger, bulletin)
        except AffectationImpossible as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except BulletinIncoherent as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    )


def _alertes_du_ledger(
    dossier: Dossier,
    ledger: InMemoryLedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
) -> dict[str, Alerte]:
    """Les alertes d'un ledger déjà construit avec les décisions : qui en a
    déjà un ne le relit pas en base."""
    mouvements = _mouvements_surveilles(dossier, ledger, justificatifs, decisions)
    return {alerte.id: alerte for alerte in analyser(mouvements)}


def _alertes_du_dossier(
    dossier: Dossier,
    base: LedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
) -> dict[str, Alerte]:
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    return _alertes_du_ledger(dossier, ledger, decisions, justificatifs)


def _enregistrer_routes_anomalies(app: FastAPI) -> None:
    @app.get("/dossiers/{dossier_id}/anomalies", response_model=list[AlerteAnomalieVue])
    def lister_anomalies(
        dossier: DossierPortefeuilleDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        justificatifs: JustificatifsDep,
        registre: RegistreAnomaliesDep,
    ) -> list[AlerteAnomalieVue]:
        alertes = _alertes_du_dossier(dossier, base, decisions, justificatifs)
        return [_alerte_vue(alerte, registre.etat(alerte.id)) for alerte in alertes.values()]

    @app.post(
        "/dossiers/{dossier_id}/anomalies/{alerte_id}",
        response_model=AlerteAnomalieVue,
    )
    def instruire_anomalie(
        alerte_id: str,
        entree: InstructionAnomalieEntree,
        dossier: DossierPortefeuilleDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        justificatifs: JustificatifsDep,
        registre: RegistreAnomaliesDep,
        identite: IdentiteDep,
        role: RoleMembreDep,
    ) -> AlerteAnomalieVue:
        """Le gestionnaire qualifie. Lecture consulte, ne qualifie pas."""
        _exiger_ecriture(role, "La lecture ne qualifie pas une alerte.")
        _, identite = _verifier_acces_gestionnaire(identite)
        alertes = _alertes_du_dossier(dossier, base, decisions, justificatifs)
        alerte = alertes.get(alerte_id)
        if alerte is None:
            raise HTTPException(status_code=404, detail="Alerte inconnue.")
        try:
            etat = registre.instruire(
                alerte_id, entree.decision, identite.user_id, entree.commentaire
            )
        except TransitionRefusee as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        return _alerte_vue(alerte, etat)


_CATEGORIES_TICKET = frozenset({"usage_personnel_suspect", "non_categorise_a_verifier"})


def _categorie_du_libelle(libelle: str) -> str | None:
    debut = libelle.rfind(" (")
    if debut < 0 or not libelle.endswith(")"):
        return None
    return libelle[debut + 2 : -1]


def _ticket_necessaire(vue: TransactionVue) -> bool:
    if vue.montant_cts >= 0 or vue.a_justificatif or vue.statut == "à trancher":
        return False
    categorie = _categorie_du_libelle(vue.libelle)
    if categorie is None:
        return False
    return categorie in _CATEGORIES_TICKET or categorie.startswith("a_verifier")


def _compte_chiffre(compte: str) -> str | None:
    return compte if compte.isdigit() else None


def _compte_suggere(proposition: str | None) -> str | None:
    if not proposition:
        return None
    compte = charger_compte_par_categorie().get(proposition)
    if compte and compte != "512" and not compte.startswith("445"):
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
            if compte != "512" and not compte.startswith("445")
        }
    )
    return [CompteChoix(compte=compte, libelle=libelle_compte(compte)) for compte in comptes]


def _sujet_depuis_vue(dossier: Dossier, vue: TransactionVue) -> SujetExpertVue | None:
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
    if not _ticket_necessaire(vue):
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
    registre: RegistreInstructions,
    exclues: frozenset[EcritureId],
) -> list[SujetExpertVue]:
    sujets: list[SujetExpertVue] = []
    alertes = _alertes_du_ledger(dossier, ledger, decisions, justificatifs)
    for alerte in alertes.values():
        if alerte.ecriture_id in exclues:
            continue
        if registre.etat(alerte.id) not in ("ouverte", "en_instruction"):
            continue
        sujets.append(
            _sujet(
                dossier,
                f"anomalie:{alerte.id}",
                "gestionnaire",
                "anomalie",
                alerte.libelle_ui,
                alerte.detail,
                alerte.montant_centimes,
                str(alerte.ecriture_id),
            )
        )
    return sujets


def _sujets_expert(
    dossier: Dossier,
    base: LedgerService,
    decisions: DecisionRepository,
    justificatifs: JustificatifRepository,
    registre: RegistreInstructions,
) -> list[SujetExpertVue]:
    ledger = _ledger_avec_decisions(dossier, base, decisions)
    exclues = annulees(ledger.grand_livre(dossier.id))
    sujets = [
        sujet
        for vue in _vues_dossier(dossier, ledger, justificatifs)
        if EcritureId(vue.ecriture_id) not in exclues
        if (sujet := _sujet_depuis_vue(dossier, vue)) is not None
    ]
    sujets.extend(_sujets_anomalies(dossier, ledger, decisions, justificatifs, registre, exclues))
    return sujets


def _sujet(
    dossier: Dossier,
    sujet_id: str,
    cote: Literal["chauffeur", "gestionnaire"],
    nature: Literal["a_trancher", "ticket", "anomalie"],
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
    identite: IdentiteDep,
) -> ImputationVue:
    """Pose la contre-passation et la nouvelle écriture. L'originale reste.
    La réponse dit ce qui a été écrit, et les sujets à jour de ce dossier seul."""
    tenant_id, _identite = _verifier_acces_gestionnaire(identite)
    dossier = dossiers.obtenir(DossierId(entree.dossier_id))
    if dossier is None or dossier.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Dossier inconnu.")
    connus = {ecriture.id: ecriture for ecriture in base.grand_livre(dossier.id)}
    ecriture = connus.get(EcritureId(entree.ecriture_id))
    if ecriture is None:
        raise HTTPException(status_code=404, detail="Écriture inconnue.")
    try:
        inverse, nouvelle = preparer_imputation(ecriture, entree.compte, set(connus))
    except ImputationRefusee as erreur:
        raise HTTPException(status_code=400, detail=str(erreur)) from erreur
    base.enregistrer(inverse)
    base.enregistrer(nouvelle)
    sujets = _sujets_expert(dossier, base, decisions, justificatifs, registre)
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
    identite: IdentiteDep,
) -> None:
    """Contre-passe la nouvelle écriture et l'inverse posé par l'imputation.
    Le solde revient à l'écriture d'origine."""
    tenant_id, _identite = _verifier_acces_gestionnaire(identite)
    dossier = dossiers.obtenir(DossierId(entree.dossier_id))
    if dossier is None or dossier.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Dossier inconnu.")
    connus = {ecriture.id: ecriture for ecriture in base.grand_livre(dossier.id)}
    for identifiant in (entree.ecriture_id, entree.contrepassation_id):
        ecriture = connus.get(EcritureId(identifiant))
        if ecriture is None:
            raise HTTPException(status_code=404, detail="Écriture inconnue.")
        inverse = contrepasser(ecriture)
        if inverse.id not in connus:
            base.enregistrer(inverse)
            connus[inverse.id] = inverse


def _enregistrer_routes_expert(app: FastAPI) -> None:
    @app.get("/expert/file", response_model=FileExpertVue)
    def lire_file_expert(
        dossiers: DossiersDep,
        base: LedgerBaseDep,
        decisions: DecisionsDep,
        justificatifs: JustificatifsDep,
        registre: RegistreAnomaliesDep,
        identite: IdentiteDep,
    ) -> FileExpertVue:
        """File de l'expert-comptable : sujets chauffeur et gestionnaire,
        tous dossiers du portefeuille. Le portefeuille agrégé ne change pas."""
        tenant_id, _identite = _verifier_acces_gestionnaire(identite)
        sujets: list[SujetExpertVue] = []
        for dossier in dossiers.lister_par_tenant(tenant_id):
            sujets.extend(_sujets_expert(dossier, base, decisions, justificatifs, registre))
        return FileExpertVue(sujets=sujets, comptes=_comptes_expert())

    app.post("/expert/imputations", response_model=ImputationVue)(imputer_ecriture)
    app.post("/expert/imputations/annuler", status_code=204)(annuler_imputation)


def create_app() -> FastAPI:
    app = FastAPI(title="AxeLCompta — démo produit (API)", version="0.0.1")
    from axelcompta.api.observabilite import brancher

    brancher(app)
    app.state.digifactory_branche = True
    _configurer_cors(app)
    _configurer_contexte_rls(app)
    _enregistrer_routes_dossiers(app)
    _enregistrer_routes_transactions(app)
    _enregistrer_route_correction(app)
    _enregistrer_routes_annulation(app)
    _enregistrer_routes_anomalies(app)
    _enregistrer_routes_expert(app)
    _enregistrer_routes_revue(app)
    _enregistrer_routes_portefeuille(app)
    _enregistrer_routes_connexions(app)
    _enregistrer_routes_rappels(app)
    _enregistrer_routes_regles(app)
    _enregistrer_routes_membres(app)
    _enregistrer_routes_invitation(app)
    _enregistrer_routes_cloture(app)
    _enregistrer_routes_exports(app)
    _enregistrer_routes_provisions(app)
    _enregistrer_routes_declarations(app)
    _enregistrer_routes_pieces_greffe(app)
    _enregistrer_routes_greffe_inpi(app)
    _enregistrer_routes_notifications(app)
    _enregistrer_routes_cloture_exercice(app)
    _enregistrer_routes_affectation(app)
    _enregistrer_routes_dividendes_paie(app)
    _enregistrer_routes_paie(app)
    return app


app = create_app()
