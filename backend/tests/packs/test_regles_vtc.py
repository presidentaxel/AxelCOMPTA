"""Chaque règle du pack VTC embarque ses cas (doc 05 §2.2) : un libellé
qu'elle doit reconnaître, avec la catégorie attendue de la première règle
qui matche. Une règle sans exemple fait échouer ce test.

Les exemples viennent des libellés réels vus le 2026-11-05 (MK DRIVING,
B'CARS SERVICES), réduits au nom du commerçant."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.packs.vtc_demo import (
    charger_categories_banque,
    charger_compte_par_categorie,
    charger_regles,
    plancher_de,
)
from axelcompta.workflow.synchro import COMPTE_ATTENTE, choisir_compte

# (libellé, catégorie attendue de la première règle qui matche)
EXEMPLES: tuple[tuple[str, str], ...] = (
    ("RETRAIT DAB 12/03 PARIS 11", "retrait_especes"),
    ("PRLV SEPA DGFIP TVA 03/2026", "tva_payee"),
    ("IMPOTS TVA CA3 MARS", "tva_payee"),
    ("Retrait GAB", "retrait_especes"),
    ("TOTAL", "carburant"),
    ("CB TOTAL ACCESS A6", "carburant"),
    ("SANEF AUTOROUTE SENLIS", "peage_stationnement"),
    ("EFFIA PARK", "peage_stationnement"),
    ("NORAUTO PARIS", "entretien_reparation_vehicule"),
    ("PRLV AXA ASSURANCE", "assurance_vehicule"),
    ("ORANGE VAD 123", "telecommunications"),
    ("Transfer from STICHTING CUSTODIAN UBER PAYMENTS", "recettes_plateformes"),
    ("AMENDE.GOUV", "amendes_infractions"),
    ("ABO COMPTA - octobre 2026 - BC-1", "honoraires_comptable_juridique"),
    ("Tesla Inc.", "carburant"),
    ("IONITY GMBH", "carburant"),
    ("ADP ROISSY P3", "peage_stationnement"),
    ("ORY P4A CB BS", "peage_stationnement"),
    ("ARCOUR", "peage_stationnement"),
    ("rémunération, septembre 2026", "remuneration_dirigeant"),
    ("Direct debit rejection", "frais_bancaires"),
    ("PRE-SWISSLIFE PS-12345", "assurance_personnelle_sante"),
    ("FRANPRIX BARBES", "repas_et_receptions"),
    ("PRIMARK VILLENEUVE", "usage_personnel_suspect"),
    ("PRLV URSSAF IDF", "charges_sociales_impots"),
    ("DGFIP IMPOT", "charges_sociales_impots"),
    ("ARVAL SERVICE LEASE", "loyers_locations"),
    ("VIREMENT INTERNE", "virement_interne"),
    ("APPORT EN COMPTE COURANT", "compte_courant_associe"),
)

# Libellés qui ne doivent être pris par aucune règle.
SANS_REGLE = ("TESLA FRANCE SARL", "LE MONDIAL", "MAXICOFFEE GC", "CASH SERVICES")


def _premiere(libelle: str) -> str | None:
    return next((r.categorie for r in charger_regles() if r.motif.search(libelle)), None)


@pytest.mark.parametrize(("libelle", "categorie"), EXEMPLES)
def test_chaque_exemple_va_a_sa_categorie(libelle: str, categorie: str) -> None:
    assert _premiere(libelle) == categorie


@pytest.mark.parametrize("libelle", SANS_REGLE)
def test_ces_libelles_ne_sont_pris_par_aucune_regle(libelle: str) -> None:
    assert _premiere(libelle) is None


def test_chaque_regle_a_au_moins_un_exemple() -> None:
    """Une règle ajoutée au CSV sans exemple ici fait échouer la CI."""
    sans_exemple = [
        regle.motif.pattern
        for regle in charger_regles()
        if not any(regle.motif.search(libelle) for libelle, _ in EXEMPLES)
    ]
    assert sans_exemple == []


def test_la_table_bridge_ne_vise_que_des_categories_du_pack() -> None:
    categories = set(charger_compte_par_categorie()) | {
        "usage_personnel_suspect",
        "compte_courant_associe",
    }
    table = charger_categories_banque()
    assert table["87"] == "carburant"
    assert table["251"] == "peage_stationnement"
    assert "273" not in table  # « Supermarchés » : TOTAL y est rangé, trop ambigu
    assert set(table.values()) <= categories


def _transaction(libelle: str, montant_cts: int) -> NormalizedTransaction:
    return NormalizedTransaction(
        id=TransactionId("t"),
        dossier_id=DossierId("d"),
        date=date(2026, 3, 1),
        montant_cts=montant_cts,
        libelle=libelle,
        source_provider="test",
        raw_payload={},
    )


def test_un_achat_de_quelques_euros_chez_total_n_est_pas_impute_seul() -> None:
    """AXE-837 : 1,50 € chez Total est proposé « carburant », sans être
    imputé ; un plein à 60 € l'est toujours."""
    pipeline = RulesAndMlPipeline(regles=charger_regles(), modele=None)
    petit = pipeline.categoriser(DossierId("d"), _transaction("CB TOTAL ACCESS A6", -1_50))
    plein = pipeline.categoriser(DossierId("d"), _transaction("CB TOTAL ACCESS A6", -60_00))

    assert (petit.categorie, plein.categorie) == ("carburant", "carburant")
    assert choisir_compte(petit, charger_compte_par_categorie()) == COMPTE_ATTENTE
    assert choisir_compte(plein, charger_compte_par_categorie()) == "6061"
    # Juste au plancher : imputé.
    seuil = pipeline.categoriser(DossierId("d"), _transaction("CB TOTAL", -5_00))
    assert choisir_compte(seuil, charger_compte_par_categorie()) == "6061"


def test_le_plancher_se_regle_dans_le_pack() -> None:
    regles = charger_regles()
    assert plancher_de("carburant", regles) == 5_00
    assert plancher_de("peage_stationnement", regles) is None
    # Les recharges électriques n'ont pas de plancher (une courte recharge coûte peu).
    tesla = next(r for r in regles if r.motif.search("TESLA INC"))
    assert tesla.montant_min_cts is None
