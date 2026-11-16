"""Tableau 2054-SD millésime 2026 (notice 2032-NOT-SD) : immobilisations.

Mouvements de l'exercice, par catégorie et au total : valeur brute au début
(journal AN), acquisitions (débits), cessions et mises hors service
(crédits), valeur à la fin. Pas de réévaluation ni de virement de poste à
poste dans les écritures : ces colonnes restent à zéro, et la valeur
d'origine en fin d'exercice égale la valeur brute de fin.

Les codes de case ont été relevés sur le formulaire officiel 2050-LIASSE
millésime 2026 (impots.gouv.fr, 2050-liasse_5320.pdf, page 5), avec leur
position dans la colonne. « Ø » s'écrit « 0 », comme partout ailleurs.
Pas de PDF (ADR-006).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .impot_societes import arrondir_euros
from .liasse_2033_annexes import Mouvements, immobilisations_2033c
from .rubriques_2033 import rubrique


@dataclass(frozen=True, slots=True)
class Ligne2054:
    """Codes d'une ligne. Cadre A : début, réévaluation, acquisitions.
    Cadre B : virement de poste à poste, cessions, fin, valeur d'origine."""

    debut: str
    reevaluation: str
    acquisitions: str
    virement: str
    cessions: str
    fin: str
    origine: str


FRAIS = Ligne2054("CZ", "D8", "D9", "IN", "C0", "D0", "D7")
INCORPORELLES = Ligne2054("KD", "KE", "KF", "IO", "LV", "LW", "1X")
TERRAINS = Ligne2054("KG", "KH", "KI", "IP", "LX", "LY", "LZ")
SOL_PROPRE = Ligne2054("KJ", "KK", "KL", "IQ", "MA", "MB", "MC")
SOL_AUTRUI = Ligne2054("KM", "KN", "KO", "IR", "MD", "ME", "MF")
AGENCEMENTS_CONSTRUCTIONS = Ligne2054("KP", "KQ", "KR", "IS", "MG", "MH", "MI")
MATERIEL_INDUSTRIEL = Ligne2054("KS", "KT", "KU", "IT", "MJ", "MK", "ML")
AGENCEMENTS_DIVERS = Ligne2054("KV", "KW", "KX", "IU", "MM", "MN", "MO")
TRANSPORT = Ligne2054("KY", "KZ", "LA", "IV", "MP", "MQ", "MR")
BUREAU = Ligne2054("LB", "LC", "LD", "IW", "MS", "MT", "MU")
DIVERS = Ligne2054("LE", "LF", "LG", "IX", "MV", "MW", "MX")
EN_COURS = Ligne2054("LH", "LI", "LJ", "MY", "MZ", "NA", "NB")
AVANCES = Ligne2054("LK", "LL", "LM", "NC", "ND", "NE", "NF")
PARTICIPATIONS = Ligne2054("8U", "8V", "8W", "I0", "0X", "0Y", "0Z")
AUTRES_TITRES = Ligne2054("1P", "1R", "1S", "I1", "2B", "2C", "2D")
PRETS = Ligne2054("1T", "1U", "1V", "I2", "2E", "2F", "2G")
TOTAL_CORPORELLES = Ligne2054("LN", "LO", "LP", "IY", "NG", "NH", "NI")
TOTAL_FINANCIERES = Ligne2054("LQ", "LR", "LS", "I3", "NJ", "NK", "2H")
TOTAL_GENERAL = Ligne2054("0G", "0H", "0J", "I4", "0K", "0L", "0M")

# Préfixe de compte (PCG) → ligne ; le plus long préfixe l'emporte.
COMPTES_2054: dict[str, Ligne2054] = {
    "201": FRAIS,
    "203": FRAIS,
    "20": INCORPORELLES,
    "211": TERRAINS,
    "212": TERRAINS,
    "213": SOL_PROPRE,
    "2135": AGENCEMENTS_CONSTRUCTIONS,
    "214": SOL_AUTRUI,
    "215": MATERIEL_INDUSTRIEL,
    "2181": AGENCEMENTS_DIVERS,
    "2182": TRANSPORT,
    "2183": BUREAU,
    "2184": BUREAU,
    "218": DIVERS,
    "21": DIVERS,
    "231": EN_COURS,
    "232": EN_COURS,
    "237": AVANCES,
    "238": AVANCES,
    "261": PARTICIPATIONS,
    "266": PARTICIPATIONS,
    "271": AUTRES_TITRES,
    "272": AUTRES_TITRES,
    "273": AUTRES_TITRES,
    "27": PRETS,
}
_PAR_CLE = {ligne.debut: ligne for ligne in COMPTES_2054.values()}
CORPORELLES = (
    TERRAINS,
    SOL_PROPRE,
    SOL_AUTRUI,
    AGENCEMENTS_CONSTRUCTIONS,
    MATERIEL_INDUSTRIEL,
    AGENCEMENTS_DIVERS,
    TRANSPORT,
    BUREAU,
    DIVERS,
    EN_COURS,
    AVANCES,
)
FINANCIERES = (PARTICIPATIONS, AUTRES_TITRES, PRETS)


def _ligne(debut: int, acquisitions: int, cessions: int, codes: Ligne2054) -> dict[str, int]:
    fin = debut + acquisitions - cessions
    return {
        codes.debut: debut,
        codes.reevaluation: 0,
        codes.acquisitions: acquisitions,
        codes.virement: 0,
        codes.cessions: cessions,
        codes.fin: fin,
        codes.origine: fin,
    }


def _par_ligne(mouvements: Mouvements) -> dict[str, tuple[int, int, int]]:
    """Par ligne (clé : code de début), centimes : début, acquisitions, cessions."""
    table = {prefixe: ligne.debut for prefixe, ligne in COMPTES_2054.items()}
    centimes: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    comptes = set(mouvements.ouverture) | set(mouvements.debits) | set(mouvements.credits)
    for compte in comptes:
        if not compte.startswith("2") or compte.startswith("28") or compte.startswith("29"):
            continue
        cle = rubrique(compte, table)
        if cle is None:
            continue
        cumul = centimes[cle]
        cumul[0] += mouvements.ouverture.get(compte, 0)
        cumul[1] += mouvements.debits.get(compte, 0)
        cumul[2] += mouvements.credits.get(compte, 0)
    return {cle: (v[0], v[1], v[2]) for cle, v in centimes.items()}


def immobilisations_2054(mouvements: Mouvements) -> dict[str, int]:
    """Cases en euros : une ligne par catégorie mouvementée, les totaux
    corporels (III), financiers (IV) et général. Vide sans immobilisation
    (tableau déposé « Néant »). Le total général reste celui de la 2033-C."""
    lignes_2033 = immobilisations_2033c(mouvements)
    if "496" not in lignes_2033 and "490" not in lignes_2033:
        return {}
    euros = {
        cle: tuple(arrondir_euros(v) for v in valeurs)
        for cle, valeurs in _par_ligne(mouvements).items()
    }
    cases: dict[str, int] = {}
    for cle, (debut, acquisitions, cessions) in euros.items():
        cases |= _ligne(debut, acquisitions, cessions, _PAR_CLE[cle])
    for total, groupe in ((TOTAL_CORPORELLES, CORPORELLES), (TOTAL_FINANCIERES, FINANCIERES)):
        presentes = [euros[g.debut] for g in groupe if g.debut in euros]
        if presentes:
            debut, acquisitions, cessions = (sum(v[i] for v in presentes) for i in range(3))
            cases |= _ligne(debut, acquisitions, cessions, total)
    cloture = lignes_2033.get("496", 0)
    cases |= {
        "0G": lignes_2033.get("490", 0),
        "0H": 0,
        "0J": lignes_2033.get("492", 0),
        "I4": 0,
        "0K": lignes_2033.get("494", 0),
        "0L": cloture,
        "0M": cloture,
    }
    return cases
