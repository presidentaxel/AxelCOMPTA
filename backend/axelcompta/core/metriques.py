"""Compteurs et jauges exposés au format Prometheus (doc 15).

Pas d'I/O : le registre est en mémoire, le texte est rendu par l'API.
Les noms suivent le document, avec des underscores à la place des points.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _Serie:
    nom: str
    labels: tuple[tuple[str, str], ...]
    valeur: float


class Registre:
    def __init__(self) -> None:
        self._series: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    def incrementer(self, nom: str, valeur: float = 1, **labels: str) -> None:
        cle = (nom, tuple(sorted(labels.items())))
        self._series[cle] = self._series.get(cle, 0) + valeur

    def jauger(self, nom: str, valeur: float, **labels: str) -> None:
        self._series[(nom, tuple(sorted(labels.items())))] = valeur

    def texte(self) -> str:
        lignes = [
            _ligne(_Serie(nom, labels, valeur))
            for (nom, labels), valeur in sorted(self._series.items())
        ]
        return "\n".join(lignes) + ("\n" if lignes else "")


def _ligne(serie: _Serie) -> str:
    if not serie.labels:
        return f"{serie.nom} {serie.valeur}"
    etiquettes = ",".join(f'{nom}="{valeur}"' for nom, valeur in serie.labels)
    return f"{serie.nom}{{{etiquettes}}} {serie.valeur}"


METRIQUES = Registre()
