"""Détection des résidus qui ne doivent jamais sortir vers un LLM."""

from __future__ import annotations

import re
from collections.abc import Callable

from axelcompta.core.errors import DomaineError

# IBAN FR, e-mail, téléphone FR, carte (groupes de 4), plaque, NIR simplifié.
_RESIDUS = (
    re.compile(r"\bFR\d{2}(?:\s?\d){10,24}\b", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b"),
    re.compile(r"(?:\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}"),
    re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b"),
    re.compile(r"\b[A-Z]{2}-\d{3}-[A-Z]{2}\b"),
    re.compile(r"\b[12]\s?\d{2}\s?(?:0[1-9]|1[0-2])\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b"),
)
_GENRES = ("IBAN", "EMAIL", "TELEPHONE", "CARTE", "PLAQUE", "NIR")


class FuiteDetectee(DomaineError):
    """Un prompt contient encore un identifiant brut."""


def residus(texte: str) -> bool:
    return any(motif.search(texte) for motif in _RESIDUS)


def remplacer_residus(
    texte: str, jeton_pour: Callable[[str, str], str]
) -> tuple[str, tuple[str, ...]]:
    """Remplace chaque résidu. Retourne le texte et les valeurs brutes retirées."""
    trouves: list[str] = []
    rendu = texte
    for motif, genre in zip(_RESIDUS, _GENRES, strict=True):

        def _remplacer(trouve: re.Match[str], genre: str = genre) -> str:
            trouves.append(trouve.group(0))
            return jeton_pour(genre, trouve.group(0))

        rendu = motif.sub(_remplacer, rendu)
    return rendu, tuple(trouves)


def affirmer_sans_fuite(texte: str, secrets: tuple[str, ...]) -> None:
    if residus(texte):
        raise FuiteDetectee("identifiant brut encore présent")
    for secret in secrets:
        propre = secret.strip()
        if len(propre) >= 3 and propre.casefold() in texte.casefold():
            raise FuiteDetectee("partie connue encore présente")
