"""Bilan 2050/2051 sur les chauffeurs de démo : l'actif net égale le passif,
et le résultat est le même que celui de la 2033-B."""

from __future__ import annotations

import dataclasses

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.demo_chauffeurs_type import construire_ledger, parametres_cloture
from axelcompta.ingestion.providers.chauffeurs_demo import PROFIL_KARIM, PROFIL_YANIS


def test_le_bilan_reel_reste_equilibre() -> None:
    for profil in (PROFIL_KARIM, PROFIL_YANIS):
        ledger, _ = construire_ledger(profil)
        parametres = dataclasses.replace(parametres_cloture(profil), regime_liasse="2050")
        liasse = ClotureSimplifieeService(ledger).cloturer(profil.dossier_id, "2025", parametres)
        actif_net = liasse.cases["2050.CO"] - liasse.cases["2050.1A"]
        assert actif_net == liasse.cases["2050.EE"]
        assert liasse.cases["2050.DI"] == liasse.cases["2033B.310"]
        assert "2033A.180" in liasse.cases
