"""Clôture fiscale complète d'un exercice au régime simplifié d'imposition
(IS, ou IR sans écriture d'IS ni 2065 quand `soumis_is` est faux) :
écritures d'inventaire, puis liasse 2065 + 2033-A à E, toutes les
cases dans une seule `LiassePivot` (doc 02 §5 : un pivot, plusieurs
renderers — PDF CERFA aujourd'hui, EDI-TDFC plus tard).

Ordre imposé par le calcul :
1. liquidation de la TVA (n'affecte pas le résultat) ;
2. résultat fiscal **hors IS** → IS dû (le résultat fiscal ne dépend pas de
   l'IS : il est déduit en 306 puis réintégré en 324, effet nul) ;
3. écriture d'IS, puis tous les tableaux sur la balance définitive.

Clés des cases : `2033A.084`, `2033B.310`... en centimes d'euros entiers
(le formulaire ne porte pas de centimes), plus les cases historiques
(`CA_HT`, `RESULTAT`...) pour le tableau de bord.
"""

from __future__ import annotations

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId
from axelcompta.ledger.models import Ecriture, Sens

from .ca3 import declaration_ca3
from .controles_tdfc import controler_liasse
from .ecritures_cloture import (
    ecriture_impot_societes,
    ecriture_liquidation_tva,
    id_cloture_is,
    id_cloture_tva,
)
from .impot_societes import arrondir_euros, calculer_is
from .liasse_2033 import Balance, bilan, compte_de_resultat, net_actif, resultat_fiscal
from .liasse_2033_annexes import (
    Mouvements,
    immobilisations_2033c,
    mouvements,
    releve_2033d,
    valeur_ajoutee_2033e,
)
from .liasse_2050 import bilan_2050
from .liasse_2052 import compte_2052
from .liasse_2054 import immobilisations_2054
from .liasse_2055 import amortissements_2055
from .liasse_2056 import provisions_2056
from .liasse_2058 import deficits_2058, resultat_2058
from .models import LiassePivot, ParametresCloture
from .provisions import ecritures_provisions, prefixe_provisions


def soldes(ecritures: tuple[Ecriture, ...]) -> Balance:
    balance: Balance = {}
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            signe = 1 if ligne.sens is Sens.DEBIT else -1
            balance[ligne.compte] = balance.get(ligne.compte, 0) + signe * ligne.montant.centimes
    return balance


def chiffre_affaires_ht(ecritures: tuple[Ecriture, ...], annee: int) -> int:
    """Recettes hors taxe (706) de l'année civile, en centimes : l'assiette
    des seuils de la franchise en base de TVA (plafonds civils)."""
    return sum(
        ligne.montant.centimes if ligne.sens is Sens.CREDIT else -ligne.montant.centimes
        for ecriture in ecritures
        if ecriture.date.year == annee
        for ligne in ecriture.lignes
        if ligne.compte.startswith("706")
    )


def ecritures_exercice(
    ecritures: tuple[Ecriture, ...], parametres: ParametresCloture
) -> tuple[Ecriture, ...]:
    return tuple(
        e for e in ecritures if parametres.exercice_debut <= e.date <= parametres.exercice_fin
    )


def hors_inventaire(
    dossier_id: DossierId, ecritures: tuple[Ecriture, ...], parametres: ParametresCloture
) -> tuple[Ecriture, ...]:
    """Les écritures de l'exercice sans ses écritures d'inventaire. Une fois
    l'exercice clos, celles-ci sont en base (`axelcompta.exercices`) ; on
    les recalcule toujours depuis le reste, à l'identique (identifiants et
    montants stables), plutôt que de les compter deux fois ou de fausser
    les soldes « avant inventaire » (TVA de la 2033-D)."""
    annee = parametres.exercice_fin.year
    exclues = {id_cloture_tva(dossier_id, annee), id_cloture_is(dossier_id, annee)}
    prefixe = prefixe_provisions(dossier_id, annee)
    return tuple(e for e in ecritures if e.id not in exclues and not e.id.startswith(prefixe))


def ecritures_de_cloture(
    dossier_id: DossierId, ecritures: tuple[Ecriture, ...], parametres: ParametresCloture
) -> tuple[Ecriture, ...]:
    """Provisions saisies, puis TVA, puis IS. `ecritures` : celles de l'exercice."""
    ecritures = hors_inventaire(dossier_id, ecritures, parametres)
    fin = parametres.exercice_fin
    provisions = ecritures_provisions(dossier_id, parametres.provisions, fin)
    avant_tva = ecritures + provisions
    tva = ecriture_liquidation_tva(dossier_id, soldes(avant_tva), fin)
    avec_tva = avant_tva + ((tva,) if tva else ())
    if not parametres.soumis_is:
        return provisions + ((tva,) if tva else ())
    balance = soldes(avec_tva)
    fiscal = resultat_fiscal(compte_de_resultat(balance), balance, parametres.deficits_anterieurs)
    impot = calculer_is(fiscal["370"], parametres.exercice_debut, fin).impot
    ecriture_is = ecriture_impot_societes(dossier_id, impot, fin)
    return provisions + tuple(e for e in (tva, ecriture_is) if e is not None)


def _prefixer(tableau: str, lignes: dict[str, int]) -> dict[str, int]:
    """Euros → centimes (entiers), clé `2033B.310`."""
    return {f"{tableau}.{code}": euros * 100 for code, euros in lignes.items()}


def _cases_2065(fiscal: dict[str, int], parametres: ParametresCloture) -> dict[str, int]:
    calcul = calculer_is(fiscal["370"], parametres.exercice_debut, parametres.exercice_fin)
    return {
        "BENEFICE_TAUX_REDUIT": calcul.base_taux_reduit,
        "BENEFICE_TAUX_NORMAL": calcul.base_taux_normal,
        "DEFICIT": fiscal["372"],
        "IMPOT": calcul.impot,
    }


def _cases_historiques(balance: Balance, balance_avant: Balance) -> dict[str, int]:
    """Cases du tableau de bord, en centimes exacts (pas arrondies à l'euro)."""
    produits = -sum(s for c, s in balance.items() if c.startswith("7"))
    charges = sum(s for c, s in balance.items() if c.startswith("6"))
    tva = -sum(s for c, s in balance_avant.items() if c.startswith("445"))
    return {
        "CA_HT": produits,
        "CHARGES": charges,
        "RESULTAT": produits - charges,
        "TRESORERIE": balance.get("512", 0),
        "TVA_A_PAYER": tva,
    }


def _liasse_reel_normal(
    balance: Balance,
    balance_avant: Balance,
    resultat: dict[str, int],
    m: Mouvements,
    fiscal: dict[str, int],
    parametres: ParametresCloture,
) -> dict[str, int]:
    """Annexes 2050 à 2058-B dont les totaux sont ceux de la 2033."""
    exploitation, suite = compte_2052(balance)
    immos = immobilisations_2033c(m)
    releve = releve_2033d(balance_avant, m, fiscal, parametres.deficits_anterieurs)
    return (
        _prefixer("2050", bilan_2050(balance, resultat["310"]))
        | _prefixer("2052", exploitation)
        | _prefixer("2053", suite)
        | _prefixer("2054", immobilisations_2054(m))
        | _prefixer("2055", amortissements_2055(immos))
        | _prefixer("2056", provisions_2056(m))
        | _prefixer("2058A", resultat_2058(fiscal))
        | _prefixer("2058B", deficits_2058(releve))
    )


def cloturer_fiscalement(
    dossier_id: DossierId,
    exercice: str,
    ecritures: tuple[Ecriture, ...],
    parametres: ParametresCloture,
) -> LiassePivot:
    ecritures = hors_inventaire(dossier_id, ecritures_exercice(ecritures, parametres), parametres)
    completes = ecritures + ecritures_de_cloture(dossier_id, ecritures, parametres)
    balance_avant, balance = soldes(ecritures), soldes(completes)
    resultat = compte_de_resultat(balance)
    fiscal = resultat_fiscal(resultat, balance, parametres.deficits_anterieurs)
    actif_passif = bilan(balance, resultat["310"])
    m = mouvements(completes)
    cases = _cases_historiques(balance, balance_avant)
    # Clé historique du tableau de bord : le résultat fiscal, quel que soit
    # l'impôt. Les cases du formulaire 2065 n'existent qu'à l'IS.
    cases["2065"] = (fiscal["370"] - fiscal["372"]) * 100
    salaires = {"SALAIRES": arrondir_euros(balance.get("641", 0))}
    if parametres.soumis_is:
        cases |= _prefixer("2065", _cases_2065(fiscal, parametres))
        cases |= _prefixer("2065J", salaires)
    else:
        # 2031 cadre C.1 : bénéfice (370) ou déficit (372) de la 2033-B.
        cases |= _prefixer("2031", {"BENEFICE": fiscal["370"], "DEFICIT": fiscal["372"]})
        cases |= _prefixer("2031H", salaires)
    cases |= _prefixer("2033A", actif_passif)
    cases |= _prefixer("2033A.NET", net_actif(actif_passif))
    cases |= _prefixer("2033B", resultat | fiscal)
    cases |= _prefixer("2033C", immobilisations_2033c(m))
    cases |= _prefixer(
        "2033D", releve_2033d(balance_avant, m, fiscal, parametres.deficits_anterieurs)
    )
    cases |= _prefixer("2033E", valeur_ajoutee_2033e(balance, parametres.effectif_moyen))
    cases |= {f"CA3.{cle}": montant for cle, montant in declaration_ca3(balance_avant).items()}
    if parametres.regime_liasse == "2050":
        cases |= _liasse_reel_normal(balance, balance_avant, resultat, m, fiscal, parametres)
    elif parametres.regime_liasse != "2033":
        raise DomaineError(f"régime de liasse inconnu : {parametres.regime_liasse}")
    liasse = LiassePivot(
        dossier_id=dossier_id,
        exercice=exercice,
        cases=cases,
        exercice_debut=parametres.exercice_debut,
        exercice_fin=parametres.exercice_fin,
        identite=parametres.identite,
        forme_juridique=parametres.forme_juridique,
        soumis_is=parametres.soumis_is,
        associes=parametres.associes,
    )
    controler_liasse(liasse)
    return liasse
