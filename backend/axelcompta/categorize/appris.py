"""Propositions apprises des décisions de l'indiv sur son propre dossier.

Quand l'indiv a tranché une opération, les opérations semblables du même
dossier, dans le même sens (entrée ou sortie d'argent), reprennent sa
catégorie comme proposition. Ce n'est qu'une proposition : l'écriture reste
« à trancher » et l'indiv confirme d'un geste. Rien ne s'impute seul.

Ressemblance : cosinus entre n-grammes de caractères des libellés, chiffres
retirés (dates, références, numéros de semaine), plus proche voisin. Seuil
choisi sur le jeu d'audit (74 dossiers de chauffeurs) en simulant un indiv
qui tranche ses lignes dans l'ordre, chaque ligne comparée aux seules lignes
antérieures de son dossier : à 0,6, 81 % des lignes reçoivent une
proposition, juste dans 92 % des cas (2026-09-27). Réglé sur ce jeu
seulement, jamais sur les dossiers réels à qui on l'applique.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from axelcompta.core.libelles import sans_categorie

SEUIL_SIMILARITE = 0.6


@dataclass(frozen=True, slots=True)
class OperationTranchee:
    libelle: str
    montant_cts: int  # convention bancaire : positif = argent reçu
    categorie: str


@dataclass(frozen=True, slots=True)
class PropositionApprise:
    categorie: str
    similarite: float


def libelle_sans_categorie(libelle: str) -> str:
    """Les anciennes écritures portent la catégorie en suffixe (AXE-848) :
    à retirer avant de comparer."""
    return sans_categorie(libelle)


def normaliser(libelle: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", libelle).encode("ascii", "ignore").decode()
    lettres = re.sub(r"[^a-z ]", " ", re.sub(r"\d+", " ", sans_accent.lower()))
    return " ".join(lettres.split())


def propositions_apprises(
    tranchees: Sequence[OperationTranchee],
    a_proposer: Sequence[tuple[str, int]],
    seuil: float = SEUIL_SIMILARITE,
) -> list[PropositionApprise | None]:
    """Une proposition (ou `None`) par `(libelle, montant_cts)` de
    `a_proposer`, dans le même ordre."""
    if not tranchees or not a_proposer:
        return [None] * len(a_proposer)
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    textes = [normaliser(t.libelle) or "_" for t in tranchees]
    textes += [normaliser(libelle) or "_" for libelle, _ in a_proposer]
    matrice = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)).fit_transform(textes)
    connues, requetes = matrice[: len(tranchees)], matrice[len(tranchees) :]
    similarites = (requetes @ connues.T).toarray()
    sens_connus = np.array([t.montant_cts > 0 for t in tranchees])
    sens_requetes = np.array([montant > 0 for _, montant in a_proposer])
    # Un voisin de sens contraire ne compte pas : une entrée d'argent ne
    # reprend jamais la catégorie d'une sortie.
    similarites[sens_requetes[:, None] != sens_connus[None, :]] = -1.0
    meilleurs = similarites.argmax(axis=1)
    resultat: list[PropositionApprise | None] = []
    for ligne, indice in zip(similarites, meilleurs, strict=True):
        similarite = float(ligne[indice])
        resultat.append(
            PropositionApprise(tranchees[indice].categorie, similarite)
            if similarite >= seuil
            else None
        )
    return resultat
