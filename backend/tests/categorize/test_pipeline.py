from __future__ import annotations

from datetime import date

import pytest

from axelcompta.categorize.models import Etage
from axelcompta.categorize.pipeline import (
    CATEGORIE_NON_CLASSEE,
    CategorizationPipeline,
    SansClassement,
)
from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.workflow.synchro import COMPTE_ATTENTE, choisir_compte


def test_categorization_pipeline_est_abstrait() -> None:
    with pytest.raises(TypeError):
        CategorizationPipeline()  # type: ignore[abstract]


def test_sans_classement_envoie_tout_en_attente() -> None:
    """AXE-829 : aucune règle, aucun modèle, le compte d'attente."""
    transaction = NormalizedTransaction(
        id=TransactionId("tx1"),
        dossier_id=DossierId("d1"),
        date=date(2026, 9, 3),
        montant_cts=-4_500,
        libelle="CB TOTAL A6",
        source_provider="fixture",
        raw_payload={},
    )
    proposition = SansClassement().categoriser(DossierId("d1"), transaction)
    assert (proposition.categorie, proposition.etage) == (
        CATEGORIE_NON_CLASSEE,
        Etage.REVUE_HUMAINE,
    )
    assert choisir_compte(proposition, {CATEGORIE_NON_CLASSEE: "606"}) == COMPTE_ATTENTE
