from __future__ import annotations

import dataclasses
import re
from datetime import date

import pytest

from axelcompta.categorize.ml_fallback import Calibration
from axelcompta.categorize.models import Etage
from axelcompta.categorize.rules_and_ml import (
    CATEGORIE_PAR_DEFAUT,
    SEUIL_PROPOSITION_ML,
    RulesAndMlPipeline,
)
from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.packs.vtc_demo import RegleCategorisation, charger_regles

REGLES_TEST = (RegleCategorisation(re.compile(r"total|esso", re.IGNORECASE), "carburant", "haute"),)


def _transaction(libelle: str, montant_cts: int = -4_500) -> NormalizedTransaction:
    return NormalizedTransaction(
        id=TransactionId("tx1"),
        dossier_id=DossierId("d1"),
        date=date(2026, 9, 3),
        montant_cts=montant_cts,
        libelle=libelle,
        source_provider="fixture",
        raw_payload={},
    )


def test_une_regle_qui_matche_gagne_avec_sa_confiance() -> None:
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST)
    proposition = pipeline.categoriser(DossierId("d1"), _transaction("CB TOTAL A6"))
    assert proposition.categorie == "carburant"
    assert proposition.etage is Etage.REGLE
    assert proposition.confiance == 0.95


def test_sans_regle_ni_modele_tombe_en_categorie_par_defaut() -> None:
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST)
    proposition = pipeline.categoriser(DossierId("d1"), _transaction("VIREMENT INCONNU"))
    assert proposition.categorie == CATEGORIE_PAR_DEFAUT
    assert proposition.etage is Etage.ML
    assert proposition.confiance == 0.0


class _ModeleBidon:
    """Modèle sklearn minimal (predict/predict_proba) pour tester le
    branchement, sans dépendre du vrai .joblib (gitignoré)."""

    classes_ = ("carburant", "peage_stationnement")

    def predict(self, x: list[str]) -> list[str]:
        return ["peage_stationnement" for _ in x]

    def predict_proba(self, x: list[str]) -> list[list[float]]:
        return [[0.1, 0.87] for _ in x]


def test_sans_regle_avec_modele_utilise_la_prediction_ml() -> None:
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST, modele=_ModeleBidon())
    proposition = pipeline.categoriser(DossierId("d1"), _transaction("SANEF A10"))
    assert proposition.categorie == "peage_stationnement"
    assert proposition.etage is Etage.ML
    assert proposition.confiance == pytest.approx(0.87)


class _ModeleHesitant:
    classes_ = ("carburant", "peage_stationnement")

    def predict(self, x: list[str]) -> list[str]:
        return ["peage_stationnement" for _ in x]

    def predict_proba(self, x: list[str]) -> list[list[float]]:
        return [[0.3, SEUIL_PROPOSITION_ML - 0.01] for _ in x]


def test_sous_le_seuil_le_modele_ne_propose_rien() -> None:
    """Mieux vaut « pas de proposition » qu'une catégorie fausse à confirmer
    d'un geste. La confiance du modèle reste tracée."""
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST, modele=_ModeleHesitant())
    proposition = pipeline.categoriser(DossierId("d1"), _transaction("SANEF A10"))
    assert proposition.categorie == CATEGORIE_PAR_DEFAUT
    assert proposition.etage is Etage.ML
    assert proposition.confiance == pytest.approx(SEUIL_PROPOSITION_ML - 0.01)


def test_une_regle_de_sens_contraire_est_sautee() -> None:
    """« BOLT » sur un paiement sortant n'est pas une recette plateforme."""
    regles = (
        RegleCategorisation(re.compile(r"bolt", re.IGNORECASE), "recettes_plateformes", "haute"),
    )
    pipeline = RulesAndMlPipeline(regles=regles)
    sortie = pipeline.categoriser(DossierId("d1"), _transaction("BOLT.EU/O/2603", -1_500))
    assert sortie.categorie == CATEGORIE_PAR_DEFAUT
    entree = pipeline.categoriser(DossierId("d1"), _transaction("BOLT OPERATIONS", 42_000))
    assert entree.categorie == "recettes_plateformes"


def test_un_modele_calibre_propose_et_fixe_le_seuil_par_categorie() -> None:
    """Sous le seuil de proposition calibré, rien ; au-dessus, la proposition
    porte le seuil d'imputation de sa catégorie."""
    calibration = Calibration(
        x=(0.0, 1.0),
        y=(0.0, 1.0),
        seuil_proposition=0.9,
        seuil_imputation=0.95,
        classes_imputables=frozenset({"peage_stationnement"}),
    )
    pipeline = RulesAndMlPipeline(regles=(), modele=_ModeleBidon(), calibration=calibration)
    proposition = pipeline.categoriser(DossierId("d1"), _transaction("SANEF A10"))
    assert proposition.categorie == CATEGORIE_PAR_DEFAUT  # 0,87 < 0,9
    calibration_basse = dataclasses.replace(calibration, seuil_proposition=0.5)
    pipeline = RulesAndMlPipeline(regles=(), modele=_ModeleBidon(), calibration=calibration_basse)
    proposition = pipeline.categoriser(DossierId("d1"), _transaction("SANEF A10"))
    assert proposition.categorie == "peage_stationnement"
    assert proposition.seuil_imputation == 0.95


class _ModeleCompteur(_ModeleBidon):
    """Compte les lignes qui arrivent jusqu'au modèle."""

    def __init__(self) -> None:
        self.lignes = 0

    def predict_proba(self, x: list[str]) -> list[list[float]]:
        self.lignes += len(x)
        return super().predict_proba(x)


def _transaction_numero(
    identifiant: str, libelle: str, montant_cts: int = -4_500
) -> NormalizedTransaction:
    return dataclasses.replace(_transaction(libelle, montant_cts), id=TransactionId(identifiant))


def test_une_operation_deja_vue_ne_repasse_ni_par_les_regles_ni_par_le_modele() -> None:
    modele = _ModeleCompteur()
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST, modele=modele)
    premiere = pipeline.categoriser_lot(DossierId("d1"), [_transaction("SANEF A10")])
    assert modele.lignes == 1
    seconde = pipeline.categoriser_lot(DossierId("d2"), [_transaction_numero("tx2", "SANEF A10")])
    assert modele.lignes == 1
    assert seconde == [
        dataclasses.replace(
            premiere[0], dossier_id=DossierId("d2"), transaction_id=TransactionId("tx2")
        )
    ]


def test_le_meme_libelle_n_est_calcule_qu_une_fois_dans_un_lot() -> None:
    modele = _ModeleCompteur()
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST, modele=modele)
    lot = [_transaction_numero(f"tx{i}", "SANEF A10") for i in range(3)]
    propositions = pipeline.categoriser_lot(DossierId("d1"), lot)
    assert modele.lignes == 1
    assert [p.transaction_id for p in propositions] == ["tx0", "tx1", "tx2"]
    assert {p.categorie for p in propositions} == {"peage_stationnement"}


def test_un_autre_montant_est_recalcule() -> None:
    """Le sens du montant peut changer la proposition : il fait partie de la clé."""
    modele = _ModeleCompteur()
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST, modele=modele)
    pipeline.categoriser_lot(DossierId("d1"), [_transaction("SANEF A10", -4_500)])
    pipeline.categoriser_lot(DossierId("d1"), [_transaction("SANEF A10", 4_500)])
    assert modele.lignes == 2


def test_avec_ou_sans_memoire_les_propositions_sont_les_memes() -> None:
    lot = [
        _transaction_numero("a", "CB TOTAL A6"),
        _transaction_numero("b", "SANEF A10"),
        _transaction_numero("c", "SANEF A10"),
        _transaction_numero("d", "CB TOTAL A6", -9_000),
    ]
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST, modele=_ModeleBidon())
    attendu = [
        RulesAndMlPipeline(regles=REGLES_TEST, modele=_ModeleBidon()).categoriser(
            DossierId("d1"), transaction
        )
        for transaction in lot
    ]
    assert pipeline.categoriser_lot(DossierId("d1"), lot) == attendu
    assert pipeline.categoriser_lot(DossierId("d1"), lot) == attendu


def test_la_memoire_est_bornee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("axelcompta.categorize.rules_and_ml.CAPACITE_MEMOIRE", 2)
    modele = _ModeleCompteur()
    pipeline = RulesAndMlPipeline(regles=REGLES_TEST, modele=modele)
    for libelle in ("SANEF A10", "SANEF A11", "SANEF A12"):
        pipeline.categoriser_lot(DossierId("d1"), [_transaction(libelle)])
    assert modele.lignes == 3
    pipeline.categoriser_lot(DossierId("d1"), [_transaction("SANEF A10")])  # oubliée
    assert modele.lignes == 4
    pipeline.categoriser_lot(DossierId("d1"), [_transaction("SANEF A12")])  # encore là
    assert modele.lignes == 4


def _tx(
    id_: str,
    libelle: str,
    montant_cts: int,
    *,
    compte: str | None = None,
    type_operation: str | None = None,
    categorie_banque: str | None = None,
) -> NormalizedTransaction:
    return dataclasses.replace(
        _transaction(libelle, montant_cts),
        id=TransactionId(id_),
        compte_bancaire=compte,
        type_operation=type_operation,
        categorie_banque=categorie_banque,
    )


def test_deux_jambes_d_un_virement_interne_vont_au_580_avant_toute_regle() -> None:
    """AXE-826 : « carburant » sur un virement entre enveloppes n'est pas un plein."""
    pipeline = RulesAndMlPipeline(regles=charger_regles())
    sortie = _tx("s", "carburant", -1_500, compte="pro")
    entree = _tx("e", "carburant", 1_500, compte="carburant")
    plein = _tx("p", "TOTAL", -1_500, compte="pro")

    resultat = {
        p.transaction_id: p
        for p in pipeline.categoriser_lot(DossierId("d1"), [sortie, entree, plein])
    }

    assert resultat["s"].categorie == resultat["e"].categorie == "virement_interne"
    assert resultat["s"].etage is Etage.REGLE and resultat["s"].confiance == 0.95
    assert resultat["p"].categorie == "carburant"


def test_une_regle_de_paiement_ne_s_applique_pas_a_un_virement() -> None:
    pipeline = RulesAndMlPipeline(regles=charger_regles())
    virement = _tx("v", "cotisation URSSAF", -2_100, type_operation="transfer")
    prelevement = _tx("p", "PRLV URSSAF", -2_100, type_operation="direct_debit")

    resultat = pipeline.categoriser_lot(DossierId("d1"), [virement, prelevement])

    assert resultat[0].categorie == CATEGORIE_PAR_DEFAUT
    assert resultat[1].categorie == "charges_sociales_impots"


def test_la_categorie_de_la_banque_propose_quand_le_modele_s_abstient() -> None:
    pipeline = RulesAndMlPipeline(
        regles=REGLES_TEST,
        categories_banque={"251": "peage_stationnement", "230": "recettes_plateformes"},
    )
    parking = _tx("a", "LIBELLE OBSCUR", -700, categorie_banque="251")
    mauvais_sens = _tx("b", "AUTRE OBSCUR", -700, categorie_banque="230")
    inconnue = _tx("c", "ENCORE OBSCUR", -700, categorie_banque="999")

    resultat = pipeline.categoriser_lot(DossierId("d1"), [parking, mauvais_sens, inconnue])

    assert (resultat[0].categorie, resultat[0].etage) == ("peage_stationnement", Etage.BANQUE)
    assert resultat[0].confiance == 0.5
    assert resultat[1].categorie == CATEGORIE_PAR_DEFAUT  # recette sur une sortie : refusée
    assert resultat[2].categorie == CATEGORIE_PAR_DEFAUT


def test_une_regle_l_emporte_sur_la_categorie_de_la_banque() -> None:
    pipeline = RulesAndMlPipeline(
        regles=REGLES_TEST, categories_banque={"273": "repas_et_receptions"}
    )
    proposition = pipeline.categoriser(
        DossierId("d1"), _tx("a", "TOTAL", -6_000, categorie_banque="273")
    )
    assert (proposition.categorie, proposition.etage) == ("carburant", Etage.REGLE)


def test_la_memoire_distingue_type_d_operation_et_categorie_de_banque() -> None:
    """Même libellé, même montant, signaux différents : deux résultats."""
    pipeline = RulesAndMlPipeline(regles=charger_regles(), categories_banque={"87": "carburant"})
    carte = _tx("a", "carburant", -1_500, type_operation="card")
    virement = _tx("b", "carburant", -1_500, type_operation="transfer")
    assert pipeline.categoriser(DossierId("d1"), carte).categorie == "carburant"
    assert pipeline.categoriser(DossierId("d1"), virement).categorie == CATEGORIE_PAR_DEFAUT
