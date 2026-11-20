"""Reprendre les opérations restées au 471 avec le pipeline actuel (AXE-850).

Le 05/11, la synchro a tourné sans modèle : presque tout est parti au 471,
et la synchro ne recatégorise pas une opération déjà importée. Cette reprise
repasse chaque opération bancaire encore au compte d'attente (sans décision,
sans reclassement, ni annulée, ni soldée par une semaine Rollee, ni virement
interne) dans le pipeline, et applique **la même règle qu'une synchro
neuve** (`choisir_compte`) : au-dessus du seuil, l'OD de reclassement
d'AXE-420 (le 512 ne bouge pas) ; en dessous, rien. Pur.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from axelcompta.categorize.models import ProposedEntry
from axelcompta.categorize.pipeline import CategorizationPipeline
from axelcompta.core.ids import DossierId, EcritureId, TransactionId
from axelcompta.ingestion.ecritures_semaines import id_solde
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.banque import ligne_banque, montant_bancaire
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.periodes import Periode

from .reclassement import reclasser, sources_reclassees
from .revue import COMPTE_ATTENTE, CategorieInconnueError
from .synchro import choisir_compte
from .virement_interne import sources_en_virement_interne


@dataclass(frozen=True, slots=True)
class Reprise:
    candidates: int
    reclassements: tuple[Ecriture, ...]


def candidates(ecritures: Sequence[Ecriture], decidees: Collection[EcritureId]) -> list[Ecriture]:
    """Les opérations bancaires encore au 471 que personne n'a touchées."""
    ids = {e.id for e in ecritures}
    exclues = (
        set(decidees)
        | annulees(ecritures)
        | sources_reclassees(ecritures)
        | sources_en_virement_interne(ecritures)
    )
    return [
        e
        for e in ecritures
        if e.id not in exclues
        and id_solde(str(e.id)) not in ids
        and ligne_banque(e) is not None
        and any(ligne.compte.startswith(COMPTE_ATTENTE) for ligne in e.lignes)
    ]


def _transaction(
    dossier_id: DossierId, ecriture: Ecriture, moyen: str | None
) -> NormalizedTransaction:
    # shortcut: rebâtie depuis l'écriture (libellé, montant, date, moyen de
    # paiement) ; la catégorie Bridge n'y est plus. Relire l'archive brute
    # si l'écart de catégorisation se voit.
    return NormalizedTransaction(
        id=TransactionId(str(ecriture.id)),
        dossier_id=dossier_id,
        date=ecriture.date,
        montant_cts=montant_bancaire(ecriture),
        libelle=ecriture.libelle,
        source_provider="reprise_attente",
        raw_payload={},
        type_operation=moyen,
    )


def reprendre(
    dossier_id: DossierId,
    ecritures: Sequence[Ecriture],
    decidees: Collection[EcritureId],
    moyens: Mapping[EcritureId, str],
    pipeline: CategorizationPipeline,
    comptes: tuple[dict[str, str | None], dict[str, str]],
    periodes_closes: Sequence[Periode] = (),
    regime_tva: str | None = None,
) -> Reprise:
    """Les OD de reclassement à écrire. Rejouable : une opération reclassée
    n'est plus candidate."""
    a_reprendre = candidates(ecritures, decidees)
    propositions: list[ProposedEntry] = pipeline.categoriser_lot(
        dossier_id, [_transaction(dossier_id, e, moyens.get(e.id)) for e in a_reprendre]
    )
    _statut, par_categorie = comptes
    ods = []
    for source, proposition in zip(a_reprendre, propositions, strict=True):
        if choisir_compte(proposition, par_categorie) == COMPTE_ATTENTE:
            continue
        try:
            od = reclasser(
                source, proposition.categorie, ecritures, comptes, periodes_closes, regime_tva
            )
        except CategorieInconnueError:
            continue  # pas de compte pour ce statut : la synchro l'aurait laissée au 471
        if od is not None:
            ods.append(od)
    return Reprise(len(a_reprendre), tuple(ods))
