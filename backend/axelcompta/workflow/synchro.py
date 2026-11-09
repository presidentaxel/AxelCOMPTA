"""Synchronisation d'un dossier réel : lot du fournisseur -> archive brute ->
catégorisation -> écritures (doc 12 §1.2, doc 16 §9).

Ce que ça garantit, et qui n'était pas vrai du chemin de démo :

- **Idempotent.** L'id d'une écriture dérive de l'id de transaction du
  fournisseur (`{dossier}:{source}-{id}`), jamais d'un compteur : relancer la
  synchro, ou relire une fenêtre qui se recouvre, ne crée aucun doublon.
- **Reprise sûre.** Ordre : archive brute, proposition, écriture, puis
  curseur en dernier. Une interruption au milieu se rattrape au passage
  suivant ; au pire une proposition orpheline, sans effet.
- **Le ledger reste append-only** (doc 06 §1). Une transaction modifiée ou
  supprimée côté banque *après* avoir été comptabilisée n'est ni réécrite ni
  ignorée : elle est contre-passée (écriture inverse, journal OD) et
  signalée en quarantaine. L'originale ne change pas.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.pipeline import CategorizationPipeline
from axelcompta.core.ids import EcritureId
from axelcompta.core.pcg import COMPTE_BANQUE
from axelcompta.ingestion.comptes_bancaires import (
    CompteBancaireRepository,
    compte_de,
    comptes_ecartes,
)
from axelcompta.ingestion.journal import JournalIngestion
from axelcompta.ingestion.providers.base import LotTransactions, NormalizedTransaction
from axelcompta.ledger.banque import montant_bancaire
from axelcompta.ledger.contrepassation import contrepasser, id_contrepassation
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.periodes import Periode, periode_close_de
from axelcompta.ledger.service import LedgerService
from axelcompta.tenants.models import Dossier

from .auto_accept import construire_ecriture_categorisee
from .propositions import PropositionRepository
from .reclassement import annuler_reclassements

COMPTE_ATTENTE = "471"
# Motif de quarantaine montré au chauffeur : une opération bancaire datée dans
# un exercice déjà clos ne s'y écrit plus ; le gestionnaire la reprend.
MOTIF_PERIODE_CLOSE = (
    "periode_close : opération datée dans un exercice déjà clos, à reprendre par votre gestionnaire"
)

# Sans settlement plateforme réconcilié (Rollee, doc 13 §4), un virement Uber
# ou Bolt ne peut pas être comptabilisé en 706 : la ventilation TVA vient du
# relevé de la plateforme, pas de la banque. En attente, jamais en produit.
CATEGORIES_EN_ATTENTE_DE_SETTLEMENT = frozenset({"recettes_plateformes", "commissions_plateformes"})

# Seuils d'acceptation automatique. Tout ce qui est en dessous va au compte
# d'attente, donc dans la file de revue de l'indiv. Depuis le 2026-09-27, une
# proposition ML d'un modèle calibré porte son propre seuil, propre à sa
# catégorie (`ProposedEntry.seuil_imputation`) ; `SEUIL_ML` ne vaut plus que
# pour un modèle sans fichier de calibration.
SEUIL_REGLE = 0.75
SEUIL_ML = 0.90


class SourceTransactions(Protocol):
    async def lire_lot(self, dossier: Dossier, depuis_maj: datetime | None) -> LotTransactions: ...


@dataclass(frozen=True, slots=True)
class RapportSynchro:
    nouvelles: int
    a_trancher: int  # parmi les nouvelles, celles envoyées au compte d'attente
    deja_connues: int
    modifiees_signalees: int
    supprimees_signalees: int
    rejets: int
    curseur: datetime | None
    # Opérations datées dans un exercice clos, arrivées après la clôture :
    # en quarantaine, jamais au grand livre (I4, AXE-806).
    periode_close: int = 0
    # Opérations d'un compte écarté ou à décider (AXE-729) : ni écriture ni
    # question, gardées dans l'archive brute.
    compte_non_retenu: int = 0


def choisir_compte(proposition: ProposedEntry, comptes: dict[str, str]) -> str:
    """Compte d'imputation, ou 471 quand la proposition ne mérite pas de
    confiance sans regard humain."""
    if proposition.categorie in CATEGORIES_EN_ATTENTE_DE_SETTLEMENT:
        return COMPTE_ATTENTE
    if proposition.etage is Etage.REGLE:
        seuil = SEUIL_REGLE
    elif proposition.seuil_imputation is not None:
        seuil = proposition.seuil_imputation
    else:
        seuil = SEUIL_ML
    if proposition.etage not in (Etage.REGLE, Etage.ML) or proposition.confiance < seuil:
        return COMPTE_ATTENTE
    return comptes.get(proposition.categorie, COMPTE_ATTENTE)


def _signature(ecriture: Ecriture) -> tuple[int, object]:
    """(montant signé côté banque, date) : ce qui ne doit plus bouger une fois
    comptabilisé. Lu sur 512 ou sur un sous-compte 512x (AXE-832)."""
    return montant_bancaire(ecriture), ecriture.date


def _annuler(
    ledger: LedgerService,
    comptabilisees: dict[EcritureId, Ecriture],
    existante: Ecriture,
    dossier: Dossier,
) -> None:
    """Pose l'écriture inverse une seule fois. L'originale reste en place."""
    periodes = ledger.periodes_closes(existante.dossier_id)
    inverse = contrepasser(existante, periodes, dossier.exercice_debut)
    if inverse.id in comptabilisees:
        return
    ledger.enregistrer(inverse)
    comptabilisees[inverse.id] = inverse
    # AXE-420 : les reclassements des décisions sur cette opération aussi.
    for annulation in annuler_reclassements(
        existante.id, list(comptabilisees.values()), periodes, dossier.exercice_debut
    ):
        ledger.enregistrer(annulation)
        comptabilisees[annulation.id] = annulation


def id_ecriture(dossier: Dossier, source_nom: str, transaction_id: str) -> EcritureId:
    """L'écriture d'une opération bancaire : stable d'une synchro à l'autre."""
    return EcritureId(f"{dossier.id}:{source_nom}-{transaction_id}")


def _archiver_lot(
    dossier: Dossier, source_nom: str, journal: JournalIngestion, lot: LotTransactions
) -> None:
    for brute in lot.brutes:
        journal.archiver(
            dossier.id,
            source_nom,
            _texte_ou_none(brute.get("id")),
            _texte_ou_none(brute.get("updated_at")),
            brute,
        )
    for rejet in lot.rejets:
        journal.mettre_en_quarantaine(
            dossier.id, source_nom, f"ligne_illisible : {rejet.raison}", None, rejet.payload
        )


@dataclass(slots=True)
class _Compteurs:
    nouvelles: int = 0
    a_trancher: int = 0
    connues: int = 0
    non_retenues: int = 0
    modifiees: int = 0
    supprimees: int = 0
    periode_close: int = 0


def _traiter_transactions(
    dossier: Dossier,
    source_nom: str,
    lot: LotTransactions,
    comptabilisees: dict[EcritureId, Ecriture],
    journal: JournalIngestion,
    ledger: LedgerService,
    propositions: PropositionRepository,
    pipeline: CategorizationPipeline,
    comptes: dict[str, str],
    comptes_bancaires: CompteBancaireRepository | None,
) -> _Compteurs:
    compteurs = _Compteurs()
    periodes = ledger.periodes_closes(dossier.id)
    hors_retenus = _hors_comptes_retenus(
        dossier, source_nom, lot, comptabilisees, comptes_bancaires
    )
    par_transaction = _propositions_des_ouvertes(
        dossier, source_nom, lot, comptabilisees, periodes, pipeline, hors_retenus
    )
    for transaction in lot.transactions:
        ecriture_id = id_ecriture(dossier, source_nom, transaction.id)
        existante = comptabilisees.get(ecriture_id)
        if existante is not None:
            _relever_existante(
                dossier,
                source_nom,
                transaction,
                existante,
                ecriture_id,
                comptabilisees,
                journal,
                ledger,
                compteurs,
            )
            continue
        if transaction.id in hors_retenus:
            compteurs.non_retenues += 1
            continue
        if periode_close_de(transaction.date, periodes) is not None:
            compteurs.periode_close += 1
            journal.mettre_en_quarantaine(
                dossier.id, source_nom, MOTIF_PERIODE_CLOSE, transaction.id, transaction.raw_payload
            )
            continue
        proposition = par_transaction[transaction.id]
        compte = choisir_compte(proposition, comptes)
        banque = _banque(dossier, transaction, comptes_bancaires)
        ecriture = dataclasses.replace(
            construire_ecriture_categorisee(transaction, proposition, compte, 0, banque),
            id=ecriture_id,
        )
        propositions.enregistrer(
            ecriture_id,
            dataclasses.replace(proposition, moyen_paiement=transaction.type_operation),
        )
        ledger.enregistrer(ecriture)
        compteurs.nouvelles += 1
        compteurs.a_trancher += compte == COMPTE_ATTENTE
    return compteurs


def _banque(
    dossier: Dossier,
    transaction: NormalizedTransaction,
    comptes_bancaires: CompteBancaireRepository | None,
) -> str:
    if comptes_bancaires is None:
        return COMPTE_BANQUE
    return compte_de(comptes_bancaires, dossier.id, transaction.compte_bancaire)


def _hors_comptes_retenus(
    dossier: Dossier,
    source_nom: str,
    lot: LotTransactions,
    comptabilisees: dict[EcritureId, Ecriture],
    comptes_bancaires: CompteBancaireRepository | None,
) -> frozenset[str]:
    """AXE-729 : nouvelles opérations d'un compte écarté ou à décider. Un
    compte vu pour la première fois est enregistré ici, avant le tri."""
    if comptes_bancaires is None:
        return frozenset()
    nouvelles = [
        t
        for t in lot.transactions
        if t.compte_bancaire is not None
        and id_ecriture(dossier, source_nom, t.id) not in comptabilisees
    ]
    for identifiant in dict.fromkeys(t.compte_bancaire for t in nouvelles):
        compte_de(comptes_bancaires, dossier.id, identifiant)
    ecartes = comptes_ecartes(comptes_bancaires, dossier.id)
    return frozenset(t.id for t in nouvelles if t.compte_bancaire in ecartes)


def _propositions_des_ouvertes(
    dossier: Dossier,
    source_nom: str,
    lot: LotTransactions,
    comptabilisees: dict[EcritureId, Ecriture],
    periodes: tuple[Periode, ...],
    pipeline: CategorizationPipeline,
    hors_retenus: frozenset[str] = frozenset(),
) -> dict[str, ProposedEntry]:
    """Catégorisées ensemble : les deux jambes d'un virement interne ne se
    reconnaissent que côte à côte (AXE-826). Une opération datée dans un
    exercice clos n'entre pas dans le lot : elle part en quarantaine."""
    nouvelles = [
        t
        for t in lot.transactions
        if id_ecriture(dossier, source_nom, t.id) not in comptabilisees
        and periode_close_de(t.date, periodes) is None
        and t.id not in hors_retenus
    ]
    return {p.transaction_id: p for p in pipeline.categoriser_lot(dossier.id, nouvelles)}


def _relever_existante(
    dossier: Dossier,
    source_nom: str,
    transaction: NormalizedTransaction,
    existante: Ecriture,
    ecriture_id: EcritureId,
    comptabilisees: dict[EcritureId, Ecriture],
    journal: JournalIngestion,
    ledger: LedgerService,
    compteurs: _Compteurs,
) -> None:
    """Une fois contre-passée, l'originale ne compte plus : même revenue à
    l'identique, la ligne bancaire n'est plus comptabilisée et repart en
    quarantaine plutôt que de passer pour « déjà connue »."""
    deja_annulee = id_contrepassation(ecriture_id) in comptabilisees
    inchangee = _signature(existante) == (transaction.montant_cts, transaction.date)
    if inchangee and not deja_annulee:
        compteurs.connues += 1
        return
    compteurs.modifiees += 1
    _annuler(ledger, comptabilisees, existante, dossier)
    journal.mettre_en_quarantaine(
        dossier.id,
        source_nom,
        "modifiee_apres_comptabilisation",
        transaction.id,
        transaction.raw_payload,
    )


def _signaler_supprimees(
    dossier: Dossier,
    source_nom: str,
    lot: LotTransactions,
    comptabilisees: dict[EcritureId, Ecriture],
    journal: JournalIngestion,
    ledger: LedgerService,
) -> int:
    signalees = 0
    for transaction_id in lot.supprimees:
        existante = comptabilisees.get(id_ecriture(dossier, source_nom, transaction_id))
        if existante is None:
            continue
        signalees += 1
        _annuler(ledger, comptabilisees, existante, dossier)
        journal.mettre_en_quarantaine(
            dossier.id,
            source_nom,
            "supprimee_apres_comptabilisation",
            transaction_id,
            {"id": transaction_id},
        )
    return signalees


async def synchroniser_dossier(
    dossier: Dossier,
    source: SourceTransactions,
    source_nom: str,
    journal: JournalIngestion,
    ledger: LedgerService,
    propositions: PropositionRepository,
    pipeline: CategorizationPipeline,
    comptes_par_categorie: dict[str, str],
    comptes_bancaires: CompteBancaireRepository | None = None,
) -> RapportSynchro:
    """`comptes_bancaires` : registre des sous-comptes 512x (AXE-832). Sans
    lui, toute opération va au 512, comme avant."""
    # Un compte retenu après coup : on relit tout pour importer son passé.
    a_relire = comptes_bancaires is not None and any(
        c.a_relire for c in comptes_bancaires.lister(dossier.id)
    )
    curseur = None if a_relire else journal.curseur(dossier.id, source_nom)
    lot = await source.lire_lot(dossier, curseur)
    _archiver_lot(dossier, source_nom, journal, lot)
    comptabilisees = {e.id: e for e in ledger.grand_livre(dossier.id)}
    compteurs = _traiter_transactions(
        dossier,
        source_nom,
        lot,
        comptabilisees,
        journal,
        ledger,
        propositions,
        pipeline,
        comptes_par_categorie,
        comptes_bancaires,
    )
    supprimees = _signaler_supprimees(dossier, source_nom, lot, comptabilisees, journal, ledger)
    if a_relire and comptes_bancaires is not None:
        comptes_bancaires.relu(dossier.id)
    # Curseur en dernier : une interruption plus haut se rattrape au prochain passage.
    if lot.curseur is not None:
        journal.avancer_curseur(dossier.id, source_nom, lot.curseur)
    return RapportSynchro(
        nouvelles=compteurs.nouvelles,
        a_trancher=compteurs.a_trancher,
        deja_connues=compteurs.connues,
        modifiees_signalees=compteurs.modifiees,
        supprimees_signalees=supprimees,
        rejets=len(lot.rejets),
        curseur=lot.curseur,
        periode_close=compteurs.periode_close,
        compte_non_retenu=compteurs.non_retenues,
    )


def _texte_ou_none(valeur: object) -> str | None:
    return None if valeur is None else str(valeur)
