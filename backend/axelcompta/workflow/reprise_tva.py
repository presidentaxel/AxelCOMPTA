"""Reprise des opérations imputées TTC avant AXE-831.

Jusqu'ici, une dépense allait tout entière au compte de sa catégorie, sans
TVA déductible. La reprise n'efface rien (append-only, I2) :

* opération tranchée par une décision (montant au 471, puis reclassé) : un
  nouveau reclassement, de l'imputation TTC vers l'imputation avec TVA ;
* opération imputée directement par la synchro : une OD `{S}:tva-1` qui
  déplace la TVA récupérable du compte vers 44566. Elle est annulée avec S
  si S est un jour contre-passée.

Une opération d'un exercice clos est reprise au premier jour de l'exercice
ouvert (I4), comme toute correction. Pur : rien n'est lu ni écrit ici.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from axelcompta.core.ids import EcritureId
from axelcompta.core.pcg import est_compte_tva_deductible
from axelcompta.ledger.banque import comptes_hors_banque, ligne_banque
from axelcompta.ledger.contrepassation import id_contrepassation, origine
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.periodes import Periode
from axelcompta.packs.tva_deductible import regle_tva

from .reclassement import (
    complement_tva,
    complements_tva_actifs,
    est_od_repliee,
    imputation_en_vigueur,
    reclasser,
)
from .revue import COMPTE_ATTENTE, CategorieInconnueError


def _operation_bancaire(ecriture: Ecriture, ids: set[EcritureId]) -> bool:
    return (
        origine(ecriture.id) is None
        and not est_od_repliee(ecriture.id)
        and id_contrepassation(ecriture.id) not in ids
        and ligne_banque(ecriture) is not None
    )


def _complement(
    source: Ecriture,
    categorie: str,
    regime_tva: str,
    vues: Sequence[Ecriture],
    periodes_closes: Sequence[Periode],
) -> Ecriture | None:
    """Opération imputée directement : un seul compte, pas encore de TVA."""
    autres = comptes_hors_banque(source)
    if len(autres) != 1 or any(est_compte_tva_deductible(x.compte) for x in source.lignes):
        return None
    if complements_tva_actifs(source.id, vues):
        return None
    regle = regle_tva(categorie, source.date, regime_tva)
    if regle is None:
        return None
    return complement_tva(source, autres[0], regle, periodes_closes)


def reprises_tva(
    ecritures: Sequence[Ecriture],
    categories: Mapping[EcritureId, str],
    comptes: tuple[dict[str, str | None], dict[str, str]],
    regime_tva: str,
    periodes_closes: Sequence[Periode] = (),
) -> list[Ecriture]:
    """Les OD à écrire pour un dossier. `categories` : la catégorie retenue de
    chaque opération (dernière décision humaine, sinon la proposition).
    Idempotent : une opération déjà reprise ne produit plus rien."""
    vues = list(ecritures)
    ids = {e.id for e in vues}
    a_ecrire: list[Ecriture] = []
    for source in ecritures:
        categorie = categories.get(source.id)
        if not categorie or not _operation_bancaire(source, ids):
            continue
        if any(ligne.compte == COMPTE_ATTENTE for ligne in source.lignes):
            # Seulement une opération déjà tranchée : une opération encore au
            # 471 attend sa décision, la reprise ne l'impute pas à sa place.
            en_vigueur = imputation_en_vigueur(source, vues)
            if en_vigueur is None or en_vigueur[0].compte == COMPTE_ATTENTE:
                continue
            try:
                od = reclasser(source, categorie, vues, comptes, periodes_closes, regime_tva)
            except CategorieInconnueError:
                continue
        else:
            od = _complement(source, categorie, regime_tva, vues, periodes_closes)
        if od is not None:
            vues.append(od)
            a_ecrire.append(od)
    return a_ecrire
