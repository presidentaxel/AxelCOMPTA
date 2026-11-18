"""AXE-943 : Kbis, statuts, lettre de l'ancien comptable, classement."""

from __future__ import annotations

from axelcompta.ocr.categories import Contexte
from axelcompta.ocr.documents import CLASSEMENT, KBIS, LETTRE_COMPTABLE, STATUTS

KBIS_LU = {
    "siren": "908771033",
    "denomination": "KERFICE SERVICE",
    "forme_juridique": "SASU",
    "siege": "1 rue de Paris 75001 Paris",
    "code_naf": "4932Z",
    "date_immatriculation": "2021-12-20",
    "montants": [{"nom": "capital_cts", "valeur_cts": 100000}],
}


def test_un_kbis_de_la_societe_est_accepte() -> None:
    assert KBIS.controler(KBIS_LU, Contexte(siren="908771033")) == []
    assert KBIS.resumer(KBIS_LU).startswith("Kbis lu : KERFICE SERVICE, SASU, SIREN 908771033")


def test_un_kbis_d_une_autre_societe_va_a_un_humain() -> None:
    (erreur,) = KBIS.controler(KBIS_LU, Contexte(siren="552100554"))
    assert "autre société" in erreur


def test_des_statuts_dont_les_parts_ne_tombent_pas_juste() -> None:
    lu = {
        "forme_juridique": "SAS",
        "montants": [
            {"nom": "capital_cts", "valeur_cts": 100000},
            {"nom": "nombre_parts_total", "valeur_cts": 100},
        ],
        "associes": [
            {"nom": "A", "prenom": "B", "parts": 60},
            {"nom": "C", "prenom": "D", "parts": 30},
        ],
    }
    assert STATUTS.controler(lu, Contexte()) == [
        "Les associés ont 90 parts, les statuts en comptent 100."
    ]
    lu["associes"][1]["parts"] = 40  # type: ignore[index]
    assert STATUTS.controler(lu, Contexte()) == []


def test_une_lettre_sans_cabinet() -> None:
    assert LETTRE_COMPTABLE.controler({"cabinet": ""}, Contexte()) == ["Cabinet : non lu."]


def test_le_classement_refuse_autre_et_une_annee_folle() -> None:
    assert (
        CLASSEMENT.controler({"type_document": "liasse", "annee_exercice": "2025"}, Contexte())
        == []
    )
    assert CLASSEMENT.controler({"type_document": "autre", "annee_exercice": ""}, Contexte())
    assert CLASSEMENT.controler({"type_document": "kbis", "annee_exercice": "1890"}, Contexte())


def test_le_schema_n_a_aucun_champ_a_deux_types() -> None:
    """L'API refuse un schéma avec trop de champs « texte ou null »."""
    schema = STATUTS.schema()
    assert "anyOf" not in str(schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
