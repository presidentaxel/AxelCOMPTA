"""AXE-943 : la section Reprise comptable et ses contrôles."""

from __future__ import annotations

from axelcompta.ocr.categories import Contexte
from axelcompta.ocr.reprise import (
    BALANCE,
    DECLARATION_TVA,
    EMPRUNT,
    GRAND_LIVRE,
    LIASSE,
    PIECE,
)


def _m(**montants: int) -> list[dict[str, object]]:
    return [{"nom": k, "valeur_cts": v} for k, v in montants.items()]


LIASSE_LUE = {
    "siren": "908771033",
    "exercice_fin": "2022-09-30",
    "montants": _m(
        chiffre_affaires_cts=2287900,
        resultat_cts=700800,
        total_actif_cts=2114000,
        total_passif_cts=2114000,
        deficits_reportables_cts=0,
    ),
}
FEC_2022 = {"resultat_cts": 700786}


def test_une_liasse_recoupee_avec_le_fec_a_l_euro_pres() -> None:
    ctx = Contexte(siren="908771033", exercice=2022, fec=FEC_2022)
    assert LIASSE.controler(LIASSE_LUE, ctx) == []
    assert LIASSE.champs_fiche(LIASSE_LUE) == {"deficits": "0.00"}
    fausse = {**LIASSE_LUE, "montants": _m(resultat_cts=170800)}
    assert LIASSE.controler(fausse, ctx) == [
        "Résultat lu 1 708,00 €, le FEC du même exercice dit 7 007,86 €."
    ]


def test_une_liasse_rangee_dans_le_mauvais_exercice_ou_desequilibree() -> None:
    erreurs = LIASSE.controler(
        {**LIASSE_LUE, "montants": _m(resultat_cts=1, total_actif_cts=500, total_passif_cts=900)},
        Contexte(exercice=2023),
    )
    assert erreurs == [
        "Clôture lue 2022-09-30, le document est rangé en 2023.",
        "Actif 5,00 € et passif 9,00 € ne tombent pas juste.",
    ]


def test_une_balance_dont_les_soldes_se_compensent() -> None:
    comptes = [
        {"compte": "512000", "libelle": "Banque", "solde_cts": 54472},
        {"compte": "101300", "libelle": "Capital", "solde_cts": -50000},
        {"compte": "120000", "libelle": "Résultat", "solde_cts": -4472},
    ]
    lu = {"siren": "", "exercice_fin": "2022-09-30", "comptes": comptes, "montants": []}
    assert BALANCE.controler(lu, Contexte()) == []
    assert BALANCE.donnees(lu) == {
        "soldes_cts": {"512000": 54472, "101300": -50000, "120000": -4472}
    }
    comptes[0]["solde_cts"] = 64472
    assert BALANCE.controler(lu, Contexte()) == [
        "Les soldes ne se compensent pas : écart de 100,00 €."
    ]


def test_un_grand_livre_equilibre() -> None:
    lu = {
        "siren": "",
        "exercice_debut": "",
        "exercice_fin": "",
        "montants": _m(total_debit_cts=5, total_credit_cts=5),
    }
    assert GRAND_LIVRE.controler(lu, Contexte()) == []


def test_une_ca12_dont_la_nette_est_le_solde_apres_acomptes() -> None:
    lu = {
        "siren": "",
        "formulaire": "CA12",
        "periode_debut": "2023-07-01",
        "periode_fin": "2024-06-30",
        "montants": _m(
            tva_collectee_cts=794600,
            tva_deductible_cts=563300,
            acomptes_cts=140800,
            tva_nette_cts=90500,
        ),
    }
    assert DECLARATION_TVA.controler(lu, Contexte()) == []
    lu["montants"] = _m(tva_collectee_cts=794600, tva_deductible_cts=563300, tva_nette_cts=90500)
    assert DECLARATION_TVA.controler(lu, Contexte())


def test_un_recapitulatif_de_tva_sans_periode_rangee_sur_un_exercice() -> None:
    # « declaration-tva KERFICE SERVICE 2023.pdf » : les montants, ni SIREN ni période.
    lu = {
        "siren": "",
        "formulaire": "",
        "periode_debut": "",
        "periode_fin": "",
        "montants": _m(tva_collectee_cts=635500, tva_deductible_cts=697100, tva_nette_cts=-61600),
    }
    assert DECLARATION_TVA.controler(lu, Contexte(exercice=2023)) == []
    assert DECLARATION_TVA.resumer(lu) == (
        "Déclaration de TVA lue : période non imprimée, celle de l'exercice, nette −616,00 €."
    )
    # En vrac, sans exercice, la période reste obligatoire ; l'arithmétique aussi.
    assert DECLARATION_TVA.controler(lu, Contexte()) == ["Fin de période : non lue."]
    faux = {
        **lu,
        "montants": _m(tva_collectee_cts=635500, tva_deductible_cts=697100, tva_nette_cts=61600),
    }
    assert DECLARATION_TVA.controler(faux, Contexte(exercice=2023))


def test_une_piece_ht_tva_ttc() -> None:
    lu = {
        "emetteur": "TotalEnergies",
        "date_piece": "2025-03-02",
        "numero": "",
        "nature": "achat",
        "objet": "carburant",
        "montants": _m(ht_cts=5000, tva_cts=1000, ttc_cts=6000),
    }
    assert PIECE.controler(lu, Contexte()) == []
    lu["montants"] = _m(ht_cts=5000, tva_cts=1000, ttc_cts=6500)
    assert PIECE.controler(lu, Contexte()) == ["HT 50,00 € + TVA 10,00 € ≠ TTC 65,00 €."]


def test_un_tableau_d_emprunt_dont_une_echeance_ne_tombe_pas_juste() -> None:
    echeance = {
        "date": "2025-01-05",
        "echeance_cts": 50000,
        "capital_cts": 45000,
        "interets_cts": 4500,
        "assurance_cts": 500,
        "capital_restant_cts": 955000,
    }
    lu = {
        "preteur": "Bred",
        "date_debut": "",
        "taux": "",
        "montants": _m(capital_emprunte_cts=1000000),
        "echeances": [echeance],
    }
    assert EMPRUNT.controler(lu, Contexte()) == []
    echeance["interets_cts"] = 4000
    assert EMPRUNT.controler(lu, Contexte()) == [
        "Échéance du 2025-01-05 : 500,00 € ≠ capital + intérêts + assurance."
    ]
