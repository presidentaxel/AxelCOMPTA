"""Façade : un tuple de mouvements entre, un tuple d'alertes sort."""

from __future__ import annotations

from .detecteurs import (
    detecter_double_plein,
    detecter_doublons,
    detecter_ecart_profil,
    detecter_enseigne_ambigue,
    detecter_libelle_generique,
    detecter_personnel,
    detecter_petit_carburant,
)
from .models import Alerte, MouvementSurveille

_PLAFOND = 10_000


def analyser(
    mouvements: tuple[MouvementSurveille, ...], plancher_carburant_cts: int | None = None
) -> tuple[Alerte, ...]:
    """Détecteurs V1, dans l'ordre du doc 05 §6.2bis, puis ceux du carburant
    (AXE-836). `plancher_carburant_cts` : le plancher du pack (AXE-837).
    Au plus 10 000 mouvements."""
    bornes = mouvements[:_PLAFOND]
    return (
        detecter_personnel(bornes)
        + detecter_enseigne_ambigue(bornes)
        + detecter_ecart_profil(bornes)
        + detecter_doublons(bornes)
        + detecter_double_plein(bornes, plancher_carburant_cts)
        + detecter_petit_carburant(bornes, plancher_carburant_cts)
        + detecter_libelle_generique(bornes)
    )
