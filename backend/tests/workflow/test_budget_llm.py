"""AXE-887 : garde-fous de coût de l'étage LLM."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.workflow.budget_llm import (
    ECHECS_MAX,
    Depenses,
    Lot,
    Plafonds,
    abandonnees,
    anomalies,
    bandeau,
    coupe_circuit,
    cout,
    echecs_par_cle,
    id_lot,
    max_tokens,
    plafonds_configures,
    projection_depasse,
    refus_budget,
    seuils_atteints,
)

MAINTENANT = datetime(2026, 11, 13, 12, tzinfo=UTC)


def lot(
    ident: str = "l1",
    dossier: str = "d1",
    statut: str = "termine",
    cout_usd: float = 0.1,
    **autres: object,
) -> Lot:
    base = Lot(
        id=ident,
        tenant_id=TenantId("t"),
        dossier_id=DossierId(dossier),
        version="v",
        modele="claude-fable-5-2",
        cles=("A",),
        statut=statut,  # type: ignore[arg-type]
        estimation_usd=0.05,
        soumis_le=MAINTENANT,
        batch_id="b1",
        cout_usd=cout_usd,
        termine_le=MAINTENANT,
    )
    return replace(base, **autres)  # type: ignore[arg-type]


def test_l_api_batch_coute_moitie_prix_et_un_modele_inconnu_au_prix_fort() -> None:
    assert cout("claude-fable-5-2", 1_000_000, 0) == pytest.approx(4.0)
    assert cout("modele-inconnu", 1_000_000, 0) == cout("claude-fable-5-2", 1_000_000, 0)


def test_max_tokens_suit_le_lot_et_reste_borne() -> None:
    assert max_tokens(1) < max_tokens(80) <= 16_000
    assert max_tokens(10_000) == 16_000


def test_l_identifiant_d_un_lot_ne_depend_pas_de_l_ordre_mais_de_la_tentative() -> None:
    d = DossierId("d1")
    assert id_lot(d, "v", ["A", "B"], 1) == id_lot(d, "v", ["B", "A"], 1)
    assert id_lot(d, "v", ["A", "B"], 1) != id_lot(d, "v", ["A", "B"], 2)


def test_deux_echecs_ou_un_refus_et_le_libelle_ne_repart_plus() -> None:
    lots = [lot("1", statut="echec"), lot("2", statut="echec", cles=("A", "B"))]
    assert abandonnees(lots) == {"A"}
    assert abandonnees([lot("3", statut="refus", cles=("C",))]) == {"C"}
    assert echecs_par_cle([lot("4", statut="refus")])["A"] == ECHECS_MAX


def test_une_soumission_jamais_partie_ne_compte_pas_comme_un_echec() -> None:
    assert abandonnees([lot(str(i), statut="echec", batch_id=None) for i in range(3)]) == set()


def test_le_coupe_circuit_s_ouvre_quand_la_moitie_des_lots_recents_echoue() -> None:
    bons = [lot(f"ok{i}") for i in range(2)]
    mauvais = [lot(f"ko{i}", statut="echec") for i in range(2)]
    assert coupe_circuit([*bons, *mauvais], MAINTENANT)
    assert not coupe_circuit([*bons, mauvais[0]], MAINTENANT)  # 1 sur 3
    anciens = [replace(m, termine_le=MAINTENANT - timedelta(days=2)) for m in mauvais]
    assert not coupe_circuit([*bons, *anciens], MAINTENANT)


def test_un_lot_compte_son_estimation_tant_qu_il_n_est_pas_releve() -> None:
    depenses = Depenses.du_mois([lot("a", statut="soumis"), lot("b", cout_usd=0.2)], MAINTENANT)
    assert depenses.par_dossier["d1"] == pytest.approx(0.25)
    mois_dernier = lot("c", soumis_le=MAINTENANT - timedelta(days=30))
    assert Depenses.du_mois([mois_dernier], MAINTENANT).globale == 0


def test_au_dela_du_plafond_du_chauffeur_ou_global_rien_ne_part() -> None:
    depenses = Depenses.du_mois([lot(cout_usd=0.45)], MAINTENANT)
    plafonds = Plafonds(chauffeur_usd=0.5, global_usd=10)
    assert refus_budget(depenses, DossierId("d1"), 0.04, plafonds) is None
    assert "chauffeur" in (refus_budget(depenses, DossierId("d1"), 0.06, plafonds) or "")
    assert "global" in (
        refus_budget(depenses, DossierId("d2"), 0.1, Plafonds(0.5, global_usd=0.5)) or ""
    )


def test_les_seuils_et_la_projection() -> None:
    assert seuils_atteints(0.40, 0.5) == [50, 80]
    assert seuils_atteints(0.5, 0.5) == [50, 80, 100]
    # 13 jours et demi pour 0,30 $ : environ 0,67 $ sur 30 jours.
    assert projection_depasse(0.30, 0.5, MAINTENANT)
    assert not projection_depasse(0.10, 0.5, MAINTENANT)
    assert not projection_depasse(0.30, 0.5, MAINTENANT.replace(day=2))  # trop tôt


def test_un_chauffeur_qui_coute_trois_fois_la_moyenne_est_signale() -> None:
    lots = [lot(f"l{i}", dossier=f"d{i}", cout_usd=0.05) for i in range(5)]
    lots.append(lot("cher", dossier="d9", cout_usd=1.0))
    assert anomalies(Depenses.du_mois(lots, MAINTENANT)) == ["d9"]
    assert anomalies(Depenses.du_mois(lots[:3], MAINTENANT)) == []  # trop peu de dossiers


def test_le_bandeau_d_integrations() -> None:
    assert bandeau(0.1, 5.0, MAINTENANT.replace(day=2)) is None
    assert bandeau(4.1, 5.0, MAINTENANT) == "80 % du budget du mois de l'IA est utilisé."
    assert "atteint" in (bandeau(5.0, 5.0, MAINTENANT) or "")


def test_les_plafonds_se_reglent_par_l_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    assert plafonds_configures() == Plafonds(0.5, 100.0)
    monkeypatch.setenv("AXELCOMPTA_LLM_PLAFOND_CHAUFFEUR_USD", "0.2")
    assert plafonds_configures().chauffeur_usd == 0.2
