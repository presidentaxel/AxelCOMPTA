"""Affectation du résultat d'un exercice clos (doc 06 §5) : réserve légale,
dividendes, report à nouveau.

Louis, 2026-09-26 : le chauffeur doit pouvoir faire quelque chose de son
résultat, et c'est lui qui choisit. On lui propose des scénarios chiffrés,
du plus au moins de dividendes, avec leur coût fiscal et ce qu'il reste en
trésorerie ; il décide seul (écran à lui, décision de l'associé unique).

Pur : ni base ni API. Les taux vivent dans `fiscalite_dividendes.toml`.
Ce qui n'est pas calculé est dit, pas deviné : les cotisations sociales
d'un gérant non salarié sur la part de dividendes au-delà du seuil.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

CHEMIN_FISCALITE = Path(__file__).with_name("fiscalite_dividendes.toml")
# Réserve légale (C. com. art. L232-10) : 5 % du bénéfice diminué des pertes
# antérieures, jusqu'à ce qu'elle atteigne 10 % du capital.
TAUX_RESERVE_LEGALE = Decimal("0.05")
PLAFOND_RESERVE_LEGALE = Decimal("0.10")
# Scénario prudent : garder en trésorerie trois mois de charges courantes.
MOIS_DE_COUSSIN = 3


@dataclass(frozen=True, slots=True)
class FiscaliteDividendes:
    pfu_impot_revenu: Decimal
    prelevements_sociaux: Decimal
    seuil_tns_capital: Decimal
    csg: Decimal = Decimal(0)
    crds: Decimal = Decimal(0)
    solidarite: Decimal = Decimal(0)


class MillesimeDividendesInconnu(LookupError):
    pass


@cache
def _fiscalites(chemin: Path = CHEMIN_FISCALITE) -> dict[int, FiscaliteDividendes]:
    with chemin.open("rb") as fichier:
        brut = tomllib.load(fichier)
    return {
        int(annee): FiscaliteDividendes(
            pfu_impot_revenu=Decimal(v["pfu_impot_revenu_pct"]) / 100,
            prelevements_sociaux=Decimal(v["prelevements_sociaux_pct"]) / 100,
            seuil_tns_capital=Decimal(v["seuil_tns_capital_pct"]) / 100,
            csg=Decimal(v["csg_pct"]) / 100,
            crds=Decimal(v["crds_pct"]) / 100,
            solidarite=Decimal(v["solidarite_pct"]) / 100,
        )
        for annee, v in brut["annees"].items()
    }


def fiscalite(annee_versement: int) -> FiscaliteDividendes:
    connues = _fiscalites()
    if annee_versement not in connues:
        raise MillesimeDividendesInconnu(
            f"Les taux des dividendes sont inconnus pour {annee_versement}."
        )
    return connues[annee_versement]


@dataclass(frozen=True, slots=True)
class SituationAffectation:
    """En centimes. `report_a_nouveau` : créditeur positif, débiteur négatif.
    `dettes` : ce que la trésorerie doit encore payer (IS, TVA, dividendes
    déjà décidés). `gerant_non_salarie` : gérant majoritaire d'EURL ou de
    SARL, dont une part des dividendes supporte des cotisations sociales."""

    resultat: int
    capital: int
    reserve_legale: int
    report_a_nouveau: int
    tresorerie: int
    dettes: int
    charges_mensuelles: int
    gerant_non_salarie: bool
    annee_versement: int


@dataclass(frozen=True, slots=True)
class Scenario:
    cle: str
    libelle: str
    dividendes: int
    impot_revenu: int
    prelevements_sociaux: int
    part_soumise_cotisations: int  # non chiffrée : dite, pas devinée
    net_percu: int
    laisse_en_societe: int
    tresorerie_apres: int


def _arrondi(montant: Decimal) -> int:
    return int(montant.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pertes_anterieures(situation: SituationAffectation) -> int:
    return max(0, -situation.report_a_nouveau)


def dotation_reserve_legale(situation: SituationAffectation) -> int:
    base = situation.resultat - pertes_anterieures(situation)
    if base <= 0:
        return 0
    manque = _arrondi(situation.capital * PLAFOND_RESERVE_LEGALE) - situation.reserve_legale
    return max(0, min(_arrondi(base * TAUX_RESERVE_LEGALE), manque))


def distribuable(situation: SituationAffectation) -> int:
    """Bénéfice distribuable (C. com. art. L232-11) : résultat, moins les
    pertes antérieures et la réserve légale, plus le report créditeur."""
    if situation.resultat <= 0:
        return max(0, situation.report_a_nouveau + min(0, situation.resultat))
    reste = situation.resultat - pertes_anterieures(situation) - dotation_reserve_legale(situation)
    return max(0, reste + max(0, situation.report_a_nouveau))


def disponible(situation: SituationAffectation) -> int:
    """Trésorerie qu'on peut sortir sans laisser de dette impayée."""
    return max(0, situation.tresorerie - situation.dettes)


def chiffrer(situation: SituationAffectation, cle: str, libelle: str, dividendes: int) -> Scenario:
    taux = fiscalite(situation.annee_versement)
    part_cotisations = 0
    if situation.gerant_non_salarie:
        seuil = _arrondi(situation.capital * taux.seuil_tns_capital)
        part_cotisations = max(0, dividendes - seuil)
    sous_pfu = dividendes - part_cotisations
    impot = _arrondi(dividendes * taux.pfu_impot_revenu)
    sociaux = _arrondi(sous_pfu * taux.prelevements_sociaux)
    return Scenario(
        cle=cle,
        libelle=libelle,
        dividendes=dividendes,
        impot_revenu=impot,
        prelevements_sociaux=sociaux,
        part_soumise_cotisations=part_cotisations,
        net_percu=dividendes - impot - sociaux,
        laisse_en_societe=situation.resultat - dotation_reserve_legale(situation) - dividendes,
        tresorerie_apres=situation.tresorerie - dividendes,
    )


def scenarios(situation: SituationAffectation) -> list[Scenario]:
    """Du moins au plus de dividendes, jamais au-delà de ce qui est à la fois
    distribuable et disponible en trésorerie. Le choix reste au chauffeur."""
    plafond = min(distribuable(situation), disponible(situation))
    coussin = MOIS_DE_COUSSIN * situation.charges_mensuelles
    prudent = min(plafond, max(0, disponible(situation) - coussin))
    return [
        chiffrer(situation, "garder", "Tout garder dans la société", 0),
        chiffrer(situation, "prudent", "Prudent : garder trois mois de charges", prudent),
        chiffrer(situation, "moitie", "La moitié du possible", plafond // 2),
        chiffrer(situation, "maximum", "Le maximum possible", plafond),
    ]


def id_affectation(dossier_id: DossierId, annee_exercice: int) -> EcritureId:
    return EcritureId(f"{dossier_id}:affectation-{annee_exercice}")


def ecriture_affectation(
    dossier_id: DossierId,
    annee_exercice: int,
    le: date,
    situation: SituationAffectation,
    dividendes: int,
) -> Ecriture:
    """Solde le résultat (120 ou 129) : apurement des pertes antérieures
    (119), réserve légale (1061), dividendes à payer (457), le reste en
    report à nouveau (110, ou prélevé dessus si les dividendes dépassent le
    résultat de l'exercice)."""
    if dividendes < 0 or dividendes > min(distribuable(situation), disponible(situation)):
        raise ValueError("dividendes hors de ce qui est distribuable et disponible")
    lignes: list[LigneEcriture] = []
    resultat = situation.resultat
    if resultat < 0:
        lignes += [_l("119", Sens.DEBIT, -resultat), _l("129", Sens.CREDIT, -resultat)]
        if dividendes:
            lignes += [_l("110", Sens.DEBIT, dividendes), _l("457", Sens.CREDIT, dividendes)]
    else:
        apurement = min(pertes_anterieures(situation), resultat)
        dotation = dotation_reserve_legale(situation)
        reste = resultat - apurement - dotation - dividendes
        lignes.append(_l("120", Sens.DEBIT, resultat))
        lignes += [_l("119", Sens.CREDIT, apurement)] if apurement else []
        lignes += [_l("1061", Sens.CREDIT, dotation)] if dotation else []
        lignes += [_l("457", Sens.CREDIT, dividendes)] if dividendes else []
        if reste:
            lignes.append(_l("110", Sens.CREDIT if reste > 0 else Sens.DEBIT, abs(reste)))
    return Ecriture(
        id=id_affectation(dossier_id, annee_exercice),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=le,
        libelle=f"Affectation du résultat de l'exercice {annee_exercice}",
        reference_piece=f"AFFECTATION-{annee_exercice}",
        lignes=tuple(lignes),
    )


def _l(compte: str, sens: Sens, montant: int) -> LigneEcriture:
    return LigneEcriture(compte=compte, sens=sens, montant=Money(montant))
