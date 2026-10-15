"""CCA et FNP : seulement ce que l'indiv a saisi, jamais une règle de date."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.cloture_fiscale import hors_inventaire
from axelcompta.closing.models import ParametresCloture, ProvisionCloture
from axelcompta.closing.provisions import (
    ProvisionInvalide,
    ecritures_provisions,
    prefixe_provisions,
)
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.demo_chauffeurs_type import construire_ledger, parametres_cloture
from axelcompta.ingestion.providers.chauffeurs_demo import PROFIL_KARIM
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

DOSSIER = DossierId("dossier-test")
FIN = date(2025, 12, 31)


def _parametres(*provisions: ProvisionCloture) -> ParametresCloture:
    return ParametresCloture(
        exercice_debut=date(2025, 1, 1),
        exercice_fin=FIN,
        forme_juridique="SASU",
        provisions=provisions,
    )


def test_une_cca_constate_la_charge_d_avance() -> None:
    ecriture = ecritures_provisions(
        DOSSIER, (ProvisionCloture("cca", "616", 12_000, "assurance janvier"),), FIN
    )[0]
    assert ecriture.id == EcritureId(f"{prefixe_provisions(DOSSIER, 2025)}0")
    debit = {(ligne.compte, ligne.sens, ligne.montant.centimes) for ligne in ecriture.lignes}
    assert debit == {("486", Sens.DEBIT, 12_000), ("616", Sens.CREDIT, 12_000)}
    assert (
        sum(
            ligne.montant.centimes if ligne.sens is Sens.DEBIT else -ligne.montant.centimes
            for ligne in ecriture.lignes
        )
        == 0
    )


def test_une_fnp_constate_la_charge_a_payer() -> None:
    ecriture = ecritures_provisions(
        DOSSIER, (ProvisionCloture("fnp", "622", 8_000, "honoraire non parvenu"),), FIN
    )[0]
    comptes = {(ligne.compte, ligne.sens) for ligne in ecriture.lignes}
    assert comptes == {("622", Sens.DEBIT), ("408", Sens.CREDIT)}


@pytest.mark.parametrize(
    "provision",
    [
        ProvisionCloture("rabais", "606", 100, "non"),
        ProvisionCloture("cca", "706", 100, "un produit"),
        ProvisionCloture("cca", "695", 100, "l'impôt"),
        ProvisionCloture("fnp", "622", 0, "rien"),
        ProvisionCloture("fnp", "622", 100, "  "),
    ],
)
def test_une_estimation_inutilisable_est_refusee(provision: ProvisionCloture) -> None:
    with pytest.raises(ProvisionInvalide):
        ecritures_provisions(DOSSIER, (provision,), FIN)


def test_une_provision_deja_en_base_n_est_pas_comptee_deux_fois() -> None:
    deja = Ecriture(
        id=EcritureId(f"{prefixe_provisions(DOSSIER, 2025)}0"),
        dossier_id=DOSSIER,
        journal=Journal.OD,
        date=FIN,
        libelle="CCA — déjà là",
        reference_piece=None,
        lignes=(LigneEcriture(compte="486", sens=Sens.DEBIT, montant=Money(100)),),
    )
    reste = hors_inventaire(DOSSIER, (deja,), _parametres())
    assert reste == ()


def test_la_cca_saisie_entre_dans_la_liasse() -> None:
    ledger, _ = construire_ledger(PROFIL_KARIM)
    service = ClotureSimplifieeService(ledger)
    base = parametres_cloture(PROFIL_KARIM)
    sans = service.cloturer(PROFIL_KARIM.dossier_id, "2025", base)
    avec = service.cloturer(
        PROFIL_KARIM.dossier_id,
        "2025",
        dataclasses.replace(
            base, provisions=(ProvisionCloture("cca", "616", 10_000, "assurance janvier"),)
        ),
    )
    assert avec.cases["2033A.092"] == sans.cases.get("2033A.092", 0) + 10_000
    cloture = service.ecritures_de_cloture(
        PROFIL_KARIM.dossier_id,
        dataclasses.replace(
            base, provisions=(ProvisionCloture("cca", "616", 10_000, "assurance janvier"),)
        ),
    )
    assert any(ecriture.libelle.startswith("CCA —") for ecriture in cloture)
