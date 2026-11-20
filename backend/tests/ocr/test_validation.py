"""AXE-991 : un humain corrige ou valide une lecture refusée par l'OCR."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from axelcompta.core.ids import TenantId
from axelcompta.ocr.categories import Contexte
from axelcompta.ocr.validation import LectureRefusee, valider_lecture
from axelcompta.tenants.fiches_import import document_import, nouvelle_fiche

LE = datetime(2026, 11, 19, tzinfo=UTC)
FICHE = nouvelle_fiche("f", TenantId("T"), "SYBD", "S", "", "b", LE)
# SG 11-2025 : solde de début débiteur lu en positif, et une ligne inventée.
LU_OCR: dict[str, object] = {
    "banque": "Société Générale",
    "titulaire": "SYBD",
    "iban": "",
    "periode_debut": "2025-11-01",
    "periode_fin": "2025-11-30",
    "montants": [
        {"nom": "solde_debut_cts", "valeur_cts": 22704},
        {"nom": "solde_fin_cts", "valeur_cts": 55074},
    ],
    "operations": [{"date": "2025-11-03", "libelle": "VIR UBER", "montant_cts": 99999}],
}
DOC = replace(
    document_import("d", FICHE, "banque:releve_bancaire", "SG.pdf", "", b"%PDF", "b", LE),
    donnees={"lu": LU_OCR, "ocr": {"version": "ocr-2", "a_verifier": True}},
)


def test_une_lecture_corrigee_qui_passe_les_controles_est_traitee() -> None:
    corrigee = {
        **LU_OCR,
        "operations": [{"date": "2025-11-03", "libelle": "VIR UBER", "montant_cts": 77778}],
        "inconnu": "écarté",
    }
    doc = valider_lecture(DOC, corrigee, Contexte(), "", "expert@x.fr", LE)
    assert doc.statut_traitement == "traite"
    assert doc.resume.endswith("Validé par expert@x.fr.")
    donnees = doc.donnees or {}
    assert donnees["type"] == "releve"  # sert comme une lecture acceptée
    assert donnees["solde_debut_cts"] == -22704
    assert "inconnu" not in donnees["lu"]  # type: ignore[operator]
    trace = donnees["validation"]
    assert isinstance(trace, dict) and trace["lu_ocr"] == LU_OCR and trace["controles"] == []
    assert donnees["ocr"] == {"version": "ocr-2", "a_verifier": False}


def test_sans_raison_une_lecture_fausse_est_refusee_avec_une_raison_elle_passe() -> None:
    with pytest.raises(LectureRefusee, match="Corrigez la lecture"):
        valider_lecture(DOC, LU_OCR, Contexte(), "  ", "expert@x.fr", LE)
    doc = valider_lecture(DOC, LU_OCR, Contexte(), "Relevé partiel, vu avec le client", "e", LE)
    assert doc.statut_traitement == "traite"
    assert "malgré les contrôles : Relevé partiel" in doc.resume
    trace = (doc.donnees or {})["validation"]
    assert isinstance(trace, dict) and trace["controles"]
