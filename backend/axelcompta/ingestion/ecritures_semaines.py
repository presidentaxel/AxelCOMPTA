"""Les écritures d'une semaine de plateforme soldée (AXE-924). Pur.

Une semaine soldée (`semaines_plateforme`) s'écrit en trois sortes d'OD,
toutes rattachées à la semaine par leur pièce (« uber:2026-11-02 ») :

* **recette du jour** : la créance sur la plateforme (467) pour ce qu'elle
  doit, le compte de l'associé (455, 108 en EI) pour les espèces gardées,
  contre 706 HT, 44571, et la commission (622, 44566) quand Rollee la donne ;
* **solde par un virement** : la contrepartie du virement (471 ou 706, telle
  que les écrans la voient) contre la créance ; le virement lui-même et le
  512 ne bougent pas ;
* **frais de virement instantané** : 627 contre la créance.

Une semaine soldée laisse donc la créance à zéro. Rejouer ne crée rien : les
identifiants dérivent du jour, du virement ou de la semaine.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from axelcompta.core.ids import DossierId, EcritureId, TransactionId
from axelcompta.core.money import Money
from axelcompta.ingestion.ecritures_settlement import construire_ecriture_settlement
from axelcompta.ingestion.providers.base import NormalizedTransaction, PlatformSettlement
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

COMPTE_CREANCE = "467"
COMPTE_FRAIS = "627"
SUFFIXE_RECETTE = ":recette-plateforme"
SUFFIXE_SOLDE = ":solde-plateforme"
SUFFIXE_FRAIS = ":frais-plateforme"


def piece_semaine(plateforme: str, lundi: date) -> str:
    return f"{plateforme}:{lundi.isoformat()}"


def id_recette(settlement_id: str) -> EcritureId:
    return EcritureId(f"{settlement_id}{SUFFIXE_RECETTE}")


def id_solde(virement_id: str) -> EcritureId:
    return EcritureId(f"{virement_id}{SUFFIXE_SOLDE}")


def id_frais(dossier_id: DossierId, plateforme: str, lundi: date) -> EcritureId:
    return EcritureId(f"{dossier_id}:{plateforme}:{lundi.isoformat()}{SUFFIXE_FRAIS}")


def ecriture_recette(
    settlement_id: str,
    jour: PlatformSettlement,
    especes_cts: int,
    compte_especes: str | None,
    lundi: date,
    tva_recettes_regime: str,
) -> Ecriture:
    """La recette d'un jour : `construire_ecriture_settlement` (mêmes lignes
    706, TVA, commission), la banque remplacée par la créance, et la part en
    espèces portée au compte de l'associé."""
    transaction = NormalizedTransaction(
        id=TransactionId(settlement_id),
        dossier_id=jour.dossier_id,
        date=jour.period_start,
        montant_cts=jour.net_payout_cts,
        libelle=f"{jour.platform} {jour.period_start.isoformat()}",
        source_provider="rollee",
        raw_payload={},
    )
    base = construire_ecriture_settlement(
        transaction,
        jour,
        0,
        tva_recettes_regime=tva_recettes_regime,
        compte_banque=COMPTE_CREANCE,
    )
    lignes = list(base.lignes)
    if especes_cts:
        if compte_especes is None:
            raise ValueError("espèces sans compte de l'associé")
        rang = next(i for i, x in enumerate(lignes) if x.compte == COMPTE_CREANCE)
        due = jour.net_payout_cts - especes_cts
        lignes[rang : rang + 1] = [
            *([LigneEcriture(COMPTE_CREANCE, Sens.DEBIT, Money(due))] if due else []),
            LigneEcriture(compte_especes, Sens.DEBIT, Money(especes_cts)),
        ]
    return replace(
        base,
        id=id_recette(settlement_id),
        journal=Journal.OD,
        libelle=f"Recette {jour.platform.capitalize()} du {jour.period_start:%d/%m/%Y}",
        reference_piece=piece_semaine(jour.platform, lundi),
        lignes=tuple(lignes),
    )


def ecriture_solde(
    virement: Ecriture, contrepartie: str, montant_cts: int, plateforme: str, lundi: date
) -> Ecriture:
    """Le virement solde la créance : sa contrepartie (471, 706) est vidée."""
    return Ecriture(
        id=id_solde(str(virement.id)),
        dossier_id=virement.dossier_id,
        journal=Journal.OD,
        date=virement.date,
        libelle=f"Versement {plateforme.capitalize()} : {virement.libelle}"[:200],
        reference_piece=piece_semaine(plateforme, lundi),
        lignes=(
            LigneEcriture(contrepartie, Sens.DEBIT, Money(montant_cts)),
            LigneEcriture(COMPTE_CREANCE, Sens.CREDIT, Money(montant_cts)),
        ),
    )


def ecriture_frais(
    dossier_id: DossierId, plateforme: str, lundi: date, le: date, frais_cts: int
) -> Ecriture:
    return Ecriture(
        id=id_frais(dossier_id, plateforme, lundi),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=le,
        libelle=f"Frais de virements instantanés {plateforme.capitalize()}",
        reference_piece=piece_semaine(plateforme, lundi),
        lignes=(
            LigneEcriture(COMPTE_FRAIS, Sens.DEBIT, Money(frais_cts)),
            LigneEcriture(COMPTE_CREANCE, Sens.CREDIT, Money(frais_cts)),
        ),
    )
