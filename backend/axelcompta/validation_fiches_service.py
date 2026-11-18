"""Vérifier les critères d'import de chaque fiche (AXE-989).

Composition root : lit pour chaque fiche reliée à un dossier sa banque
(comptes, grand livre), ses jours Rollee et ses documents, calcule les
critères (`validation_fiches.py`) et garde leurs manques sur la fiche. Lancé
au passage horaire, après la synchro : une fiche dont Digifactory ou Rollee
décroche redevient « en traitement ».
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.couverture_bancaire_fiche import couverture_de_la_fiche
from axelcompta.couverture_plateformes import (
    couverture,
    jours_rollee,
    mois_avec_banque,
    recaps_deposes,
    virements_vus,
)
from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.ingestion.comptes_bancaires_postgres import PostgresCompteBancaireRepository
from axelcompta.ingestion.settlements_plateforme import SettlementStocke
from axelcompta.ingestion.settlements_plateforme_postgres import PostgresSettlements
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.stockage_documents import depot_documents
from axelcompta.tenants.fiches_import import DocumentImport, FicheImport
from axelcompta.tenants.fiches_import_depot import FichesImportRepository
from axelcompta.tenants.fiches_import_etat import debut_a_couvrir, exercices
from axelcompta.tenants.fiches_import_postgres import PostgresFichesImport
from axelcompta.tenants.fiches_import_validation import (
    CHAMP_VALIDATION,
    SECTIONS_VALIDEES,
    manques_gardes,
)
from axelcompta.traitement_documents_import import traiter
from axelcompta.validation_fiches import (
    Validation,
    plateformes_declarees,
    valider_banque,
    valider_plateformes,
)


def valider_fiche(
    fiche: FicheImport,
    documents: Sequence[DocumentImport],
    comptes: Sequence[CompteBancaire],
    grand_livre: Sequence[Ecriture],
    stockes: Sequence[SettlementStocke],
    maintenant: datetime,
) -> Validation:
    """Les critères d'une fiche reliée à son dossier. `documents` portent
    déjà leurs mouvements (FEC et QIF lus avant AXE-973 relus)."""
    aujourd_hui = maintenant.date()
    lus = exercices(fiche.champs, aujourd_hui, documents)
    couverts = couverture_de_la_fiche(fiche, documents, comptes, grand_livre, aujourd_hui)
    jours = jours_rollee(stockes)
    plateformes = couverture(
        jours,
        virements_vus(grand_livre),
        recaps_deposes(documents),
        debut_a_couvrir(fiche.champs, aujourd_hui),
        aujourd_hui,
        mois_avec_banque(grand_livre),
    )
    criteres = [
        *valider_banque(lus, comptes, couverts, aujourd_hui),
        *valider_plateformes(
            lus, plateformes, jours, plateformes_declarees(fiche.champs), aujourd_hui
        ),
    ]
    return Validation(tuple(criteres), maintenant)


def avec_validation(fiche: FicheImport, validation: Validation) -> FicheImport | None:
    """La fiche avec sa validation, ou `None` si rien n'a changé (pas de
    réécriture chaque heure pour une fiche stable)."""
    inchangee = all(
        manques_gardes(fiche.champs, s) == validation.manques(s) for s in SECTIONS_VALIDEES
    )
    if inchangee:
        return None
    return replace(fiche, champs={**fiche.champs, CHAMP_VALIDATION: validation.json()})


def _relus(
    fiches: FichesImportRepository, tenant_id: TenantId, documents: Sequence[DocumentImport]
) -> list[DocumentImport]:
    """Un FEC ou un QIF lu avant AXE-973 n'a pas gardé ses mouvements : relu
    en mémoire, comme l'écran de la couverture bancaire."""
    relus = []
    for document in documents:
        donnees = document.donnees or {}
        avant = (donnees.get("type") == "fec" and "banque" not in donnees) or (
            donnees.get("type") == "qif" and "mouvements" not in donnees
        )
        if avant:
            _d, contenu = fiches.contenu(tenant_id, document.id)
            lu = traiter(document.categorie, document.nom_fichier, contenu)
            document = replace(document, donnees=lu.donnees or donnees)
        relus.append(document)
    return relus


def valider_portefeuille(engine: Engine, tenant_id: TenantId, maintenant: datetime) -> str:
    """Chaque fiche active reliée à un dossier : ses critères vérifiés et
    gardés. Le résumé pour le journal des tâches (« » si rien ne change)."""
    fiches = PostgresFichesImport(engine, depot_documents())
    comptes = PostgresCompteBancaireRepository(engine)
    ledger = PostgresLedgerService(engine)
    settlements = PostgresSettlements(engine)
    changees = importes = 0
    for fiche, documents in fiches.lister(tenant_id):
        if fiche.statut == "ignore" or fiche.annulee_le or not fiche.dossier_id:
            continue
        dossier = DossierId(fiche.dossier_id)
        validation = valider_fiche(
            fiche,
            _relus(fiches, tenant_id, documents),
            comptes.lister(dossier),
            ledger.grand_livre(dossier),
            settlements.lister(dossier),
            maintenant,
        )
        importes += validation.importe
        nouvelle = avec_validation(fiche, validation)
        if nouvelle is not None:
            fiches.enregistrer(nouvelle)
            changees += 1
    if not changees:
        return ""
    return f"critères d'import revus pour {changees} fiche(s), {importes} chauffeur(s) importé(s)"
