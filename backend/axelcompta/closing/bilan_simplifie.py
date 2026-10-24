"""Clôture simplifiée (doc 17 §3, semaine 3) : balance → compte de résultat
→ bilan → LiassePivot. Réduit au strict nécessaire pour le récit de démo —
pas de rapprochement bancaire, pas de dotations aux amortissements, pas de
cadrage TVA de clôture, pas de réintégrations fiscales (doc 06 §5, la
checklist complète, V1 seulement).

Le pipeline démo et la synchro Digifactory produisent, en plus des
classes 6 et 7 : `512` (banque), `44566`/`44571` (TVA), `1013` (capital
libéré, `demo_chauffeurs_type`) et `218` (immobilisation véhicule, mapping
du pack, volontairement pas ramené en charge). Tout autre compte (classe 3,
classe 4 hors TVA, classe 5 hors `512`) est nommé `COMPTES_NON_VENTILES` :
il n'a pas de ligne de bilan, mais il reste dans l'identité.

Identité, soldes signés débit positif :

`TRESORERIE + IMMOBILISATIONS + COMPTES_NON_VENTILES == RESULTAT + TVA_A_PAYER + CAPITAUX`
"""

from __future__ import annotations

from axelcompta.core.ids import DossierId
from axelcompta.core.pcg import nature_depuis_compte
from axelcompta.ledger.models import Ecriture, Sens
from axelcompta.ledger.service import LedgerService

from .cloture_fiscale import (
    cloturer_fiscalement,
    ecritures_de_cloture,
    ecritures_exercice,
    hors_inventaire,
)
from .models import LiassePivot, ParametresCloture
from .service import ClosingService


def _solde_par_compte(ecritures: tuple[Ecriture, ...]) -> dict[str, int]:
    balance: dict[str, int] = {}
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            signe = 1 if ligne.sens is Sens.DEBIT else -1
            balance[ligne.compte] = balance.get(ligne.compte, 0) + signe * ligne.montant.centimes
    return balance


def _ventiler(balance: dict[str, int]) -> dict[str, int]:
    """Postes du bilan simplifié, en centimes. `CAPITAUX` est créditeur
    positif (classe 1). `COMPTES_NON_VENTILES` garde le signe débit."""
    tresorerie = immobilisations = capitaux = non_ventiles = 0
    for compte, solde in balance.items():
        if compte == "512":
            tresorerie += solde
        elif compte in {"44566", "44571"} or compte.startswith(("6", "7")):
            continue
        elif compte.startswith("2"):
            immobilisations += solde
        elif compte.startswith("1"):
            capitaux += solde
        else:
            non_ventiles += solde
    return {
        "TRESORERIE": tresorerie,
        "IMMOBILISATIONS": immobilisations,
        "CAPITAUX": -capitaux,
        "COMPTES_NON_VENTILES": non_ventiles,
    }


def _compte_de_resultat(balance: dict[str, int]) -> tuple[int, int]:
    """(produits, charges) en centimes, toujours positifs — un solde de
    compte produit (classe 7) est créditeur donc négatif dans `balance`."""
    produits = sum(
        -solde for compte, solde in balance.items() if nature_depuis_compte(compte) == "produit"
    )
    charges = sum(
        solde for compte, solde in balance.items() if nature_depuis_compte(compte) == "charge"
    )
    return produits, charges


class ClotureSimplifieeService(ClosingService):
    """doc 17 §3, semaine 3 : compte de résultat + bilan simplifiés, une
    seule case fiscale (2065 = résultat comptable, aucune réintégration —
    hors scope démo)."""

    def __init__(self, ledger: LedgerService) -> None:
        self._ledger = ledger

    def ecritures_de_cloture(
        self, dossier_id: DossierId, parametres: ParametresCloture
    ) -> tuple[Ecriture, ...]:
        """Écritures d'inventaire (TVA, IS) à ajouter aux exports comptables
        (FEC, grand livre, balance) pour qu'ils concordent avec la liasse."""
        ecritures = ecritures_exercice(self._ledger.grand_livre(dossier_id), parametres)
        return ecritures_de_cloture(dossier_id, ecritures, parametres)

    def ecritures_exercice_completes(
        self, dossier_id: DossierId, parametres: ParametresCloture
    ) -> tuple[Ecriture, ...]:
        """Écritures de l'exercice (mêmes bornes que la liasse) suivies des
        écritures d'inventaire : ce que doivent contenir le FEC, le grand
        livre et la balance pour concorder avec la liasse au centime."""
        de_l_exercice = ecritures_exercice(self._ledger.grand_livre(dossier_id), parametres)
        ecritures = hors_inventaire(dossier_id, de_l_exercice, parametres)
        return ecritures + ecritures_de_cloture(dossier_id, ecritures, parametres)

    def cloturer(
        self, dossier_id: DossierId, exercice: str, parametres: ParametresCloture | None = None
    ) -> LiassePivot:
        """Avec `parametres` : clôture fiscale complète (écritures
        d'inventaire, liasse 2065 + 2033, `cloture_fiscale`). Sans : le
        compte de résultat et le bilan simplifiés d'origine (doc 17 §3)."""
        ecritures = self._ledger.grand_livre(dossier_id)
        if parametres is not None:
            return cloturer_fiscalement(dossier_id, exercice, ecritures, parametres)
        balance = _solde_par_compte(ecritures)
        produits, charges = _compte_de_resultat(balance)
        resultat = produits - charges
        # TVA nette due = collectée (44571, crédit) - déductible (44566, débit)
        tva_a_payer = -balance.get("44571", 0) - balance.get("44566", 0)
        dates = [ecriture.date for ecriture in ecritures]
        return LiassePivot(
            dossier_id=dossier_id,
            exercice=exercice,
            cases={
                "CA_HT": produits,
                "CHARGES": charges,
                "RESULTAT": resultat,
                "TVA_A_PAYER": tva_a_payer,
                **_ventiler(balance),
                "2065": resultat,  # case-clé du formulaire 2065 (doc 17 §3)
            },
            # Bornes réelles de l'exercice (doc 06 §7 : un exercice peut être
            # partiel, création en cours d'année) — pas une hypothèse année
            # civile qui serait fausse pour un dossier réel créé en cours
            # d'exercice.
            exercice_debut=min(dates) if dates else None,
            exercice_fin=max(dates) if dates else None,
        )
