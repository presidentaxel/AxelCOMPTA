"""AXE-887 : alertes de budget, une fois par portée, par mois et par seuil."""

from __future__ import annotations

from datetime import timedelta

from axelcompta.core.ids import TenantId
from axelcompta.workflow.alertes_llm import (
    PORTEE_ANOMALIE,
    PORTEE_CABINET,
    PORTEE_CHAUFFEUR,
    PORTEE_GLOBAL,
    nouvelles_alertes,
)
from axelcompta.workflow.budget_llm import Plafonds
from axelcompta.workflow.lots_llm import AlertesLlmMemoire
from tests.workflow.test_budget_llm import MAINTENANT, lot

PLAFONDS = Plafonds(chauffeur_usd=0.5, global_usd=1.0)
UN_DOSSIER = {TenantId("t"): 1}


def _portees(alertes: list) -> set[tuple[str, str]]:  # type: ignore[type-arg]
    return {(a.portee, a.seuil) for a in alertes}


def test_chaque_seuil_ne_part_qu_une_fois_dans_le_mois() -> None:
    memoire = AlertesLlmMemoire()
    lots = [lot(cout_usd=0.26)]
    premieres = nouvelles_alertes(lots, UN_DOSSIER, PLAFONDS, memoire, MAINTENANT.replace(day=2))
    assert (PORTEE_CHAUFFEUR, "50") in _portees(premieres)
    assert (PORTEE_CABINET, "50") in _portees(premieres)
    assert all(a.tenant_id is None for a in premieres)
    encore = nouvelles_alertes(lots, UN_DOSSIER, PLAFONDS, memoire, MAINTENANT.replace(day=2))
    assert encore == []
    plus = [lot(cout_usd=0.41)]
    suite = nouvelles_alertes(plus, UN_DOSSIER, PLAFONDS, memoire, MAINTENANT.replace(day=2))
    assert _portees(suite) == {(PORTEE_CHAUFFEUR, "80"), (PORTEE_CABINET, "80")}


def test_le_mois_suivant_les_seuils_repartent() -> None:
    memoire = AlertesLlmMemoire()
    debut = MAINTENANT.replace(day=2)
    nouvelles_alertes([lot(cout_usd=0.3)], UN_DOSSIER, PLAFONDS, memoire, debut)
    decembre = debut + timedelta(days=30)
    lots = [lot(cout_usd=0.3, soumis_le=decembre)]
    assert nouvelles_alertes(lots, UN_DOSSIER, PLAFONDS, memoire, decembre) != []


def test_le_global_a_100_pourcent_est_grave_et_va_a_l_equipe() -> None:
    lots = [lot(f"l{i}", dossier=f"d{i}", cout_usd=0.25) for i in range(4)]
    alertes = nouvelles_alertes(
        lots, {TenantId("t"): 4}, PLAFONDS, AlertesLlmMemoire(), MAINTENANT.replace(day=2)
    )
    (globale,) = [a for a in alertes if a.portee == PORTEE_GLOBAL and a.seuil == "100"]
    assert globale.grave and globale.tenant_id is None


def test_la_projection_previent_avant_les_seuils() -> None:
    # Le 13 à midi, 0,24 $ sur un plafond de cabinet de 0,50 $ : 0,58 $ en fin de mois,
    # alors qu'aucun seuil n'est encore atteint.
    alertes = nouvelles_alertes(
        [lot(cout_usd=0.24)], UN_DOSSIER, Plafonds(0.5, 100), AlertesLlmMemoire(), MAINTENANT
    )
    assert (PORTEE_CABINET, "50") not in _portees(alertes)
    assert (PORTEE_CABINET, "projection") in _portees(alertes)


def test_un_dossier_trois_fois_plus_cher_que_la_moyenne_est_signale() -> None:
    lots = [lot(f"l{i}", dossier=f"d{i}", cout_usd=0.01) for i in range(5)]
    lots.append(lot("cher", dossier="d9", cout_usd=0.2))
    alertes = nouvelles_alertes(
        lots, {TenantId("t"): 6}, Plafonds(10, 100), AlertesLlmMemoire(), MAINTENANT.replace(day=2)
    )
    assert [a.cle for a in alertes if a.portee == PORTEE_ANOMALIE] == ["d9"]
