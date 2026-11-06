"""Résolution d'une écriture « à trancher » par une décision humaine (doc 17
§9 bloc C). Prend une écriture déjà posée sur le compte d'attente (471,
doc 06 §2) et la catégorie choisie par l'humain, produit l'écriture réelle
correspondante — montants et sens de chaque ligne inchangés, seul le compte
de contrepartie change. Une reclassification, jamais un nouveau calcul.
"""

from __future__ import annotations

import dataclasses

from axelcompta.core.errors import DomaineError
from axelcompta.ledger.contrepassation import origine
from axelcompta.ledger.models import Ecriture

from .decisions import CATEGORIE_ANNULATION, DecisionHumaine

COMPTE_ATTENTE = "471"
CATEGORIE_USAGE_PERSONNEL = "usage_personnel"
CATEGORIE_REMUNERATION = "remuneration_dirigeant"
# Pourquoi une catégorie de statut n'a pas de compte (doc 06 §7).
_SANS_COMPTE = {
    CATEGORIE_USAGE_PERSONNEL: (
        "Pour cette forme de société, l'usage personnel est signalé sans écriture."
    ),
    "compte_courant_associe": (
        "Pour cette forme de société, il n'y a pas d'apport ou de remboursement d'associé."
    ),
    CATEGORIE_REMUNERATION: (
        "Pour cette forme de société, la rémunération dépend de la situation du gérant "
        "(majoritaire ou non). Elle reste à préciser."
    ),
    "cotisations_dirigeant": (
        "Pour cette forme de société, les cotisations dépendent de la situation du gérant "
        "(majoritaire ou non). Elles restent à préciser."
    ),
    "prelevement_source_paie": "Seul un président assimilé salarié a un bulletin de paie.",
    "dividendes": "À l'impôt sur le revenu, il n'y a pas de dividendes.",
    "impots_dividendes": "À l'impôt sur le revenu, il n'y a pas de dividendes.",
}


class CategorieInconnueError(DomaineError, ValueError):
    """La catégorie choisie n'a ni compte dans le pack ni traitement spécial
    connu — pas de repli silencieux (doc 08 §2.7)."""


def resoudre_ecriture_a_trancher(
    ecriture: Ecriture,
    categorie_choisie: str,
    comptes_statut: dict[str, str | None],
    comptes_par_categorie: dict[str, str],
) -> Ecriture:
    """Remplace le compte d'attente par le compte réel correspondant à la
    décision humaine. Lève `CategorieInconnueError` plutôt que de deviner un
    compte — une décision qu'on ne sait pas traduire est un bug à corriger,
    pas un cas à masquer.

    `comptes_statut` : les catégories dont le compte vient de la matrice des
    statuts et non du pack (`ConfigurationDossier.comptes_categories_statut`,
    doc 06 §3.6, §7) : usage personnel (455, 108, ou signalé sans écriture)
    et rémunération du dirigeant (641, 644, 108, ou à préciser)."""
    cible = compte_cible(categorie_choisie, comptes_statut, comptes_par_categorie)
    lignes = tuple(
        dataclasses.replace(ligne, compte=cible) if ligne.compte == COMPTE_ATTENTE else ligne
        for ligne in ecriture.lignes
    )
    return dataclasses.replace(ecriture, lignes=lignes)


def compte_cible(
    categorie_choisie: str,
    comptes_statut: dict[str, str | None],
    comptes_par_categorie: dict[str, str],
) -> str:
    if categorie_choisie in comptes_statut:
        compte_statut = comptes_statut[categorie_choisie]
        if compte_statut is None:
            raise CategorieInconnueError(_SANS_COMPTE[categorie_choisie])
        return compte_statut
    compte = comptes_par_categorie.get(categorie_choisie)
    if compte is None:
        raise CategorieInconnueError(
            "Cette réponse ne correspond à aucune catégorie connue pour cette société."
        )
    return compte


def appliquer_decisions(
    ecritures: tuple[Ecriture, ...],
    decisions: tuple[DecisionHumaine, ...],
    comptes_statut: dict[str, str | None],
    comptes_par_categorie: dict[str, str],
) -> tuple[Ecriture, ...]:
    """Le grand livre tel que les décisions humaines le disent : chaque
    écriture tranchée prend son compte réel, les autres restent telles
    quelles. Les écritures en base ne changent jamais (append-only, doc 06
    §1) : la décision est une couche lue par-dessus. La dernière décision
    d'une écriture l'emporte, et une contre-passation suit celle de son
    originale, sinon son 471 resterait ouvert."""
    dernieres = {decision.ecriture_id: decision for decision in decisions}
    resultat = []
    for ecriture in ecritures:
        decision = dernieres.get(origine(ecriture.id) or ecriture.id)
        if decision is not None and decision.categorie != CATEGORIE_ANNULATION:
            ecriture = resoudre_ecriture_a_trancher(
                ecriture, decision.categorie, comptes_statut, comptes_par_categorie
            )
        resultat.append(ecriture)
    return tuple(resultat)
