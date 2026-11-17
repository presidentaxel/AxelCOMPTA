"""Tableau 2058-C-SD millésime 2026 : affectation du résultat et
renseignements divers (notice 2032-NOT-SD).

L'affectation déclarée est celle du résultat de l'exercice précédent,
décidée pendant l'exercice (AXE-452). Elle se lit dans l'écriture
d'affectation passée dans l'exercice (`…:affectation-<année>`) :

* origines : report à nouveau du bilan précédent (ØC), résultat de
  l'exercice précédent (ØD), prélèvements sur les réserves (ØE), total ØF ;
* affectations : réserve légale (ZB), autres réserves (ZD), dividendes
  (ZE), autres répartitions (ZF), nouveau report à nouveau (ZG), total ZH.

Le total I égale le total II par construction : ZG est le report à nouveau
qui reste.

Renseignements divers : la LOA (AXE-803) est un crédit-bail mobilier.
YQ : engagements restants à la clôture (loyers et levée d'option). J7, le
prix de revient des biens, n'est pas servi : il n'est pas saisi.

Codes relevés sur le formulaire officiel 2050-LIASSE millésime 2026
(page 12). « Ø » s'écrit « 0 ». Euros entiers.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from axelcompta.ledger.models import Ecriture, Sens

from .impot_societes import arrondir_euros
from .liasse_2033_annexes import Mouvements
from .loa import ContratLoa, engagement_restant

_REPORT = ("110", "119")


def _net_credit(ecriture: Ecriture, prefixes: tuple[str, ...]) -> int:
    """Crédits moins débits des comptes `prefixes`, en centimes."""
    return sum(
        (x.montant.centimes if x.sens is Sens.CREDIT else -x.montant.centimes)
        for x in ecriture.lignes
        if x.compte.startswith(prefixes)
    )


def affectation_2058c(ecritures: Sequence[Ecriture], mouvements: Mouvements) -> dict[str, int]:
    """Vide si aucune affectation n'a été passée dans l'exercice."""
    affectations = [e for e in ecritures if ":affectation-" in str(e.id)]
    if not affectations:
        return {}
    report_avant = -sum(v for c, v in mouvements.ouverture.items() if c.startswith(_REPORT))
    # 120 débité : bénéfice, positif ; 129 crédité : perte, négative.
    resultat = -sum(_net_credit(e, ("120", "129")) for e in affectations)
    reserves = [_net_credit(e, ("106",)) for e in affectations]
    prelevements = -sum(v for v in reserves if v < 0)
    legale = sum(max(_net_credit(e, ("1061",)), 0) for e in affectations)
    autres = sum(max(_net_credit(e, ("1062", "1063", "1064", "1068")), 0) for e in affectations)
    dividendes = sum(_net_credit(e, ("457",)) for e in affectations)
    origines = [arrondir_euros(v) for v in (report_avant, resultat, prelevements)]
    affecte = [arrondir_euros(v) for v in (legale, autres, dividendes)]
    report_apres = sum(origines) - sum(affecte)
    return {
        "0C": origines[0],
        "0D": origines[1],
        "0E": origines[2],
        "0F": sum(origines),
        "ZB": affecte[0],
        "ZD": affecte[1],
        "ZE": affecte[2],
        "ZF": 0,
        "ZG": report_apres,
        "ZH": sum(origines),
    }


def credit_bail_2058c(contrats: Sequence[ContratLoa], cloture: date) -> dict[str, int]:
    """YQ : loyers restant dus et levée d'option à la clôture. J7 (prix de
    revient des biens) n'est pas servi : le prix du véhicule n'est pas
    saisi, et la somme des loyers n'en est pas un."""
    if not contrats:
        return {}
    return {"YQ": arrondir_euros(sum(engagement_restant(c, cloture) for c in contrats))}
