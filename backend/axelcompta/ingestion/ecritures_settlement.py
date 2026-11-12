"""Génération d'écritures depuis un settlement réconcilié (doc 13 §5).

Templates de données par régime de commission (doc 13 §5.2) — pas une
branche de code : ajouter une plateforme = ajouter une entrée dans
`TEMPLATES_COMMISSION`, pas un `if`. Le taux de TVA sur les recettes
(doc 13 §5.1) est **configurable par dossier** via `tva_recettes_regime`
(doc 14 §1.2) — ajouté pour la démo à 3 chauffeurs (doc 17 §4 : Yanis est en
franchise, Karim et Sophie assujettis 10%), alors que la première version de
ce module (profil unique doc 17 §3) l'avait figé en dur à 10% assujetti.

Ne dépend pas de `ledger` pour ses règles de calcul : celles-ci sont pures
(`_ventiler`). Dépend de `ledger.models` uniquement pour construire l'objet
`Ecriture` — `ledger` lui-même ne dépend jamais d'`ingestion` en retour
(règle absolue, doc 03 §3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import EcritureId, TransactionId
from axelcompta.core.money import Money
from axelcompta.core.pcg import COMPTE_BANQUE
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

from .providers.base import NormalizedTransaction, PlatformSettlement

# doc 13 §5.1 : régimes possibles pour `tva_recettes_regime` (vocabulaire du
# CSV d'onboarding, doc 14 §1.2). `None` pour franchise : pas de taux, pas de
# TVA collectée du tout — le montant brut de la plateforme est déjà le net
# comptable, traité à part (`_lignes_franchise`).
TAUX_TVA_RECETTES_PAR_REGIME: dict[str, Decimal | None] = {
    "assujetti_taux_reduit": Decimal("0.10"),
    "franchise": None,
}


@dataclass(frozen=True, slots=True)
class TemplateCommissionTVA:
    """doc 13 §5.2 : la TVA sur commission dépend de l'entité facturante."""

    taux: Decimal
    autoliquidation: bool


TEMPLATES_COMMISSION = {
    "france_20": TemplateCommissionTVA(taux=Decimal("0.20"), autoliquidation=False),
    "autoliquidation_ue": TemplateCommissionTVA(taux=Decimal("0.20"), autoliquidation=True),
}


class RegimeTvaInconnu(DomaineError):
    """`commission_tva_regime` sans template (doc 13 §5.2), ou combinaison
    `tva_recettes_regime` × `commission_tva_regime` non couverte — erreur
    attendue : un nouveau régime s'ajoute en données, ne se devine jamais
    (doc 08 §5)."""


class RegimeTvaRecettesInconnu(DomaineError):
    """`tva_recettes_regime` sans entrée dans `TAUX_TVA_RECETTES_PAR_REGIME` —
    même logique que `RegimeTvaInconnu` côté recettes plutôt que commission."""


def _ventiler(montant_ttc_cts: int, taux: Decimal) -> tuple[int, int]:
    """(HT, TVA) tels que HT + TVA == montant_ttc_cts exactement — aucune
    perte au centime, tout l'arrondi porte sur la TVA."""
    ht = int(
        (Decimal(montant_ttc_cts) / (Decimal(1) + taux)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return ht, montant_ttc_cts - ht


def _lignes_commission(
    settlement: PlatformSettlement,
    template: TemplateCommissionTVA,
    recettes_ht: int,
    tva_collectee: int,
) -> list[LigneEcriture]:
    if template.autoliquidation:
        # déjà HT, pas de TVA facturée par la plateforme (Bolt, doc 13 §5.3)
        commission_ht = settlement.commission_cts
        tva_autoliq = int(
            (Decimal(commission_ht) * template.taux).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        return [
            LigneEcriture("622", Sens.DEBIT, Money(commission_ht)),
            LigneEcriture("44566", Sens.DEBIT, Money(tva_autoliq), code_tva="autoliquidation"),
            LigneEcriture("706", Sens.CREDIT, Money(recettes_ht)),
            LigneEcriture("44571", Sens.CREDIT, Money(tva_collectee)),
            LigneEcriture("44571", Sens.CREDIT, Money(tva_autoliq), code_tva="autoliquidation"),
        ]
    commission_ht, tva_commission = _ventiler(settlement.commission_cts, template.taux)
    return [
        LigneEcriture("622", Sens.DEBIT, Money(commission_ht)),
        LigneEcriture("44566", Sens.DEBIT, Money(tva_commission)),
        LigneEcriture("706", Sens.CREDIT, Money(recettes_ht)),
        LigneEcriture("44571", Sens.CREDIT, Money(tva_collectee)),
    ]


def _lignes_franchise(settlement: PlatformSettlement, compte_banque: str) -> list[LigneEcriture]:
    """doc 13 §5.3 « cas franchise » : pas de TVA collectée sur les recettes
    (le brut plateforme est déjà le montant comptable), commission plateforme
    non récupérable donc comptabilisée TTC intégralement (pas de ligne
    44566). Seul `france_20` est couvert ici (Uber) — combiner franchise avec
    une commission en autoliquidation UE (Bolt) pose une vraie question
    fiscale (l'obligation d'autoliquider une TVA due peut subsister malgré la
    franchise) volontairement laissée hors scope démo (doc 17 §3 : « pas de
    cas limites »), à trancher avec l'expert-comptable avant la V1.
    """
    if settlement.commission_tva_regime != "france_20":
        raise RegimeTvaInconnu(
            f"franchise + {settlement.commission_tva_regime} : combinaison non couverte, "
            "doc 17 §3 (pas de cas limites dans la démo)"
        )
    return [
        LigneEcriture(compte_banque, Sens.DEBIT, Money(settlement.net_payout_cts)),
        LigneEcriture("622", Sens.DEBIT, Money(settlement.commission_cts)),  # TTC, non récupérable
        LigneEcriture("706", Sens.CREDIT, Money(settlement.gross_earnings_cts)),  # pas de TVA
    ]


def construire_ecriture_settlement(
    transaction: NormalizedTransaction,
    settlement: PlatformSettlement,
    numero: int,
    *,
    tva_recettes_regime: str = "assujetti_taux_reduit",
    compte_banque: str = COMPTE_BANQUE,
) -> Ecriture:
    """doc 13 §5.3. Le montant du 512 est celui du settlement
    (`net_payout_cts`), pas celui de la transaction bancaire : les deux
    peuvent différer d'1 centime (tolérance de réconciliation, doc 13 §4.2)
    et seul le premier garantit l'équilibre avec les lignes dérivées.

    `tva_recettes_regime` est une configuration de dossier (doc 14 §1.2),
    jamais devinée depuis les données du settlement.

    `compte_banque` : sous-compte 512x du compte bancaire qui a reçu le
    virement (AXE-832), 512 par défaut.
    """
    if tva_recettes_regime not in TAUX_TVA_RECETTES_PAR_REGIME:
        raise RegimeTvaRecettesInconnu(tva_recettes_regime)

    if tva_recettes_regime == "franchise":
        lignes = _lignes_franchise(settlement, compte_banque)
    else:
        template = TEMPLATES_COMMISSION.get(settlement.commission_tva_regime)
        if template is None:
            raise RegimeTvaInconnu(settlement.commission_tva_regime)
        taux = TAUX_TVA_RECETTES_PAR_REGIME[tva_recettes_regime]
        assert taux is not None  # tous les régimes non-franchise ont un taux (garanti par le dict)
        recettes_ht, tva_collectee = _ventiler(settlement.gross_earnings_cts, taux)
        lignes = [
            LigneEcriture(compte_banque, Sens.DEBIT, Money(settlement.net_payout_cts)),
            *_lignes_commission(settlement, template, recettes_ht, tva_collectee),
        ]

    return Ecriture(
        id=EcritureId(f"settlement-{numero}"),
        dossier_id=transaction.dossier_id,
        journal=Journal.BQ,
        date=transaction.date,
        libelle=f"Règlement {settlement.platform} — {transaction.libelle}",
        reference_piece=None,
        lignes=tuple(lignes),
    )


# --- AXE-821 : ventiler un virement déjà passé en recette --------------------

SUFFIXE_VENTILATION = ":ventilation-plateforme"


class VirementNonVentilable(DomaineError):
    """Le virement ne porte pas exactement le versé du relevé sur le compte
    de recette : on ne ventile pas à l'aveugle."""


def id_ventilation_plateforme(ecriture_id: EcritureId) -> EcritureId:
    return EcritureId(f"{ecriture_id}{SUFFIXE_VENTILATION}")


def ecriture_de_ventilation(
    virement: Ecriture,
    settlement: PlatformSettlement,
    compte_recette: str,
    *,
    tva_recettes_regime: str,
    date_ecriture: date | None = None,
) -> Ecriture:
    """AXE-821. Le virement S (512 au débit, `compte_recette` au crédit pour
    le net) reste tel quel : le 512 ne bouge jamais. Une OD à côté reprend le
    net du compte de recette et pose le détail du relevé : recette brute HT,
    TVA collectée, commission et sa TVA (doc 13 §5.3). Mêmes lignes que
    `construire_ecriture_settlement`, la ligne de banque remplacée par le
    compte de recette. Aucune ligne au compte d'attente.

    Lève `VirementNonVentilable` si S ne crédite pas exactement le versé
    sur `compte_recette`."""
    credit = sum(
        ligne.montant.centimes
        for ligne in virement.lignes
        if ligne.compte == compte_recette and ligne.sens is Sens.CREDIT
    )
    if credit != settlement.net_payout_cts:
        raise VirementNonVentilable(
            f"{compte_recette} crédité de {credit} c, versé du relevé {settlement.net_payout_cts} c"
        )
    transaction = NormalizedTransaction(
        id=TransactionId(str(virement.id)),
        dossier_id=virement.dossier_id,
        date=virement.date,
        montant_cts=settlement.net_payout_cts,
        libelle=virement.libelle,
        source_provider=settlement.source_provider,
        raw_payload={},
    )
    detail = construire_ecriture_settlement(
        transaction,
        settlement,
        0,
        tva_recettes_regime=tva_recettes_regime,
        compte_banque=COMPTE_BANQUE,
    )
    lignes = tuple(
        LigneEcriture(compte_recette, Sens.DEBIT, ligne.montant)
        if ligne.compte == COMPTE_BANQUE
        else ligne
        for ligne in detail.lignes
    )
    periode = f"{settlement.period_start:%d/%m} au {settlement.period_end:%d/%m/%Y}"
    return Ecriture(
        id=id_ventilation_plateforme(virement.id),
        dossier_id=virement.dossier_id,
        journal=Journal.OD,
        date=date_ecriture or virement.date,
        libelle=f"Ventilation {settlement.platform} du {periode}",
        reference_piece=str(virement.id),
        lignes=lignes,
    )
