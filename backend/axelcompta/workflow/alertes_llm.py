"""Alertes de budget de l'étage LLM (AXE-887).

Seuils de 50, 80 et 100 % du budget du mois, par chauffeur, par cabinet et
au global, plus une alerte de projection (cabinet et global) quand le
rythme du mois dépassera le budget avant la fin du mois. Les chauffeurs qui
coûtent plus de 3 fois la moyenne sont signalés : boucle ou dossier anormal.

Une alerte ne part qu'une fois par portée, par mois et par seuil
(`AlertesLlm.marquer`). Elle va à l'équipe AxeL, jamais au cabinet : le
gestionnaire ne voit pas ce que l'IA coûte.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from axelcompta.core.ids import TenantId

from .budget_llm import (
    Depenses,
    Lot,
    Plafonds,
    anomalies,
    du_mois,
    projection_depasse,
    seuils_atteints,
)
from .lots_llm import AlertesLlm

PORTEE_CHAUFFEUR = "chauffeur"
PORTEE_CABINET = "cabinet"
PORTEE_GLOBAL = "global"
PORTEE_ANOMALIE = "anomalie"


@dataclass(frozen=True, slots=True)
class AlerteLlm:
    portee: str
    cle: str  # dossier, tenant, ou « tous »
    seuil: str  # « 50 », « 80 », « 100 », « projection », « x3 »
    texte: str
    tenant_id: TenantId | None  # le cabinet à prévenir ; None : l'équipe AxeL

    @property
    def grave(self) -> bool:
        return self.portee == PORTEE_GLOBAL and self.seuil == "100"


def _candidates(
    lots: list[Lot],
    dossiers_par_tenant: Mapping[TenantId, int],
    plafonds: Plafonds,
    maintenant: datetime,
) -> Iterable[AlerteLlm]:
    depenses = Depenses.du_mois(lots, maintenant)
    for dossier_id, depense in sorted(depenses.par_dossier.items()):
        for seuil in seuils_atteints(depense, plafonds.chauffeur_usd):
            texte = f"Claude : {seuil} % du budget du mois atteint pour le dossier {dossier_id}."
            yield AlerteLlm(PORTEE_CHAUFFEUR, dossier_id, str(seuil), texte, None)
    par_tenant: dict[TenantId, float] = {}
    for lot in du_mois(lots, maintenant):
        par_tenant[lot.tenant_id] = par_tenant.get(lot.tenant_id, 0.0) + lot.depense_usd
    for tenant, depense in sorted(par_tenant.items()):
        plafond = plafonds.chauffeur_usd * max(dossiers_par_tenant.get(tenant, 1), 1)
        yield from _paliers(PORTEE_CABINET, str(tenant), depense, plafond, maintenant, None)
    yield from _paliers(
        PORTEE_GLOBAL, "tous", depenses.globale, plafonds.global_usd, maintenant, None
    )
    for dossier_id in anomalies(depenses):
        texte = f"Claude : le dossier {dossier_id} coûte plus de 3 fois la moyenne ce mois-ci."
        yield AlerteLlm(PORTEE_ANOMALIE, dossier_id, "x3", texte, None)


def _paliers(
    portee: str,
    cle: str,
    depense: float,
    plafond: float,
    maintenant: datetime,
    tenant: TenantId | None,
) -> Iterable[AlerteLlm]:
    qui = "du cabinet" if portee == PORTEE_CABINET else "global"
    for seuil in seuils_atteints(depense, plafond):
        texte = (
            f"Claude : {seuil} % du budget {qui} du mois atteint "
            f"({depense:.2f} $ sur {plafond:.2f} $)."
        )
        yield AlerteLlm(portee, cle, str(seuil), texte, tenant)
    if projection_depasse(depense, plafond, maintenant):
        texte = (
            f"Claude : au rythme actuel, le budget {qui} ({plafond:.2f} $) "
            "sera dépassé avant la fin du mois."
        )
        yield AlerteLlm(portee, cle, "projection", texte, tenant)


def nouvelles_alertes(
    lots: list[Lot],
    dossiers_par_tenant: Mapping[TenantId, int],
    plafonds: Plafonds,
    alertes: AlertesLlm,
    maintenant: datetime,
) -> list[AlerteLlm]:
    """Les alertes à envoyer maintenant : celles déjà parties ce mois-ci sont filtrées."""
    mois = f"{maintenant:%Y-%m}"
    return [
        alerte
        for alerte in _candidates(lots, dossiers_par_tenant, plafonds, maintenant)
        if alertes.marquer(alerte.portee, alerte.cle, mois, alerte.seuil, maintenant)
    ]
