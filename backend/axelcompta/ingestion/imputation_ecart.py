"""Imputer l'écart d'une semaine de plateforme (AXE-969). Pur.

Une semaine écrite telle quelle (AXE-912) laisse son écart sur la créance de
la plateforme (467x) : recette des jours au débit, virements et frais au
crédit. L'expert-comptable l'impute en un clic sur le compte qu'il choisit,
par une OD qui solde la créance de cette semaine et garde son motif :

* **encore dû** (la créance reste débitrice) : 658 (petit écart de
  règlement), 455 (versé sur un compte de l'associé), un 512x (versé sur un
  autre compte du dossier) ;
* **versé en trop** (la créance est créditrice) : 758, 706 ou 7068/708
  (recette absente de Rollee : pourboire, bonus), 455, un 512x.

L'écart est lu dans le grand livre : les écritures de la semaine portent la
pièce `plateforme:lundi` (`piece_semaine`). Rejouer n'écrit rien de plus :
l'identifiant dérive de la semaine, et un écart soldé vaut 0.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.ecritures_semaines import compte_creance, piece_semaine
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

SUFFIXE_IMPUTATION = ":imputation-ecart"

# Le compte d'imputation et le sens d'écart qu'il accepte.
COMPTES_ENCORE_DU = ("658", "455")
COMPTES_TROP_VERSE = ("758", "706", "7068", "708", "455")
LIBELLES_COMPTES = {
    "658": "Charges diverses de gestion courante (petit écart de règlement)",
    "758": "Produits divers de gestion courante (petit écart de règlement)",
    "455": "Compte courant d'associé (versé sur un compte non relié)",
    "706": "Prestations de services (recette absente de Rollee)",
    "7068": "Revenus de plateforme hors course, sans TVA",
    "708": "Produits des activités annexes (pourboire, bonus)",
}


def id_imputation(dossier_id: DossierId, plateforme: str, lundi: date) -> EcritureId:
    return EcritureId(f"{dossier_id}:{plateforme}:{lundi.isoformat()}{SUFFIXE_IMPUTATION}")


def ecart_de_la_semaine(grand_livre: Sequence[Ecriture], plateforme: str, lundi: date) -> int:
    """Solde de la créance de la plateforme porté par les écritures de la
    semaine. Positif : encore dû par la plateforme ; négatif : versé en trop."""
    piece = piece_semaine(plateforme, lundi)
    creance = compte_creance(plateforme)
    exclues = annulees(grand_livre)
    solde = 0
    for ecriture in grand_livre:
        if ecriture.reference_piece != piece or ecriture.id in exclues:
            continue
        for ligne in ecriture.lignes:
            if ligne.compte == creance:
                signe = 1 if ligne.sens is Sens.DEBIT else -1
                solde += signe * ligne.montant.centimes
    return solde


def verifier_compte(compte: str, ecart_cts: int) -> None:
    """Le compte choisi doit convenir au sens de l'écart."""
    if compte.startswith("512") and compte != "512":
        return
    acceptes = COMPTES_ENCORE_DU if ecart_cts > 0 else COMPTES_TROP_VERSE
    if compte not in acceptes:
        sens = "encore dû" if ecart_cts > 0 else "versé en trop"
        permis = ", ".join((*acceptes, "512x"))
        raise SaisieInvalide(f"Pour un écart {sens}, imputez sur : {permis}.")


def ecriture_imputation(
    grand_livre: Sequence[Ecriture],
    dossier_id: DossierId,
    plateforme: str,
    lundi: date,
    compte: str,
    motif: str,
    le: date,
) -> Ecriture | None:
    """L'OD qui solde l'écart de la semaine sur `compte`. `None` si la
    semaine n'a plus d'écart (déjà imputée, ou tombée juste)."""
    ecart = ecart_de_la_semaine(grand_livre, plateforme, lundi)
    if ecart == 0:
        return None
    verifier_compte(compte, ecart)
    creance = compte_creance(plateforme)
    montant = Money(abs(ecart))
    sens_creance = Sens.CREDIT if ecart > 0 else Sens.DEBIT
    sens_compte = Sens.DEBIT if ecart > 0 else Sens.CREDIT
    return Ecriture(
        id=id_imputation(dossier_id, plateforme, lundi),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=le,
        libelle=f"Écart {plateforme.capitalize()} du {lundi:%d/%m/%Y} : {motif}"[:200],
        reference_piece=piece_semaine(plateforme, lundi),
        lignes=(
            LigneEcriture(compte, sens_compte, montant),
            LigneEcriture(creance, sens_creance, montant),
        ),
    )
