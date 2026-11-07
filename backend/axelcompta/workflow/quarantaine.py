"""Résoudre une entrée de quarantaine d'ingestion (AXE-424).

La synchro met en quarantaine ce qu'elle ne peut pas écrire seule :

* `modifiee_apres_comptabilisation` : l'opération a changé chez la banque
  après avoir été comptabilisée. La synchro l'a déjà contre-passée (avec ses
  reclassements, AXE-420). **Accepter** passe le nouveau montant, sur la
  catégorie que l'opération avait ; une correction précédente est d'abord
  contre-passée.
* `supprimee_apres_comptabilisation` : déjà contre-passée. Accepter en prend
  acte, sans écriture.
* `periode_close` : opération datée dans un exercice clos (AXE-806).
  Accepter la passe au premier jour de l'exercice ouvert.
* `ligne_illisible` : rien à passer, seulement « ignorer ».

**Ignorer** laisse le grand livre tel quel. Chaque résolution est gardée,
avec son auteur (`resolutions_quarantaine`). Pur : rien n'est lu ni écrit ici.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.journal import EntreeQuarantaine
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.banque import ligne_banque
from axelcompta.ledger.contrepassation import contrepasser, id_contrepassation
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import Periode, date_de_report

from .reclassement import annuler_reclassements, dernier_compte_choisi, reclasser_vers
from .revue import COMPTE_ATTENTE

Decision = Literal["accepter", "ignorer"]

MODIFIEE = "modifiee_apres_comptabilisation"
SUPPRIMEE = "supprimee_apres_comptabilisation"
PERIODE_CLOSE = "periode_close"
MARQUE_CORRECTION = ":corrige-"

LIBELLES_MOTIF = {
    MODIFIEE: "Montant ou date changé par la banque après comptabilisation",
    SUPPRIMEE: "Opération retirée par la banque après comptabilisation",
    PERIODE_CLOSE: "Opération datée dans un exercice déjà clos",
}


class ResolutionRefusee(DomaineError):
    """L'entrée ne se résout pas ainsi (ligne illisible acceptée, déjà résolue…)."""


def famille_du_motif(motif: str) -> str:
    """Le motif sans son détail (« ligne_illisible : date manquante »)."""
    return motif.split(" :", 1)[0]


def _corrections(origine_id: EcritureId, ecritures: Sequence[Ecriture]) -> list[Ecriture]:
    prefixe = f"{origine_id}{MARQUE_CORRECTION}"
    trouvees = [e for e in ecritures if e.id.startswith(prefixe) and e.id[len(prefixe) :].isdigit()]
    return sorted(trouvees, key=lambda e: int(e.id[len(prefixe) :]))


def _ecriture_corrigee(
    origine_id: EcritureId,
    rang: int,
    transaction: NormalizedTransaction,
    compte_banque: str,
    periodes_closes: Sequence[Periode],
) -> Ecriture:
    montant = Money(abs(transaction.montant_cts))
    sens_banque = Sens.DEBIT if transaction.montant_cts > 0 else Sens.CREDIT
    sens_attente = Sens.CREDIT if sens_banque is Sens.DEBIT else Sens.DEBIT
    return Ecriture(
        id=EcritureId(f"{origine_id}{MARQUE_CORRECTION}{rang}"),
        dossier_id=transaction.dossier_id,
        journal=Journal.BQ,
        date=date_de_report(transaction.date, periodes_closes),
        libelle=f"{transaction.libelle} (corrigée)",
        reference_piece=str(origine_id),
        lignes=(
            LigneEcriture(compte=compte_banque, sens=sens_banque, montant=montant),
            LigneEcriture(compte=COMPTE_ATTENTE, sens=sens_attente, montant=montant),
        ),
    )


def ecritures_de_resolution(
    entree: EntreeQuarantaine,
    decision: Decision,
    origine_id: EcritureId,
    ecritures: Sequence[Ecriture],
    normaliser: Callable[[dict[str, object], DossierId], NormalizedTransaction],
    periodes_closes: Sequence[Periode] = (),
) -> list[Ecriture]:
    """Les écritures à passer pour cette résolution, dans l'ordre. `origine_id` :
    l'écriture de l'opération bancaire (`synchro.id_ecriture`)."""
    famille = famille_du_motif(entree.motif)
    if decision == "ignorer" or famille == SUPPRIMEE:
        return []
    if famille not in (MODIFIEE, PERIODE_CLOSE):
        raise ResolutionRefusee("Cette ligne est illisible : elle ne peut qu'être ignorée.")
    vues = list(ecritures)
    a_ecrire: list[Ecriture] = []
    precedentes = _corrections(origine_id, vues)
    ids = {e.id for e in vues}
    for precedente in precedentes:
        if id_contrepassation(precedente.id) not in ids:
            a_ecrire.append(contrepasser(precedente, periodes_closes))
            a_ecrire.extend(annuler_reclassements(precedente.id, vues, periodes_closes))
    transaction = normaliser(entree.payload, entree.dossier_id)
    par_id = {e.id: e for e in vues}
    reference = precedentes[-1] if precedentes else par_id.get(origine_id)
    ligne = ligne_banque(reference) if reference is not None else None
    banque = ligne.compte if ligne is not None else "512"
    nouvelle = _ecriture_corrigee(
        origine_id, len(precedentes) + 1, transaction, banque, periodes_closes
    )
    a_ecrire.append(nouvelle)
    compte = dernier_compte_choisi(reference.id, vues) if reference is not None else None
    if compte is not None:
        vues.extend(a_ecrire)
        reclassement = reclasser_vers(nouvelle, compte, vues, periodes_closes)
        if reclassement is not None:
            a_ecrire.append(reclassement)
    return a_ecrire
