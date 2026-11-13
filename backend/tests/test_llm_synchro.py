"""AXE-887 : l'étage LLM dans les tâches planifiées (sans base ni appel)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from axelcompta.core.metriques import METRIQUES
from axelcompta.llm_synchro import _a_relire, mesurer_llm, passer_llm
from tests.workflow.test_budget_llm import MAINTENANT, lot
from tests.workflow.test_propositions_ia import DOSSIER


def test_l_etage_llm_est_eteint_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AXELCOMPTA_LLM_ACTIF", raising=False)
    assert passer_llm(None, datetime(2026, 11, 20, tzinfo=UTC)) == []  # type: ignore[arg-type]
    monkeypatch.setenv("AXELCOMPTA_LLM_ACTIF", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert passer_llm(None, datetime(2026, 11, 20, tzinfo=UTC)) == [  # type: ignore[arg-type]
        "llm : ANTHROPIC_API_KEY absente, rien n'est envoyé"
    ]


def test_un_dossier_deja_passe_aujourd_hui_n_est_pas_relu() -> None:
    hier = lot("h", dossier=str(DOSSIER.id), soumis_le=MAINTENANT - timedelta(days=1))
    assert _a_relire([DOSSIER], [hier], MAINTENANT) == [DOSSIER]
    aujourd_hui = lot("a", dossier=str(DOSSIER.id), soumis_le=MAINTENANT)
    assert _a_relire([DOSSIER], [aujourd_hui], MAINTENANT) == []
    en_cours = lot(
        "c", dossier=str(DOSSIER.id), statut="soumis", soumis_le=MAINTENANT - timedelta(days=2)
    )
    assert _a_relire([DOSSIER], [en_cours], MAINTENANT) == []


def test_le_cout_du_mois_et_le_taux_de_cache_sont_mesures() -> None:
    lots = [
        lot("a", dossier="d1", cout_usd=0.1, jetons_entree=1_000, jetons_cache=750),
        lot("b", dossier="d2", cout_usd=0.3, jetons_entree=1_000, jetons_cache=250),
    ]
    (ligne,) = mesurer_llm(lots, MAINTENANT)
    assert ligne == "llm : 0.40 $ ce mois-ci, 2 chauffeur(s), 0.200 $ en moyenne, 50 % lu en cache"
    texte = METRIQUES.texte()
    assert "llm_cout_moyen_chauffeur_usd 0.2" in texte
    assert "llm_part_cache 50.0" in texte
