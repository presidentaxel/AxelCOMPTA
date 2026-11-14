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

Un même versement lu sur deux comptes Rollee du même chauffeur est gardé
deux fois. Un seul reste rapprochable ; la copie passe « à vérifier ».
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


MOTIF_DOUBLON = "même versement déjà lu sur un autre compte Rollee"
MOTIF_ECART = "même période lue sur un autre compte Rollee, montants différents"


def _plateforme(stocke: SettlementStocke) -> str:
    return stocke.settlement.platform.casefold().strip()


def _copies_identiques(actifs: Sequence[SettlementStocke]) -> dict[str, str]:
    """Même plateforme, même période, même net : une copie reste, les autres non."""
    par_empreinte: dict[tuple[str, object, object, int], list[SettlementStocke]] = {}
    for stocke in actifs:
        cle_eco = (
            _plateforme(stocke),
            stocke.settlement.period_start,
            stocke.settlement.period_end,
            stocke.settlement.net_payout_cts,
        )
        par_empreinte.setdefault(cle_eco, []).append(stocke)
    marques: dict[str, str] = {}
    for groupe in par_empreinte.values():
        if len(groupe) < 2:
            continue
        ventiles = [s for s in groupe if s.etat == "reconcilie"]
        garde = ventiles[0] if ventiles else min(groupe, key=lambda s: s.id)
        for stocke in groupe:
            if stocke.id != garde.id and stocke.etat in A_RAPPROCHER:
                marques[stocke.id] = MOTIF_DOUBLON
    return marques


def _ecarts_de_periode(actifs: Sequence[SettlementStocke], deja: set[str]) -> dict[str, str]:
    """Même période, montants différents : le plus complet reste rapprochable."""
    par_periode: dict[tuple[str, object, object], list[SettlementStocke]] = {}
    for stocke in actifs:
        if stocke.id in deja:
            continue
        par_periode.setdefault(
            (_plateforme(stocke), stocke.settlement.period_start, stocke.settlement.period_end),
            [],
        ).append(stocke)
    marques: dict[str, str] = {}
    for groupe in par_periode.values():
        marques.update(_ecart_du_groupe(groupe))
    return marques


def _ecart_du_groupe(groupe: Sequence[SettlementStocke]) -> dict[str, str]:
    if len({s.settlement.net_payout_cts for s in groupe}) < 2:
        return {}
    if any(s.etat == "reconcilie" for s in groupe):
        return {s.id: MOTIF_ECART for s in groupe if s.etat in A_RAPPROCHER}
    eligibles = [s for s in groupe if s.etat in A_RAPPROCHER]
    if len(eligibles) < 2:
        return {}
    garde = max(eligibles, key=lambda s: (s.settlement.net_payout_cts, s.id))
    return {s.id: MOTIF_ECART for s in eligibles if s.id != garde.id}


def marquer_doublons(
    stockes: Sequence[SettlementStocke], maintenant: datetime
) -> list[SettlementStocke]:
    """Garde chaque relevé. Un seul de chaque versement identique (plateforme,
    période, net) reste rapprochable : celui déjà ventilé, sinon le plus
    ancien identifiant. Les copies passent « à vérifier » et ne s'écrivent pas.
    Même période, montants différents : le plus élevé reste rapprochable
    (le relevé le plus complet), les autres attendent un regard. Si l'un est
    déjà ventilé, les autres de la même période attendent aussi."""
    actifs = [s for s in stockes if s.etat != "delie"]
    a_marquer = _copies_identiques(actifs)
    a_marquer.update(_ecarts_de_periode(actifs, set(a_marquer)))
    return [
        replace(s, etat="a_verifier", motif=a_marquer[s.id], maj_le=maintenant)
        for s in stockes
        if s.id in a_marquer
    ]


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
