"""2057-SD millésime 2026 : état des échéances des créances et des dettes à
la clôture (notice 2032-NOT-SD), depuis la balance.

Les écritures n'ont pas de date d'échéance (AXE-960). Règle proposée, à
faire valider par l'expert-comptable (AXE-815) :

* tout est à un an au plus, sauf les emprunts ;
* emprunts (VH, 7Y, 7Z) et dettes financières diverses (8A) : montant brut
  seul, colonnes d'échéance laissées à saisir, faute d'échéancier ;
* un découvert bancaire (512 créditeur) est un emprunt à un an au plus à
  l'origine (VG).

Clés : le code de la ligne pour le montant brut, `<code>.1AN` pour la part à
un an au plus quand le formulaire n'a pas de code pour cette colonne. Les
créances immobilisées ont leurs codes (UM, UR, UV).
"""

from __future__ import annotations

from collections import defaultdict

from .impot_societes import arrondir_euros
from .liasse_2033 import Balance
from .rubriques_2033 import rubrique

# Solde débiteur → ligne de l'état des créances.
CREANCES: dict[str, str] = {
    "267": "UL",
    "268": "UL",
    "274": "UP",
    "275": "UT",
    "276": "UT",
    "416": "VA",
    "411": "UX",
    "413": "UX",
    "418": "UX",
    "42": "UY",
    "43": "UZ",
    "444": "VM",
    "445": "VB",
    "442": "VN",
    "447": "VN",
    "44": "VP",
    "45": "VC",
    "486": "VS",
    "4": "VR",
}
# Solde créditeur → ligne de l'état des dettes.
DETTES: dict[str, str] = {
    "51": "VG",
    "164": "VH",
    "16": "8A",
    "17": "8A",
    "401": "8B",
    "403": "8B",
    "408": "8B",
    "404": "8J",
    "405": "8J",
    "42": "8C",
    "43": "8D",
    "444": "8E",
    "445": "VW",
    "44": "VQ",
    "45": "VI",
    "487": "8L",
    "4": "8K",
}
# Créances immobilisées : code de la colonne « à un an au plus ».
UN_AN_CODE = {"UL": "UM", "UP": "UR", "UT": "UV"}
A_SAISIR = frozenset({"VH", "7Y", "7Z", "8A"})


def echeances_2057(balance: Balance) -> dict[str, int]:
    """En euros entiers ; totaux sur les lignes déjà arrondies."""
    centimes: dict[str, int] = defaultdict(int)
    for compte, solde in balance.items():
        if solde > 0:
            code = rubrique(compte, CREANCES)
            montant = solde
        elif solde < 0:
            code = rubrique(compte, DETTES)
            montant = -solde
        else:
            continue
        if code is not None:
            centimes[code] += montant
    lignes = {code: arrondir_euros(valeur) for code, valeur in centimes.items()}
    cases = dict(lignes)
    for code, brut in lignes.items():
        if code in A_SAISIR:
            continue
        cases[UN_AN_CODE.get(code, f"{code}.1AN")] = brut
    creances = [code for code in lignes if code in set(CREANCES.values())]
    dettes = [code for code in lignes if code in set(DETTES.values())]
    cases["VT"] = sum(lignes[code] for code in creances)
    cases["VU"] = cases["VT"]
    cases["VY"] = sum(lignes[code] for code in dettes)
    cases["VZ"] = sum(lignes[code] for code in dettes if code not in A_SAISIR)
    return cases
