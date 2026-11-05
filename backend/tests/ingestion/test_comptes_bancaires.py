from __future__ import annotations

from datetime import UTC, datetime

import pytest

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_bancaires import (
    NOMBRE_MAX_COMPTES,
    CompteBancaireMemoire,
    CompteReleve,
    TropDeComptesBancaires,
    compte_comptable_suivant,
    compte_de,
    comptes_releves,
    relever_comptes,
)

DOSSIER = DossierId("DIGI_22755")
AUTRE = DossierId("DIGI_86930")
LE = datetime(2026, 11, 5, 4, 12, tzinfo=UTC)


def test_les_sous_comptes_se_numerotent_dans_l_ordre_d_apparition() -> None:
    depot = CompteBancaireMemoire()
    assert compte_de(depot, DOSSIER, "67078894") == "5121"
    assert compte_de(depot, DOSSIER, "67078892") == "5122"
    assert compte_de(depot, DOSSIER, "67078894") == "5121"  # stable
    assert compte_de(depot, AUTRE, "67115201") == "5121"  # propre à chaque dossier


def test_une_banque_inconnue_va_au_512() -> None:
    depot = CompteBancaireMemoire()
    assert compte_de(depot, DOSSIER, None) == "512"
    assert depot.lister(DOSSIER) == ()


def test_le_numero_suivant_comble_les_trous_et_passe_a_deux_chiffres() -> None:
    assert compte_comptable_suivant([]) == "5121"
    assert compte_comptable_suivant(["5121", "5123"]) == "5122"
    neuf = [f"512{i}" for i in range(1, 10)]
    assert compte_comptable_suivant(neuf) == "51210"


def test_au_dela_de_la_limite_on_s_arrete() -> None:
    pris = [f"512{i}" for i in range(1, NOMBRE_MAX_COMPTES + 1)]
    with pytest.raises(TropDeComptesBancaires):
        compte_comptable_suivant(pris)


def test_la_liste_est_triee_par_numero() -> None:
    depot = CompteBancaireMemoire()
    for i in range(12):
        compte_de(depot, DOSSIER, f"acc{i}")
    numeros = [c.compte_comptable for c in depot.lister(DOSSIER)]
    assert numeros[:3] == ["5121", "5122", "5123"]
    assert numeros[-3:] == ["51210", "51211", "51212"]


def test_le_releve_digifactory_donne_nom_et_solde() -> None:
    payload = {
        "67078853": {"id": "67078853", "name": "Compte Courant", "balance": 733.49},
        "67078894": {"id": 67078894, "name": " Compte PRO ", "balance": "1.1"},
        "sans_id": {"name": "ignoré"},
        "solde_illisible": {"id": "x", "name": "", "balance": "n/a"},
    }
    releves = {r.identifiant: r for r in comptes_releves(payload)}
    assert set(releves) == {"67078853", "67078894", "x"}
    assert releves["67078853"] == CompteReleve("67078853", "Compte Courant", 73_349)
    assert releves["67078894"].nom == "Compte PRO"
    assert releves["67078894"].solde_cts == 110
    assert releves["x"].nom is None
    assert releves["x"].solde_cts is None


@pytest.mark.parametrize("payload", [None, "texte", 3, [1, "a"], {"a": None}])
def test_un_releve_illisible_ne_donne_aucun_compte(payload: object) -> None:
    assert comptes_releves(payload) == ()


def test_le_releve_accepte_une_liste() -> None:
    releves = comptes_releves([{"id": "a", "balance": -12.5}])
    assert releves == (CompteReleve("a", None, -1_250),)


def test_relever_attribue_les_numeros_et_garde_le_solde() -> None:
    depot = CompteBancaireMemoire()
    compte_de(depot, DOSSIER, "67078894")  # vu d'abord dans une transaction
    comptes = relever_comptes(
        depot,
        DOSSIER,
        [CompteReleve("67078853", "Compte Courant", 73_349), CompteReleve("67078894", None, 110)],
        LE,
    )
    par_id = {c.identifiant: c for c in comptes}
    assert par_id["67078894"].compte_comptable == "5121"
    assert par_id["67078853"].compte_comptable == "5122"
    assert par_id["67078853"].nom == "Compte Courant"
    assert par_id["67078894"].solde_banque_cts == 110
    assert par_id["67078894"].solde_releve_le == LE


def test_un_releve_sans_nom_ne_l_efface_pas() -> None:
    depot = CompteBancaireMemoire()
    relever_comptes(depot, DOSSIER, [CompteReleve("a", "Compte PRO", 100)], LE)
    relever_comptes(depot, DOSSIER, [CompteReleve("a", None, 200)], LE)
    (compte,) = depot.lister(DOSSIER)
    assert compte.nom == "Compte PRO"
    assert compte.solde_banque_cts == 200


def test_relever_un_compte_inconnu_ne_fait_rien() -> None:
    depot = CompteBancaireMemoire()
    depot.relever(DOSSIER, CompteReleve("absent", "x", 1), LE)
    assert depot.lister(DOSSIER) == ()
