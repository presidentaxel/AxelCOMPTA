"""Comptes bancaires d'un dossier et leur sous-compte 512x (AXE-832).

Un dossier peut avoir plusieurs comptes chez sa banque (MK DRIVING : un
compte courant et quatre sous-comptes). Chacun reçoit son propre sous-compte
de banque, dans l'ordre d'apparition : 5121, 5122… Le numéro ne change plus
une fois attribué : le FEC et les écritures passées en dépendent.

Le nom et le solde viennent du relevé des comptes du fournisseur
(Digifactory `GET /accounts`), relu à chaque synchro.

Comptes retenus (AXE-729) : seuls les comptes professionnels produisent des
écritures. Un compte personnel mélangé au compte pro fabriquerait de fausses
charges. Le premier compte d'un dossier est retenu d'office, sauf si le
premier relevé en montre plusieurs ; tout autre compte attend la décision du
dirigeant (`retenu` à `None`) et ne produit rien.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId, UserId
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
    # AXE-729 : True, comptabilisé ; False, écarté (personnel) ; None, à décider.
    retenu: bool | None = None
    # Retenu après coup : la prochaine synchro relit tout l'historique pour
    # importer les opérations passées de ce compte.
    a_relire: bool = False


class CompteInconnu(DomaineError):
    """Aucun compte de ce dossier ne porte ce numéro."""


class CompteDejaComptabilise(DomaineError):
    """Écarter un compte qui a déjà des écritures les laisserait en place."""


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

    def decider(
        self, dossier_id: DossierId, compte_comptable: str, retenu: bool, par: UserId, le: datetime
    ) -> CompteBancaire:
        """Retient ou écarte un compte, et trace le choix. Retenu après coup :
        marqué « à relire ». Lève `CompteInconnu`."""
        ...

    def relu(self, dossier_id: DossierId) -> None:
        """La synchro a relu l'historique : plus rien « à relire »."""
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
    depot: CompteBancaireRepository,
    dossier_id: DossierId,
    identifiant: str | None,
    *,
    deja_comptabilise: bool = False,
) -> str:
    """Sous-compte de banque d'une opération. Banque inconnue : `512`.

    Un compte créé ici est retenu s'il est le premier du dossier, ou s'il
    porte déjà des écritures (`deja_comptabilise`, reprise AXE-832) ; à
    décider sinon (AXE-729)."""
    if identifiant is None:
        return COMPTE_BANQUE
    existants = depot.lister(dossier_id)
    for compte in existants:
        if compte.identifiant == identifiant:
            return compte.compte_comptable
    retenu = True if deja_comptabilise or not existants else None
    return _creer(depot, dossier_id, identifiant, existants, retenu=retenu)


def _creer(
    depot: CompteBancaireRepository,
    dossier_id: DossierId,
    identifiant: str,
    existants: tuple[CompteBancaire, ...],
    retenu: bool | None,
) -> str:
    nouveau = CompteBancaire(
        dossier_id=dossier_id,
        identifiant=identifiant,
        compte_comptable=compte_comptable_suivant(c.compte_comptable for c in existants),
        retenu=retenu,
    )
    return depot.ajouter(nouveau).compte_comptable


def comptes_ecartes(depot: CompteBancaireRepository, dossier_id: DossierId) -> frozenset[str]:
    """Identifiants des comptes qui ne produisent rien : écartés ou à décider."""
    return frozenset(c.identifiant for c in depot.lister(dossier_id) if c.retenu is not True)


def verifier_ecartable(nombre_ecritures: int) -> None:
    """On n'écarte pas un compte déjà comptabilisé : ses écritures resteraient."""
    if nombre_ecritures:
        raise CompteDejaComptabilise(
            f"{nombre_ecritures} opération(s) de ce compte sont déjà dans la comptabilité. "
            "Votre comptable doit les reprendre avant de l'écarter."
        )


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
        self.decisions: list[tuple[DossierId, str, bool, UserId, datetime]] = []

    def decider(
        self, dossier_id: DossierId, compte_comptable: str, retenu: bool, par: UserId, le: datetime
    ) -> CompteBancaire:
        for cle, compte in self._comptes.items():
            if cle[0] == dossier_id and compte.compte_comptable == compte_comptable:
                relire = compte.a_relire or (retenu and compte.retenu is not True)
                self._comptes[cle] = replace(compte, retenu=retenu, a_relire=relire)
                self.decisions.append((dossier_id, compte_comptable, retenu, par, le))
                return self._comptes[cle]
        raise CompteInconnu(f"{dossier_id} : pas de compte {compte_comptable}")

    def relu(self, dossier_id: DossierId) -> None:
        for cle, compte in self._comptes.items():
            if cle[0] == dossier_id and compte.a_relire:
                self._comptes[cle] = replace(compte, a_relire=False)

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
    puis son nom et son solde. Renvoie les comptes du dossier à jour.

    Premier relevé avec plusieurs comptes : aucun n'est retenu d'office, le
    dirigeant choisit (AXE-729)."""
    releves = tuple(releves)
    if not depot.lister(dossier_id) and len(releves) > 1:
        for releve in releves:
            _creer(depot, dossier_id, releve.identifiant, depot.lister(dossier_id), retenu=None)
    for releve in releves:
        compte_de(depot, dossier_id, releve.identifiant)
        depot.relever(dossier_id, releve, releve_le)
    return depot.lister(dossier_id)
