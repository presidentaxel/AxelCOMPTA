"""Le choix Pro ou Perso d'une fiche d'import, porté aux comptes du dossier
(suite d'AXE-983). Pur.

La section Banque d'une fiche garde, pour chaque compte Digifactory, un
usage : `pro` ou `perso` (champ `comptes_bancaires`, en JSON ; ou les lignes
« Nom (retenu) » d'avant). Le dossier, lui, a ses comptes (`retenu` : vrai,
faux, ou `None` à décider), et seul ce choix-là compte pour la comptabilité.

Qui décide ne change pas (AXE-729, AXE-956) : le dirigeant, ou l'expert
habilité. Le choix de la fiche s'applique donc seul quand l'expert habilité
l'a fait ; sinon, c'est une proposition que le dirigeant ou l'expert
confirme. Un compte déjà décidé n'est jamais changé : un désaccord se voit.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from axelcompta.ingestion.comptes_bancaires import CompteBancaire

CHAMP_COMPTES = "comptes_bancaires"
_LIGNE = re.compile(r"^(.*?)\s*\((retenu|écarté|à choisir)\)\s*$")


@dataclass(frozen=True, slots=True)
class ChoixFiche:
    """Le choix d'un compte sur la fiche : `True` pro, `False` perso."""

    identifiant: str
    nom: str
    retenu: bool


def choix_de_la_fiche(champs: Mapping[str, str]) -> tuple[ChoixFiche, ...]:
    """Les comptes dont la fiche dit Pro ou Perso. Un compte sans choix est
    absent."""
    brut = (champs.get(CHAMP_COMPTES) or "").strip()
    if not brut:
        return ()
    try:
        lus = json.loads(brut)
    except ValueError:
        return tuple(_lignes(brut))
    if not isinstance(lus, list):
        return ()
    choix = []
    for ligne in lus:
        if not isinstance(ligne, dict):
            continue
        usage = ligne.get("usage")
        identifiant = str(ligne.get("id") or "").strip()
        if usage in ("pro", "perso") and identifiant:
            choix.append(
                ChoixFiche(identifiant, str(ligne.get("nom") or "").strip(), usage == "pro")
            )
    return tuple(choix)


def _lignes(brut: str) -> Iterable[ChoixFiche]:
    for ligne in brut.splitlines():
        lu = _LIGNE.match(ligne.strip())
        if lu and lu.group(2) != "à choisir" and lu.group(1).strip():
            nom = lu.group(1).strip()
            yield ChoixFiche("", nom, lu.group(2) == "retenu")


def proposition(compte: CompteBancaire, choix: Iterable[ChoixFiche]) -> bool | None:
    """Ce que la fiche dit de ce compte du dossier : par identifiant
    Digifactory, sinon par nom (anciennes lignes). `None` : rien."""
    choix = tuple(choix)
    for c in choix:
        if c.identifiant and c.identifiant == compte.identifiant:
            return c.retenu
    if compte.nom:
        for c in choix:
            if not c.identifiant and c.nom == compte.nom:
                return c.retenu
    return None


def a_appliquer(
    comptes: Iterable[CompteBancaire], choix: Iterable[ChoixFiche]
) -> tuple[tuple[str, bool], ...]:
    """Les comptes « à décider » du dossier que la fiche tranche :
    (sous-compte 512x, retenu). Un compte déjà décidé n'y est jamais."""
    choix = tuple(choix)
    return tuple(
        (compte.compte_comptable, retenu)
        for compte in comptes
        if compte.retenu is None and (retenu := proposition(compte, choix)) is not None
    )


def en_desaccord(comptes: Iterable[CompteBancaire], choix: Iterable[ChoixFiche]) -> tuple[str, ...]:
    """Les sous-comptes déjà décidés autrement que ne le dit la fiche."""
    choix = tuple(choix)
    return tuple(
        compte.compte_comptable
        for compte in comptes
        if compte.retenu is not None
        and (retenu := proposition(compte, choix)) is not None
        and retenu != compte.retenu
    )
