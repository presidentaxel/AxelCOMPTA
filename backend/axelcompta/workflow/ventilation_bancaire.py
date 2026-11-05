"""Reprise des écritures passées au 512 avant AXE-832.

Une écriture bancaire déjà validée ne se modifie pas (I2). Pour la porter
sur le sous-compte de son compte bancaire, on ajoute à côté une écriture de
reclassement (journal OD, même date, même montant) : 512x d'un côté, 512 de
l'autre. Le 512 de l'opération est soldé, le 512x porte le mouvement.

On ne contre-passe pas l'originale : la synchro lit une contre-passation
comme « transaction modifiée chez la banque » et la mettrait en quarantaine.

Rejouable : l'id du reclassement dérive de celui de l'écriture
(`{id}:ventilation-banque`), une écriture déjà ventilée est ignorée.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.pcg import COMPTE_BANQUE, est_compte_banque
from axelcompta.ingestion.comptes_bancaires import CompteBancaireRepository, compte_de
from axelcompta.ingestion.journal import JournalIngestion
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

SUFFIXE_VENTILATION = ":ventilation-banque"


def id_ventilation(ecriture_id: EcritureId) -> EcritureId:
    return EcritureId(f"{ecriture_id}{SUFFIXE_VENTILATION}")


def ecriture_de_ventilation(ecriture: Ecriture, sous_compte: str) -> Ecriture | None:
    """Reclassement 512 → `sous_compte` de l'écriture, ou `None` si elle n'a
    pas de ligne 512 ou si le sous-compte n'en est pas un."""
    if sous_compte == COMPTE_BANQUE or not est_compte_banque(sous_compte):
        return None
    ligne = next((x for x in ecriture.lignes if x.compte == COMPTE_BANQUE), None)
    if ligne is None:
        return None
    inverse = Sens.CREDIT if ligne.sens is Sens.DEBIT else Sens.DEBIT
    return Ecriture(
        id=id_ventilation(ecriture.id),
        dossier_id=ecriture.dossier_id,
        journal=Journal.OD,
        date=ecriture.date,
        libelle=f"Ventilation bancaire — {ecriture.libelle}",
        reference_piece=ecriture.id,
        lignes=(
            LigneEcriture(sous_compte, ligne.sens, ligne.montant),
            LigneEcriture(COMPTE_BANQUE, inverse, ligne.montant),
        ),
    )


def ventiler(
    ecritures: Iterable[Ecriture], sous_compte_de: Callable[[Ecriture], str | None]
) -> list[Ecriture]:
    """Reclassements à poser pour un dossier. Ignorés : les écritures déjà
    ventilées, les reclassements eux-mêmes, et les paires contre-passées (elles
    se neutralisent déjà au 512)."""
    toutes = list(ecritures)
    deja = {e.id for e in toutes}
    exclues = annulees(toutes)
    nouvelles: list[Ecriture] = []
    for ecriture in toutes:
        if ecriture.id in exclues or ecriture.id.endswith(SUFFIXE_VENTILATION):
            continue
        if id_ventilation(ecriture.id) in deja:
            continue
        sous_compte = sous_compte_de(ecriture)
        if sous_compte is None:
            continue
        reclassement = ecriture_de_ventilation(ecriture, sous_compte)
        if reclassement is not None:
            nouvelles.append(reclassement)
    return nouvelles


def ventilation_du_dossier(
    dossier_id: DossierId,
    ecritures: Iterable[Ecriture],
    journal: JournalIngestion,
    comptes: CompteBancaireRepository,
    source: str,
) -> list[Ecriture]:
    """Reclassements d'un dossier synchronisé : le compte bancaire de chaque
    écriture se lit dans l'archive brute (`account_id`), son sous-compte dans
    le registre (attribué s'il est nouveau). Écriture d'une autre source, ou
    transaction sans compte connu : laissée au 512."""
    prefixe = f"{dossier_id}:{source}-"
    par_transaction = journal.comptes_des_transactions(dossier_id, source)

    def sous_compte_de(ecriture: Ecriture) -> str | None:
        if not ecriture.id.startswith(prefixe):
            return None
        identifiant = par_transaction.get(ecriture.id.removeprefix(prefixe))
        return None if identifiant is None else compte_de(comptes, dossier_id, identifiant)

    return ventiler(ecritures, sous_compte_de)
