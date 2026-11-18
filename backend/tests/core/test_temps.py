"""AXE-920 : « aujourd'hui » est le jour de Paris, pas celui d'UTC."""

from __future__ import annotations

from datetime import UTC, date, datetime

from axelcompta.core.temps import aujourd_hui_paris


def test_apres_minuit_a_paris_c_est_deja_le_lendemain() -> None:
    # 23 h 30 UTC le 13/11 = 0 h 30 le 14/11 à Paris (hiver, UTC+1).
    assert aujourd_hui_paris(datetime(2026, 11, 13, 23, 30, tzinfo=UTC)) == date(2026, 11, 14)


def test_l_ete_le_decalage_est_de_deux_heures() -> None:
    # 22 h 30 UTC le 14/07 = 0 h 30 le 15/07 à Paris (été, UTC+2).
    assert aujourd_hui_paris(datetime(2026, 7, 14, 22, 30, tzinfo=UTC)) == date(2026, 7, 15)


def test_en_journee_les_deux_fuseaux_disent_le_meme_jour() -> None:
    assert aujourd_hui_paris(datetime(2026, 11, 14, 12, 0, tzinfo=UTC)) == date(2026, 11, 14)
