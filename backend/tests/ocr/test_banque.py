"""AXE-943 : relevés de compte et RIB lus par l'OCR."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import TenantId
from axelcompta.couverture_bancaire_fiche import couverture_de_la_fiche
from axelcompta.ocr.banque import RELEVE_BANCAIRE, RIB
from axelcompta.ocr.categories import Contexte
from axelcompta.releves_en_compta import operations_lues
from axelcompta.tenants.fiches_import import document_import, modifier, nouvelle_fiche

LE = datetime(2026, 11, 18, tzinfo=UTC)
RELEVE = {
    "banque": "Société Générale",
    "titulaire": "SYBD",
    "iban": "FR7630006000011234567890189",
    "periode_debut": "2025-11-01",
    "periode_fin": "2025-11-29",
    "montants": [
        {"nom": "solde_debut_cts", "valeur_cts": -22704},
        {"nom": "solde_fin_cts", "valeur_cts": 55074},
    ],
    "operations": [
        {"date": "2025-11-03", "libelle": "VIR UBER", "montant_cts": 90000},
        {"date": "2025-11-10", "libelle": "CB TOTAL", "montant_cts": -12222},
    ],
}


def test_un_releve_prouve_par_ses_operations() -> None:
    assert RELEVE_BANCAIRE.controler(RELEVE, Contexte()) == []
    donnees = RELEVE_BANCAIRE.donnees(RELEVE)
    assert donnees["type"] == "releve"
    assert donnees["mouvements"] == [["2025-11-03", 90000], ["2025-11-10", -12222]]


def test_une_operation_oubliee_se_voit_au_centime() -> None:
    oublie = {**RELEVE, "operations": RELEVE["operations"][:1]}  # type: ignore[index]
    (erreur,) = RELEVE_BANCAIRE.controler(oublie, Contexte())
    assert erreur.endswith("(écart −122,22 €).")


def test_un_rib_et_sa_cle() -> None:
    bon = {
        "titulaire": "SYBD",
        "iban": "FR76 3000 6000 0112 3456 7890 189",
        "bic": "",
        "banque": "",
    }
    assert RIB.controler(bon, Contexte()) == []
    assert RIB.controler({**bon, "iban": "FR7630006000011234567890188"}, Contexte()) == [
        "IBAN lu invalide (FR7630006000011234567890188)."
    ]


def test_le_releve_lu_prouve_sa_periode_dans_la_couverture() -> None:
    """Ses deux soldes sont des preuves : la période est complète, jours calmes compris."""
    fiche = modifier(
        nouvelle_fiche("f", TenantId("T"), "Drame", "B", "", "b", LE),
        {"date_creation": "2025-01-01", "cloture": "31/12"},
        "b",
        LE,
    )
    document = document_import(
        "sg", fiche, "banque:releve_bancaire", "SG 11-2025.pdf", "", b"%PDF", "b", LE
    )
    lu = replace(
        document,
        statut_traitement="traite",
        donnees={**RELEVE_BANCAIRE.donnees(RELEVE), "lu": RELEVE},
    )
    (compte,) = couverture_de_la_fiche(fiche, [lu], [], [], date(2025, 12, 1))
    novembre = [p for p in compte.couverture.periodes if p.debut <= date(2025, 11, 15) <= p.fin]
    assert novembre[0].etat == "complet"
    assert [(o.jour, o.montant_cts, o.libelle) for o in operations_lues(lu)] == [
        (date(2025, 11, 3), 90000, "VIR UBER"),
        (date(2025, 11, 10), -12222, "CB TOTAL"),
    ]
