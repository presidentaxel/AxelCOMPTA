"""Opérations déjà classées, pour vérifier le classement (AXE-823).

Le mode expert montre ce qui reste à faire ; cette vue montre ce qui est
déjà fait, et par qui ou quoi : classé automatiquement (règle, modèle),
décidé par le chauffeur, ou imputé par l'expert. Un verdict « juste » ou
« faux » se garde sans écriture : il sert à mesurer la précision (AXE-816).

Pur : le grand livre (décisions appliquées), les propositions d'origine, les
décisions et les verdicts sont lus ailleurs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.ledger.contrepassation import annulees, origine
from axelcompta.ledger.models import Ecriture, Sens

from .synchro import COMPTE_ATTENTE

Statut = Literal["auto", "chauffeur", "expert"]
Verdict = Literal["juste", "faux"]

STATUTS: tuple[Statut, ...] = ("auto", "chauffeur", "expert")
ORIGINES = ("regle", "modele", "humain", "inconnue")
# Tranches de confiance du ticket : < 0,6 / 0,6–0,95 / ≥ 0,95.
TRANCHES = ("basse", "moyenne", "haute")
MARQUE_IMPUTATION = ":impute-"

_ORIGINE_PAR_ETAGE = {Etage.REGLE: "regle", Etage.ML: "modele", Etage.LLM: "modele"}


@dataclass(frozen=True, slots=True)
class OperationClassee:
    dossier_id: DossierId
    ecriture_id: EcritureId
    date: date
    libelle: str
    montant_cts: int  # signé : positif = entrée d'argent
    compte: str
    categorie: str | None
    origine: str
    confiance: float | None
    statut: Statut
    verdict: Verdict | None = None

    @property
    def sens(self) -> str:
        return "entree" if self.montant_cts > 0 else "sortie"

    @property
    def tranche(self) -> str | None:
        return tranche_de(self.confiance)


@dataclass(frozen=True, slots=True)
class Filtres:
    statut: Statut | None = None  # None : toutes
    origine: str | None = None
    categorie: str | None = None
    tranche: str | None = None
    sens: str | None = None

    def garde(self, operation: OperationClassee) -> bool:
        attendus = (
            (self.statut, operation.statut),
            (self.origine, operation.origine),
            (self.categorie, operation.categorie),
            (self.tranche, operation.tranche),
            (self.sens, operation.sens),
        )
        return all(voulu is None or voulu == valeur for voulu, valeur in attendus)


@dataclass(frozen=True, slots=True)
class Compteurs:
    auto: int
    chauffeur: int
    expert: int
    justes: int
    fausses: int


def tranche_de(confiance: float | None) -> str | None:
    if confiance is None:
        return None
    if confiance < 0.6:
        return "basse"
    return "moyenne" if confiance < 0.95 else "haute"


def _banque(ecriture: Ecriture) -> int:
    """Montant signé côté banque (512x) : positif = entrée."""
    return sum(
        (1 if ligne.sens is Sens.DEBIT else -1) * ligne.montant.centimes
        for ligne in ecriture.lignes
        if ligne.compte.startswith("512")
    )


def _compte(ecriture: Ecriture) -> str | None:
    """La contrepartie économique : ni banque, ni TVA."""
    comptes = sorted(
        {ligne.compte for ligne in ecriture.lignes if not ligne.compte.startswith(("512", "445"))}
    )
    return comptes[0] if comptes else None


def _source(ecriture_id: EcritureId) -> EcritureId:
    """`e1:impute-606` → `e1` : l'opération bancaire d'origine."""
    return EcritureId(ecriture_id.split(MARQUE_IMPUTATION, 1)[0])


def classer(
    ecritures: Sequence[Ecriture],
    propositions: Mapping[EcritureId, ProposedEntry],
    decisions: Mapping[EcritureId, str],
    verdicts: Mapping[EcritureId, Verdict],
) -> list[OperationClassee]:
    """Une opération par écriture classée. `ecritures` : le grand livre avec
    les décisions du chauffeur déjà appliquées. Sont écartées : les paires
    contre-passées, les contre-passations et ce qui est encore en 471."""
    exclues = annulees(ecritures)
    resultat = []
    for ecriture in ecritures:
        if ecriture.id in exclues or origine(ecriture.id) is not None:
            continue
        operation = _operation(ecriture, propositions, decisions, verdicts)
        if operation is not None:
            resultat.append(operation)
    return resultat


def _operation(
    ecriture: Ecriture,
    propositions: Mapping[EcritureId, ProposedEntry],
    decisions: Mapping[EcritureId, str],
    verdicts: Mapping[EcritureId, Verdict],
) -> OperationClassee | None:
    compte = _compte(ecriture)
    if compte is None or compte == COMPTE_ATTENTE:
        return None
    source = _source(ecriture.id)
    proposition = propositions.get(source)
    statut: Statut
    if MARQUE_IMPUTATION in ecriture.id:
        statut, origine_, categorie, confiance = "expert", "humain", None, None
    elif ecriture.id in decisions:
        statut, origine_, categorie, confiance = "chauffeur", "humain", decisions[ecriture.id], None
    elif proposition is not None:
        statut = "auto"
        origine_ = _ORIGINE_PAR_ETAGE.get(proposition.etage, "inconnue")
        categorie, confiance = proposition.categorie, proposition.confiance
    else:
        statut, origine_, categorie, confiance = "auto", "inconnue", None, None
    return OperationClassee(
        dossier_id=ecriture.dossier_id,
        ecriture_id=ecriture.id,
        date=ecriture.date,
        libelle=ecriture.libelle,
        montant_cts=_banque(ecriture),
        compte=compte,
        categorie=categorie,
        origine=origine_,
        confiance=confiance,
        statut=statut,
        verdict=verdicts.get(ecriture.id),
    )


def trier(operations: Iterable[OperationClassee], tri: str) -> list[OperationClassee]:
    """`confiance` : les plus fragiles d'abord (sans confiance en dernier) ;
    sinon les plus récentes d'abord."""
    if tri == "confiance":
        return sorted(
            operations,
            key=lambda o: (o.confiance is None, o.confiance or 0.0, o.date, o.ecriture_id),
        )
    return sorted(operations, key=lambda o: (o.date, o.ecriture_id), reverse=True)


def compter(operations: Iterable[OperationClassee]) -> Compteurs:
    liste = list(operations)
    return Compteurs(
        auto=sum(o.statut == "auto" for o in liste),
        chauffeur=sum(o.statut == "chauffeur" for o in liste),
        expert=sum(o.statut == "expert" for o in liste),
        justes=sum(o.verdict == "juste" for o in liste),
        fausses=sum(o.verdict == "faux" for o in liste),
    )
