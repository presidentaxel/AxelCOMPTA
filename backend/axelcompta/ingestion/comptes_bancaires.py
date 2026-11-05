"""Comptes bancaires d'un dossier et leur sous-compte 512x (AXE-832).

Un dossier peut avoir plusieurs comptes chez sa banque (MK DRIVING : un
compte courant et quatre sous-comptes). Chacun reçoit son propre sous-compte
de banque, dans l'ordre d'apparition : 5121, 5122… Le numéro ne change plus
une fois attribué : le FEC et les écritures passées en dépendent.

Le nom et le solde viennent du relevé des comptes du fournisseur
(Digifactory `GET /accounts`), relu à chaque synchro.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId
from axelcompta.core.pcg import COMPTE_BANQUE

# Au-delà, un dossier n'est plus un chauffeur mais une anomalie de données :
# on s'arrête plutôt que de numéroter à l'infini (doc 08, règle 2).
NOMBRE_MAX_COMPTES = 99


class TropDeComptesBancaires(DomaineError):
    """Le dossier dépasse `NOMBRE_MAX_COMPTES` comptes bancaires."""


@dataclass(frozen=True, slots=True)
class CompteBancaire:
    dossier_id: DossierId
    identifiant: str  # identifiant du compte chez le fournisseur
    compte_comptable: str  # 5121, 5122…
    nom: str | None = None
    solde_banque_cts: int | None = None
    solde_releve_le: datetime | None = None


@dataclass(frozen=True, slots=True)
class CompteReleve:
    """Un compte tel que le fournisseur le décrit, au moment du relevé."""

    identifiant: str
    nom: str | None
    solde_cts: int | None


class CompteBancaireRepository(Protocol):
    def lister(self, dossier_id: DossierId) -> tuple[CompteBancaire, ...]: ...

    def ajouter(self, compte: CompteBancaire) -> CompteBancaire:
        """Enregistre le compte. S'il existe déjà (même dossier, même
        identifiant), renvoie l'existant sans rien changer."""
        ...

    def relever(self, dossier_id: DossierId, releve: CompteReleve, releve_le: datetime) -> None:
        """Met à jour le nom et le solde d'un compte déjà enregistré."""
        ...


def compte_comptable_suivant(pris: Iterable[str]) -> str:
    """Premier sous-compte libre : 5121, 5122… jusqu'à 51299."""
    deja = set(pris)
    for rang in range(1, NOMBRE_MAX_COMPTES + 1):
        candidat = f"{COMPTE_BANQUE}{rang}"
        if candidat not in deja:
            return candidat
    raise TropDeComptesBancaires(f"plus de {NOMBRE_MAX_COMPTES} comptes bancaires")


def compte_de(
    depot: CompteBancaireRepository, dossier_id: DossierId, identifiant: str | None
) -> str:
    """Sous-compte de banque d'une opération. Banque inconnue : `512`."""
    if identifiant is None:
        return COMPTE_BANQUE
    existants = depot.lister(dossier_id)
    for compte in existants:
        if compte.identifiant == identifiant:
            return compte.compte_comptable
    nouveau = CompteBancaire(
        dossier_id=dossier_id,
        identifiant=identifiant,
        compte_comptable=compte_comptable_suivant(c.compte_comptable for c in existants),
    )
    return depot.ajouter(nouveau).compte_comptable


def comptes_releves(payload: object) -> tuple[CompteReleve, ...]:
    """Comptes d'une réponse `GET /accounts` Digifactory : un dict
    `{accountId: compte}` (vérifié le 2026-11-05) ou une liste. Un compte
    sans `id` est ignoré ; un solde illisible devient `None`, jamais 0."""
    valeurs: Iterable[object]
    if isinstance(payload, Mapping):
        valeurs = payload.values()
    elif isinstance(payload, list):
        valeurs = payload
    else:
        return ()
    releves: list[CompteReleve] = []
    for valeur in valeurs:
        if not isinstance(valeur, Mapping) or valeur.get("id") in (None, ""):
            continue
        nom = valeur.get("name")
        releves.append(
            CompteReleve(
                identifiant=str(valeur["id"]).strip(),
                nom=str(nom).strip() if isinstance(nom, str) and nom.strip() else None,
                solde_cts=_centimes(valeur.get("balance")),
            )
        )
    return tuple(releves)


def _centimes(valeur: object) -> int | None:
    if isinstance(valeur, bool) or valeur is None:
        return None
    try:
        montant = Decimal(str(valeur))
    except InvalidOperation:
        return None
    if not montant.is_finite():
        return None
    return int((montant * 100).to_integral_value())


class CompteBancaireMemoire:
    """Implémentation en mémoire, pour les tests et la démo."""

    def __init__(self) -> None:
        self._comptes: dict[tuple[DossierId, str], CompteBancaire] = {}

    def lister(self, dossier_id: DossierId) -> tuple[CompteBancaire, ...]:
        return tuple(
            sorted(
                (c for (d, _), c in self._comptes.items() if d == dossier_id),
                key=lambda c: (len(c.compte_comptable), c.compte_comptable),
            )
        )

    def ajouter(self, compte: CompteBancaire) -> CompteBancaire:
        cle = (compte.dossier_id, compte.identifiant)
        return self._comptes.setdefault(cle, compte)

    def relever(self, dossier_id: DossierId, releve: CompteReleve, releve_le: datetime) -> None:
        cle = (dossier_id, releve.identifiant)
        compte = self._comptes.get(cle)
        if compte is None:
            return
        self._comptes[cle] = replace(
            compte,
            nom=releve.nom or compte.nom,
            solde_banque_cts=releve.solde_cts,
            solde_releve_le=releve_le,
        )


def relever_comptes(
    depot: CompteBancaireRepository,
    dossier_id: DossierId,
    releves: Iterable[CompteReleve],
    releve_le: datetime,
) -> tuple[CompteBancaire, ...]:
    """Enregistre chaque compte relevé (numéro attribué s'il est nouveau),
    puis son nom et son solde. Renvoie les comptes du dossier à jour."""
    for releve in releves:
        compte_de(depot, dossier_id, releve.identifiant)
        depot.relever(dossier_id, releve, releve_le)
    return depot.lister(dossier_id)
