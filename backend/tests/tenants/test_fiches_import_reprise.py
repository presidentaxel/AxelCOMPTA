"""AXE-976 : la reprise comptable préremplie par le dernier FEC clos."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import TenantId
from axelcompta.tenants.fiches_import import (
    DocumentImport,
    document_import,
    modifier,
    nouvelle_fiche,
)
from axelcompta.tenants.fiches_import_reprise import champs_lus_dans_un_fec, preremplir_reprise

LE = datetime(2026, 11, 18, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 18)
FICHE = nouvelle_fiche("f", TenantId("T"), "Konate", "K", "", "b", LE)


def _fec(annee: int, soldes: dict[str, int], **autres: object) -> DocumentImport:
    document = document_import(
        f"fec-{annee}", FICHE, f"reprise:fec:{annee}", f"FEC{annee}.txt", "", b"x", "b", LE
    )
    donnees = {
        "type": "fec",
        "cloture": f"{annee}-09-30",
        "fin": f"{annee}-09-30",
        "soldes_cts": soldes,
        **autres,
    }
    return replace(document, donnees=donnees)


def test_le_dernier_fec_donne_vehicule_credit_de_tva_et_emprunt() -> None:
    fec = _fec(
        2024,
        {"2182000": 2229000, "2818200": -1000000, "4456700": 534125, "1640000": -1200000},
        immobilisations={"2182000": {"achat_le": "2022-02-09"}},
    )
    fiche = preremplir_reprise(FICHE, [fec], AUJOURD_HUI)
    assert fiche.champs["credit_tva"] == "5341.25"
    assert fiche.champs["vehicule"] == "achat"
    assert fiche.champs["vehicule_detail"] == (
        "Valeur d'origine 22 290,00 €, acheté le 09/02/2022 ; amortissements 10 000,00 €, "
        "valeur nette 12 290,00 € au 30/09/2024."
    )
    assert fiche.champs["emprunts"] == "Capital restant dû 12 000,00 € au 30/09/2024 (comptes 164)."
    assert champs_lus_dans_un_fec(fiche) == dict.fromkeys(
        ("credit_tva", "vehicule", "vehicule_detail", "emprunts"), "FEC 2024"
    )


def test_une_saisie_n_est_jamais_ecrasee_et_perd_la_mention() -> None:
    fiche = preremplir_reprise(FICHE, [_fec(2023, {"4456700": 10000})], AUJOURD_HUI)
    saisie = modifier(fiche, {"credit_tva": "250,00"}, "b", LE)
    relue = preremplir_reprise(saisie, [_fec(2024, {"4456700": 99900})], AUJOURD_HUI)
    assert relue.champs["credit_tva"] == "250.00"
    assert "credit_tva" not in champs_lus_dans_un_fec(relue)


def test_un_fec_plus_recent_remplace_la_lecture_precedente() -> None:
    premiere = preremplir_reprise(FICHE, [_fec(2023, {"4456700": 10000})], AUJOURD_HUI)
    seconde = preremplir_reprise(
        premiere, [_fec(2023, {"4456700": 10000}), _fec(2024, {"4456700": 20000})], AUJOURD_HUI
    )
    assert seconde.champs["credit_tva"] == "200.00"
    assert champs_lus_dans_un_fec(seconde)["credit_tva"] == "FEC 2024"


def test_des_loyers_de_credit_bail_sans_vehicule_a_l_actif_disent_loa() -> None:
    fiche = preremplir_reprise(FICHE, [_fec(2024, {"6122000": 540000})], AUJOURD_HUI)
    assert fiche.champs["vehicule"] == "loa"
    assert "5 400,00 €" in fiche.champs["vehicule_detail"]


def test_sans_fec_clos_rien_ne_change() -> None:
    en_cours = _fec(2027, {"4456700": 100})
    assert preremplir_reprise(FICHE, [en_cours], AUJOURD_HUI) is FICHE
    assert preremplir_reprise(FICHE, [], AUJOURD_HUI) is FICHE
