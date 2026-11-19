"""AXE-990 : associés, crédit de TVA et emprunts recopiés dans la fiche depuis
les documents lus par l'OCR, jamais par-dessus une saisie."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import TenantId
from axelcompta.ocr.documents import STATUTS
from axelcompta.ocr.passage import completer_fiche
from axelcompta.ocr.reprise import DECLARATION_TVA, EMPRUNT
from axelcompta.tenants.fiches_import import document_import, nouvelle_fiche

T = TenantId("T")
LE = datetime(2026, 11, 19, tzinfo=UTC)
PDF = b"%PDF-1.4"


def _m(**valeurs: int) -> list[dict[str, object]]:
    return [{"nom": k, "valeur_cts": v} for k, v in valeurs.items()]


def test_les_associes_des_statuts_et_leur_part() -> None:
    lu = {
        "forme_juridique": "SAS",
        "montants": _m(capital_cts=100000, nombre_parts_total=100),
        "associes": [
            {"nom": "Konate", "prenom": "Kerfala", "parts": 60},
            {"nom": "Diallo", "prenom": "Awa", "parts": 40},
        ],
    }
    champs = STATUTS.champs_fiche(lu)
    assert champs["capital"] == "1000.00"
    assert json.loads(champs["associes"]) == [
        {"prenom": "Kerfala", "nom": "Konate", "fonction": "associe", "pourcentage": "60"},
        {"prenom": "Awa", "nom": "Diallo", "fonction": "associe", "pourcentage": "40"},
    ]
    # Plus de 100 % : la liste ne se valide pas, rien n'est recopié.
    faux = {**lu, "montants": _m(capital_cts=100000, nombre_parts_total=50)}
    assert "associes" not in STATUTS.champs_fiche(faux)


def test_le_credit_de_tva_vient_d_une_declaration_annuelle_seulement() -> None:
    ca12 = {
        "formulaire": "3517-S",
        "periode_debut": "",
        "periode_fin": "2025-09-30",
        "montants": _m(tva_nette_cts=-159400),
    }
    assert DECLARATION_TVA.champs_fiche(ca12) == {"credit_tva": "1594.00"}
    due = {**ca12, "montants": _m(tva_nette_cts=125000)}
    assert DECLARATION_TVA.champs_fiche(due) == {"credit_tva": "0.00"}
    recap = {
        "formulaire": "",
        "periode_debut": "",
        "periode_fin": "",
        "montants": _m(tva_nette_cts=-61600),
    }
    assert DECLARATION_TVA.champs_fiche(recap) == {"credit_tva": "616.00"}
    ca3 = {
        "formulaire": "CA3",
        "periode_debut": "2025-08-01",
        "periode_fin": "2025-08-31",
        "montants": _m(tva_nette_cts=-20000),
    }
    assert DECLARATION_TVA.champs_fiche(ca3) == {}
    assert DECLARATION_TVA.exercice_source_seul


ECHEANCES = [
    {
        "date": f"2025-{mois:02d}-05",
        "echeance_cts": 50000,
        "capital_cts": 45000,
        "interets_cts": 5000,
        "assurance_cts": 0,
        "capital_restant_cts": 1000000 - 45000 * mois,
    }
    for mois in range(1, 13)
]
EMPRUNT_LU = {
    "preteur": "BRED",
    "date_debut": "2025-01-05",
    "taux": "4 %",
    "montants": _m(capital_emprunte_cts=1000000),
    "echeances": ECHEANCES,
}


def test_le_capital_restant_du_a_la_cloture_de_l_exercice_source() -> None:
    assert EMPRUNT.champs_a_la_cloture(EMPRUNT_LU, date(2025, 9, 30)) == {
        "emprunts": "BRED : capital restant dû 5 950,00 € au 30/09/2025 (tableau d'amortissement)."
    }
    assert EMPRUNT.champs_a_la_cloture(EMPRUNT_LU, date(2024, 12, 31)) == {}


def test_l_emprunt_rempli_la_fiche_a_la_cloture_source_jamais_sur_une_saisie() -> None:
    fiche = replace(
        nouvelle_fiche("f", T, "K", "K", "", "b", LE),
        champs={"date_creation": "2022-10-01", "cloture": "30/09"},
    )
    tableau = replace(
        document_import("e", fiche, "reprise:emprunt", "pret.pdf", "", PDF, "b", LE),
        statut_traitement="traite",
        donnees={"lu": EMPRUNT_LU},
    )
    complete = completer_fiche(fiche, [tableau], tableau, LE)
    assert complete is not None
    assert complete.champs["emprunts"].startswith("BRED : capital restant dû 5 950,00 €")
    saisie = replace(fiche, champs={**fiche.champs, "emprunts": "Aucun"})
    assert completer_fiche(saisie, [tableau], tableau, LE) is None
    a_verifier = replace(tableau, statut_traitement="a_traiter")
    assert completer_fiche(fiche, [a_verifier], a_verifier, LE) is None
