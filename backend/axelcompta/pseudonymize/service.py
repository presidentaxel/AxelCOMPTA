"""Remplace les parties connues et les identifiants par des jetons stables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from axelcompta.core.ids import DossierId

from .detecter import remplacer_residus
from .prompt import PseudonymizedPrompt


@dataclass(frozen=True, slots=True)
class PartieConnue:
    """Quelqu'un que le dossier connaît déjà : on ne laisse pas un modèle deviner."""

    texte: str
    genre: str  # "personne" ou "societe"


class Correspondance:
    """Jetons stables par dossier : `{PERSONNE_1}` désigne toujours la même personne."""

    def __init__(self) -> None:
        self._jetons: dict[tuple[str, str], str] = {}
        self._suite: dict[tuple[str, str], int] = {}

    def jeton(self, dossier_id: DossierId, genre: str, valeur: str) -> str:
        cle = (str(dossier_id), f"{genre}:{valeur.casefold()}")
        existant = self._jetons.get(cle)
        if existant is not None:
            return existant
        compteur = (str(dossier_id), genre)
        numero = self._suite.get(compteur, 0) + 1
        self._suite[compteur] = numero
        jeton = f"{{{genre}_{numero}}}"
        self._jetons[cle] = jeton
        return jeton


def pseudonymiser(
    dossier_id: DossierId,
    texte: str,
    parties: tuple[PartieConnue, ...],
    correspondance: Correspondance,
) -> PseudonymizedPrompt:
    """Seule porte d'entrée vers un prompt. Le résultat ne contient plus
    les parties connues ni les identifiants détectés."""
    rendu = texte
    secrets: list[str] = []
    for partie in sorted(parties, key=lambda p: len(p.texte), reverse=True):
        if len(partie.texte.strip()) < 3:
            continue
        genre = "SOCIETE" if partie.genre == "societe" else "PERSONNE"
        jeton = correspondance.jeton(dossier_id, genre, partie.texte)
        motif = re.compile(re.escape(partie.texte), re.IGNORECASE)
        if motif.search(rendu):
            secrets.append(partie.texte)
            rendu = motif.sub(jeton, rendu)
    rendu, bruts = remplacer_residus(
        rendu, lambda genre, valeur: correspondance.jeton(dossier_id, genre, valeur)
    )
    secrets.extend(bruts)
    return PseudonymizedPrompt(
        dossier_id=dossier_id, texte=rendu, secrets=tuple(dict.fromkeys(secrets))
    )
