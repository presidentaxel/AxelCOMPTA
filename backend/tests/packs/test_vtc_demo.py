from __future__ import annotations

from axelcompta.packs.vtc_demo import (
    charger_compte_par_categorie,
    charger_regles,
    nature_depuis_compte,
)


def test_charge_les_regles_du_pack_reel() -> None:
    regles = charger_regles()
    assert len(regles) > 0
    assert any(r.categorie == "carburant" for r in regles)
    assert all(r.confiance in {"haute", "moyenne", "basse"} for r in regles)


def test_une_regle_matche_bien_un_libelle_carburant() -> None:
    regles = charger_regles()
    regle_carburant = next(r for r in regles if r.categorie == "carburant")
    assert regle_carburant.motif.search("CB TOTAL ACCESS A6 03/09")


def test_toutes_les_regles_sont_insensibles_a_la_casse() -> None:
    # Bug trouvé en testant sur un vrai dossier complet (doc 17 §2,
    # 2026-09-05) : seule la règle "carburant" avait (?i) inline dans le
    # CSV du pack ; les 11 autres — dont recettes_plateformes, le revenu
    # principal d'un chauffeur — ne matchaient jamais un libellé bancaire
    # en MAJUSCULES (le format usuel). Sur un vrai dossier, ça faisait
    # tomber le CA à quelques centaines d'euros au lieu de dizaines de
    # milliers. Corrigé en forçant re.IGNORECASE au chargement.
    regles = charger_regles()
    regle_recettes = next(r for r in regles if r.categorie == "recettes_plateformes")
    assert regle_recettes.motif.search("FAE UBER POP COMMIS & COURTAGES SUR VENTES")
    assert regle_recettes.motif.search("REGUL UBER COMMIS & COURTAGES SUR VENTES")


def test_charge_un_compte_par_categorie() -> None:
    comptes = charger_compte_par_categorie()
    assert comptes["carburant"].startswith("6")


def test_recettes_plateformes_est_corrigee_vers_un_vrai_compte_de_produit() -> None:
    # Bug trouvé en testant sur un vrai dossier complet : le mapping brut
    # donne 418 (créance temporaire, hors compte de résultat) en premier —
    # ça exclurait silencieusement le revenu principal d'un chauffeur du CA.
    comptes = charger_compte_par_categorie()
    assert comptes["recettes_plateformes"] == "706"
    assert nature_depuis_compte(comptes["recettes_plateformes"]) == "produit"


def test_honoraires_et_charges_sociales_sont_corriges_vers_des_comptes_de_charge() -> None:
    comptes = charger_compte_par_categorie()
    assert nature_depuis_compte(comptes["honoraires_comptable_juridique"]) == "charge"
    assert nature_depuis_compte(comptes["charges_sociales_impots"]) == "charge"


def test_immobilisation_vehicule_va_en_materiel_de_transport() -> None:
    # Hors compte de résultat (un achat de véhicule s'amortit), et en 2182
    # plutôt que 218 : la 2033-C le range en matériel de transport (AXE-802).
    comptes = charger_compte_par_categorie()
    assert comptes["immobilisation_vehicule"] == "2182"
    assert nature_depuis_compte(comptes["immobilisation_vehicule"]) == "autre"


def test_nature_depuis_compte() -> None:
    assert nature_depuis_compte("6061") == "charge"
    assert nature_depuis_compte("706") == "produit"
    assert nature_depuis_compte("101") == "autre"
