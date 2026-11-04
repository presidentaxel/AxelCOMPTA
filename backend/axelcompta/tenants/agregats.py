"""Agrégats d'un dossier pour la vue portefeuille (doc 19 §2.1), gardés en base.

La page Entreprises affichait ces valeurs en reconstruisant chaque dossier
(grand livre, décisions, liasse). On les calcule une fois et on les garde ;
elles ne se recalculent que pour le dossier dont une donnée a changé.

Seules les valeurs qui coûtent sont gardées : les montants de la liasse,
l'exercice et l'alerte de franchise de TVA. Le statut d'invitation, les
preuves de l'exercice et la date du jour changent sans écriture dans nos
tables : ils sont lus à l'affichage, et l'étape de frise en est déduite.

Qui périme une ligne : en Postgres, des triggers (migration `e7b3d9a15c42`),
donc toute écriture, d'où qu'elle vienne. Les montants restent des entiers
en centimes, et aucun détail d'écriture n'est gardé ici (doc 19 §2.4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from axelcompta.core.ids import DossierId, TenantId

# À monter quand le calcul change sans qu'aucune écriture n'ait lieu : une
# formule de la liasse, la matrice des statuts, les seuils de franchise ou
# le pack métier. Les lignes calculées avec une autre version sont ignorées
# et recalculées au fil des lectures.
VERSION_CALCUL = 1


@dataclass(frozen=True, slots=True)
class AgregatStocke:
    ca_ht_cts: int
    charges_cts: int
    resultat_cts: int
    exercice_debut: str | None  # ISO, comme `DossierResume`
    exercice_fin: str | None
    alerte_tva: str | None


@dataclass(frozen=True, slots=True)
class LigneAgregat:
    """Ce que la base garde d'un dossier. `valeur` est `None` quand la ligne
    est périmée : il faut recalculer, puis `enregistrer` avec `version`."""

    version: int
    valeur: AgregatStocke | None


class AgregatsRepository(ABC):
    @abstractmethod
    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, LigneAgregat]:
        """Un dossier sans ligne n'est pas dans le résultat : à calculer, puis
        à enregistrer avec `version_lue=None`."""

    @abstractmethod
    def enregistrer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        valeur: AgregatStocke,
        version_lue: int | None,
    ) -> bool:
        """Garde `valeur` si rien n'a périmé la ligne depuis la lecture qui a
        donné `version_lue` (`None` : la ligne n'existait pas). Retourne
        `False` sinon : le calcul est servi à l'appelant mais pas gardé, le
        prochain affichage le refera sur les données à jour."""


@dataclass(slots=True)
class _Ligne:
    version: int
    a_jour: bool
    version_calcul: int | None
    valeur: AgregatStocke | None


class InMemoryAgregatsRepository(AgregatsRepository):
    """Pour les tests. En Postgres, `invalider` est fait par des triggers à
    chaque écriture ; ici, c'est au test de l'appeler."""

    def __init__(self) -> None:
        self._lignes: dict[DossierId, _Ligne] = {}

    def invalider(self, dossier_id: DossierId) -> None:
        ligne = self._lignes.get(dossier_id)
        if ligne is None:
            self._lignes[dossier_id] = _Ligne(1, False, None, None)
        else:
            ligne.a_jour = False
            ligne.version += 1

    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, LigneAgregat]:
        lues: dict[DossierId, LigneAgregat] = {}
        for dossier_id in dossier_ids:
            ligne = self._lignes.get(dossier_id)
            if ligne is None:
                continue
            valide = ligne.a_jour and ligne.version_calcul == VERSION_CALCUL
            lues[dossier_id] = LigneAgregat(ligne.version, ligne.valeur if valide else None)
        return lues

    def enregistrer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        valeur: AgregatStocke,
        version_lue: int | None,
    ) -> bool:
        ligne = self._lignes.get(dossier_id)
        if ligne is None and version_lue is None:
            self._lignes[dossier_id] = _Ligne(0, True, VERSION_CALCUL, valeur)
            return True
        if ligne is None or version_lue is None or ligne.version != version_lue:
            return False
        ligne.a_jour = True
        ligne.version_calcul = VERSION_CALCUL
        ligne.valeur = valeur
        return True
