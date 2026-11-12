"""AXE-802 : registre des immobilisations en base, en ajout seul."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy.engine import Engine

from axelcompta.closing.immobilisations import Cession, Immobilisation
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.provisions_cloture import ImmobilisationConnue
from axelcompta.tenants.provisions_cloture_postgres import PostgresProvisionsClotureRepository

pytestmark = pytest.mark.integration

T, D = TenantId("t-test"), DossierId("d1")
VEHICULE = Immobilisation("v1", "Toyota", "2182", date(2026, 4, 1), 30_000_00, 60, "achat")


def test_declarer_lire_et_ceder_une_seule_fois(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier("d1")
    depot = PostgresProvisionsClotureRepository(engine)
    depot.ajouter_immobilisation(T, D, VEHICULE)
    assert depot.lister_immobilisations(T, D) == (VEHICULE,)
    with pytest.raises(ImmobilisationConnue):
        depot.ajouter_immobilisation(T, D, VEHICULE)

    cession = Cession(date(2028, 6, 30), 18_000_00)
    depot.enregistrer_cession(T, D, "v1", cession)
    (cede,) = depot.lister_immobilisations(T, D)
    assert cede.cession == cession
    with pytest.raises(ImmobilisationConnue):
        depot.enregistrer_cession(T, D, "v1", cession)
    with pytest.raises(ImmobilisationConnue):
        depot.enregistrer_cession(T, D, "inconnu", cession)


def test_un_contrat_de_loa_s_enregistre_une_fois(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    from axelcompta.closing.loa import ContratLoa

    creer_dossier("d1")
    depot = PostgresProvisionsClotureRepository(engine)
    contrat = ContratLoa(
        "c1", "DIAC", "Austral", date(2026, 4, 1), 36, 450_00, 3_000_00, 9_000_00, 120
    )
    depot.ajouter_contrat_loa(T, D, contrat)
    assert depot.lister_contrats_loa(T, D) == (contrat,)
    with pytest.raises(ImmobilisationConnue):
        depot.ajouter_contrat_loa(T, D, contrat)
