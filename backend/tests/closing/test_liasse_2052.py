"""2052/2053 millésime 2026 : le résultat HN est celui de la 2033-B."""

from __future__ import annotations

import dataclasses

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.liasse_2033 import compte_de_resultat
from axelcompta.closing.liasse_2033_annexes import Mouvements
from axelcompta.closing.liasse_2052 import compte_2052
from axelcompta.closing.liasse_2055 import amortissements_2055
from axelcompta.closing.liasse_2056 import provisions_2056
from axelcompta.closing.liasse_2058 import deficits_2058
from axelcompta.demo_chauffeurs_type import construire_ledger, parametres_cloture
from axelcompta.ingestion.providers.chauffeurs_demo import PROFIL_KARIM, PROFIL_YANIS

# Mêmes signes que test_liasse_2033 : solde débiteur positif.
BALANCE = {
    "706": -10_000_00,
    "781": -150_00,
    "758": -50_00,
    "6061": 3_000_00,
    "645": 2_910_00,
    "6815": 200_00,
    "661": 80_00,
    "6712": 90_00,
    "695": 400_00,
}


def test_hn_reproduit_la_ligne_310() -> None:
    lignes = compte_de_resultat(BALANCE)
    exploitation, suite = compte_2052(BALANCE)
    assert suite["HN"] == lignes["310"]
    assert exploitation["GG"] == exploitation["FR"] - exploitation["GF"]
    assert exploitation["GW"] == exploitation["GG"] + exploitation["GV"]
    assert exploitation["FG"] == 10_000 and exploitation["FI"] == 10_000
    assert exploitation["FP"] == 150 and exploitation["FQ"] == 50
    assert exploitation["GB"] == 200
    assert suite["HK"] == 400 and suite["HH"] == 90


def test_les_chauffeurs_bouclent_avec_le_bilan() -> None:
    for profil in (PROFIL_KARIM, PROFIL_YANIS):
        ledger, _ = construire_ledger(profil)
        parametres = dataclasses.replace(parametres_cloture(profil), regime_liasse="2050")
        liasse = ClotureSimplifieeService(ledger).cloturer(profil.dossier_id, "2025", parametres)
        assert liasse.cases["2053.HN"] == liasse.cases["2033B.310"]
        assert liasse.cases["2053.HN"] == liasse.cases["2050.DI"]
        assert liasse.cases["2052.GG"] == liasse.cases["2052.FR"] - liasse.cases["2052.GF"]
        assert liasse.cases["2058A.XN"] == liasse.cases["2033B.370"]
        if "2033C.496" in liasse.cases:
            assert liasse.cases["2054.0L"] == liasse.cases["2033C.496"]
            assert liasse.cases["2054.0L"] == (
                liasse.cases["2054.0G"] + liasse.cases["2054.0J"] - liasse.cases["2054.0K"]
            )
        if "2033C.576" in liasse.cases:
            assert liasse.cases["2055.0R"] == liasse.cases["2033C.576"]
            assert liasse.cases["2055.0R"] == (
                liasse.cases["2055.0N"] + liasse.cases["2055.0P"] - liasse.cases["2055.0Q"]
            )
        assert liasse.cases["2058B.YJ"] == liasse.cases["2058A.XO"]
        assert liasse.cases["2058B.YK"] == liasse.cases["2033D.870"]


def test_une_provision_pour_risques_boucle() -> None:
    mouvements = Mouvements(ouverture={"151": -1_000_00, "2815": -400_00}, debits={}, credits={})
    assert provisions_2056(mouvements) == {"7C": 1_000, "UB": 0, "UC": 0, "UD": 1_000}
    assert amortissements_2055({"570": 400, "572": 50, "574": 0, "576": 450})["0R"] == 450
    assert deficits_2058({"982": 80, "983": 30, "984": 50, "860": 0, "870": 50}) == {
        "K4": 80,
        "K4bis": 0,
        "K5": 30,
        "K6": 50,
        "YJ": 0,
        "YK": 50,
    }
