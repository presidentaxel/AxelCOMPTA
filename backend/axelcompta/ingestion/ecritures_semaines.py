"""Les écritures d'une semaine de plateforme soldée (AXE-924). Pur.

Une semaine soldée (`semaines_plateforme`) s'écrit en trois sortes d'OD,
toutes rattachées à la semaine par leur pièce (« uber:2026-11-02 ») :

* **recette du jour** : la créance sur la plateforme (un 467 par plateforme)
  pour ce qu'elle doit, la caisse (530) pour les espèces encaissées par le
  chauffeur, contre 706 HT, 44571, et la commission (6222, 44566) quand
  Rollee la donne. Pourboires, bonus et autres montants hors course vont en
  708, sans TVA (AXE-926) ;
* **solde par un virement** : la contrepartie du virement (471 ou 706, telle
  que les écrans la voient) contre la créance ; le virement lui-même et le
  512 ne bougent pas ;
* **frais de virement instantané** : 627 contre la créance.

Comptes du schéma de l'expert-comptable (AXE-931).

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

# AXE-931 : un compte de liaison par plateforme ; 467 pour une plateforme
# sans compte propre.
COMPTE_CREANCE = "467"
COMPTES_CREANCE = {
    "uber": "4671",
    "bolt": "4672",
    "heetch": "4673",
    "allocab": "4674",
    "freenow": "4675",
}
COMPTE_FRAIS = "627"
# AXE-926 : revenus de plateforme hors course (pourboires, bonus, autres) :
# dans le chiffre d'affaires (la liasse lit tout le 70), sans TVA. AXE-931 :
# 708, produits des activités annexes.
COMPTE_HORS_COURSE = "708"
# AXE-931 : les espèces encaissées par le chauffeur pour la société.
COMPTE_ESPECES = "530"
SUFFIXE_RECETTE = ":recette-plateforme"
SUFFIXE_SOLDE = ":solde-plateforme"
SUFFIXE_FRAIS = ":frais-plateforme"


def compte_creance(plateforme: str) -> str:
    return COMPTES_CREANCE.get(plateforme, COMPTE_CREANCE)


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
    lundi: date,
    tva_recettes_regime: str,
    hors_course_cts: int = 0,
) -> Ecriture:
    """La recette d'un jour : `construire_ecriture_settlement` (mêmes lignes
    706, TVA, commission) sur le brut sans ce qui n'est pas une course, la
    banque remplacée par la créance, le hors course en 708 sans TVA, et la
    part en espèces portée en caisse."""
    plafond = min(jour.net_payout_cts, jour.gross_earnings_cts)
    if hors_course_cts < 0 or (hors_course_cts and hors_course_cts > plafond):
        raise ValueError("pourboires, bonus ou autres montants illisibles")
    taxable = replace(
        jour,
        gross_earnings_cts=jour.gross_earnings_cts - hors_course_cts,
        net_payout_cts=jour.net_payout_cts - hors_course_cts,
    )
    transaction = NormalizedTransaction(
        id=TransactionId(settlement_id),
        dossier_id=jour.dossier_id,
        date=jour.period_start,
        montant_cts=taxable.net_payout_cts,
        libelle=f"{jour.platform} {jour.period_start.isoformat()}",
        source_provider="rollee",
        raw_payload={},
    )
    base = construire_ecriture_settlement(
        transaction,
        taxable,
        0,
        tva_recettes_regime=tva_recettes_regime,
        compte_banque=COMPTE_CREANCE,
    )
    # La créance porte tout le gagné, hors course compris.
    creance = compte_creance(jour.platform)
    lignes = [
        LigneEcriture(creance, Sens.DEBIT, Money(jour.net_payout_cts))
        if x.compte == COMPTE_CREANCE
        else x
        for x in base.lignes
    ]
    if hors_course_cts:
        lignes.append(LigneEcriture(COMPTE_HORS_COURSE, Sens.CREDIT, Money(hors_course_cts)))
    if especes_cts:
        lignes = _avec_especes(lignes, creance, jour.net_payout_cts, especes_cts)
    return replace(
        base,
        id=id_recette(settlement_id),
        journal=Journal.OD,
        libelle=f"Recette {jour.platform.capitalize()} du {jour.period_start:%d/%m/%Y}",
        reference_piece=piece_semaine(jour.platform, lundi),
        lignes=tuple(lignes),
    )


def _avec_especes(
    lignes: list[LigneEcriture], creance: str, gagne_cts: int, especes_cts: int
) -> list[LigneEcriture]:
    """La part payée en espèces quitte la créance pour la caisse."""
    rang = next(i for i, x in enumerate(lignes) if x.compte == creance)
    due = gagne_cts - especes_cts
    return [
        *lignes[:rang],
        *([LigneEcriture(creance, Sens.DEBIT, Money(due))] if due else []),
        LigneEcriture(COMPTE_ESPECES, Sens.DEBIT, Money(especes_cts)),
        *lignes[rang + 1 :],
    ]


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
            LigneEcriture(compte_creance(plateforme), Sens.CREDIT, Money(montant_cts)),
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
            LigneEcriture(compte_creance(plateforme), Sens.CREDIT, Money(frais_cts)),
        ),
    )
