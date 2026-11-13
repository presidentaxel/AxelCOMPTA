"""Relevés de revenus des plateformes, gardés et rapprochés (AXE-821).

Un relevé = une période de revenus d'un compte de plateforme (une semaine
Uber, par exemple), lu chez Rollee. Il est gardé une fois par compte et par
période, puis rapproché du virement reçu en banque :

* `en_attente_banque` : pas encore de virement correspondant (ou la période
  n'est pas finie : Rollee la complète au fil des jours) ;
* `reconcilie` : un seul virement correspond, déjà en recette : ventilé ;
* `a_classer` : le virement correspond mais attend encore sa catégorie
  (compte d'attente) : le chauffeur le classe en recette, la synchro
  suivante le ventile ;
* `a_verifier` : plusieurs virements possibles, virement classé ailleurs,
  exercice clos, ou relevé modifié après ventilation. Rien n'est écrit.
* `delie` : relevé d'un compte Rollee dont le lien avec le dossier a été
  retiré (AXE-911). Sa ventilation est contre-passée ; il n'est plus traité.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal, Protocol

from axelcompta.core.ids import DossierId

from .providers.base import PlatformSettlement

Etat = Literal["en_attente_banque", "reconcilie", "a_classer", "a_verifier", "delie"]
A_RAPPROCHER: frozenset[str] = frozenset({"en_attente_banque", "a_classer"})


@dataclass(frozen=True, slots=True)
class SettlementStocke:
    id: str
    account_id: str
    settlement: PlatformSettlement
    etat: Etat
    maj_le: datetime
    ecriture_id: str | None = None  # le virement rapproché
    motif: str | None = None


def cle(account_id: str, settlement: PlatformSettlement) -> str:
    return f"{account_id}:{settlement.period_start}:{settlement.period_end}"


def _memes_montants(a: PlatformSettlement, b: PlatformSettlement) -> bool:
    return (a.gross_earnings_cts, a.commission_cts, a.net_payout_cts) == (
        b.gross_earnings_cts,
        b.commission_cts,
        b.net_payout_cts,
    )


def fusionner(
    connu: SettlementStocke | None,
    account_id: str,
    lu: PlatformSettlement,
    maintenant: datetime,
) -> SettlementStocke | None:
    """Le relevé à enregistrer, ou `None` si rien ne change. Un relevé déjà
    ventilé n'est jamais réécrit : s'il change chez Rollee, il passe « à
    vérifier » (la ventilation reste, c'est à l'humain de trancher)."""
    if connu is None:
        return SettlementStocke(
            cle(account_id, lu), account_id, lu, "en_attente_banque", maintenant
        )
    if _memes_montants(connu.settlement, lu):
        return None
    if connu.etat == "reconcilie":
        return replace(
            connu, etat="a_verifier", motif="relevé modifié après ventilation", maj_le=maintenant
        )
    return replace(connu, settlement=lu, maj_le=maintenant)


def a_verifier(stockes: Sequence[SettlementStocke]) -> list[SettlementStocke]:
    """AXE-891 : les relevés qu'un humain doit regarder, dans l'ordre reçu."""
    return [s for s in stockes if s.etat == "a_verifier"]


class SettlementsRepository(Protocol):
    def lister(self, dossier_id: DossierId) -> list[SettlementStocke]: ...

    def enregistrer(self, settlements: Sequence[SettlementStocke]) -> None:
        """Ajoute ou remplace, par identifiant."""
        ...


@dataclass
class SettlementsMemoire:
    stockes: dict[str, SettlementStocke] = field(default_factory=dict)

    def lister(self, dossier_id: DossierId) -> list[SettlementStocke]:
        return sorted(
            (s for s in self.stockes.values() if s.settlement.dossier_id == dossier_id),
            key=lambda s: (s.settlement.period_start, s.id),
        )

    def enregistrer(self, settlements: Sequence[SettlementStocke]) -> None:
        for settlement in settlements:
            self.stockes[settlement.id] = settlement
