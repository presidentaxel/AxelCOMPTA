"""PostgresDossierRepository et PostgresPropositionRepository contre un vrai
Postgres (doc 09 §4). Prouve le même contrat que les implémentations en
mémoire, plus ce que seule une base garantit : contraintes d'unicité et
clés étrangères."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.db import metadata
from axelcompta.core.ids import DossierId, EcritureId, TenantId, TransactionId, UserId
from axelcompta.demo_identites import IDENTITE_KARIM
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.verdicts_postgres import PostgresVerdicts

pytestmark = pytest.mark.integration


def _dossier(dossier_id: str, tenant_id: str, contact_nr: str | None = None) -> Dossier:
    return Dossier(
        id=DossierId(dossier_id),
        tenant_id=TenantId(tenant_id),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="reel_normal",
        nom="Test",
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(2025, 1, 1),
        plateformes=("Uber", "Bolt"),
        contact_nr=contact_nr,
    )


def test_dossier_relu_a_lidentique(engine: Engine, id_unique: str) -> None:
    metadata.create_all(engine)
    repo = PostgresDossierRepository(engine)
    repo.enregistrer_tenant(Tenant(id=TenantId(id_unique), nom="T"))
    dossier = _dossier(f"d-{id_unique}", id_unique, contact_nr="42")

    repo.enregistrer(dossier)

    assert repo.obtenir(dossier.id) == dossier
    assert repo.par_contact_nr("42") == dossier
    assert repo.obtenir(DossierId("inexistant")) is None


def test_identite_et_fin_d_exercice_relues_a_lidentique(engine: Engine, id_unique: str) -> None:
    metadata.create_all(engine)
    repo = PostgresDossierRepository(engine)
    repo.enregistrer_tenant(Tenant(id=TenantId(id_unique), nom="T"))
    dossier = dataclasses.replace(
        _dossier(f"d-{id_unique}", id_unique),
        exercice_fin=date(2025, 12, 31),
        identite=IDENTITE_KARIM,
    )

    repo.enregistrer(dossier)

    assert repo.obtenir(dossier.id) == dossier


def test_lister_par_tenant_isole_les_portefeuilles(engine: Engine, id_unique: str) -> None:
    metadata.create_all(engine)
    repo = PostgresDossierRepository(engine)
    for tenant in ("t-a", "t-b"):
        repo.enregistrer_tenant(Tenant(id=TenantId(tenant), nom=tenant))
    repo.enregistrer(_dossier("d-a1", "t-a"))
    repo.enregistrer(_dossier("d-b1", "t-b"))

    assert [d.id for d in repo.lister_par_tenant(TenantId("t-a"))] == ["d-a1"]
    assert repo.lister_par_tenant(TenantId("t-inconnu")) == ()


def test_enregistrer_est_idempotent_et_ne_modifie_pas(engine: Engine) -> None:
    metadata.create_all(engine)
    repo = PostgresDossierRepository(engine)
    repo.enregistrer_tenant(Tenant(id=TenantId("t"), nom="T"))
    repo.enregistrer(_dossier("d1", "t"))

    repo.enregistrer(dataclasses.replace(_dossier("d1", "t"), nom="Modifié"))

    relu = repo.obtenir(DossierId("d1"))
    assert relu is not None
    assert relu.nom == "Test"


def test_contact_nr_ne_peut_pas_pointer_vers_deux_dossiers(engine: Engine) -> None:
    metadata.create_all(engine)
    repo = PostgresDossierRepository(engine)
    repo.enregistrer_tenant(Tenant(id=TenantId("t"), nom="T"))
    repo.enregistrer(_dossier("d1", "t", contact_nr="7"))

    with pytest.raises(IntegrityError):
        repo.enregistrer(_dossier("d2", "t", contact_nr="7"))


def test_dossier_dun_tenant_inconnu_est_refuse_par_la_base(engine: Engine) -> None:
    metadata.create_all(engine)
    repo = PostgresDossierRepository(engine)

    with pytest.raises(IntegrityError):
        repo.enregistrer(_dossier("d1", "tenant-fantome"))


def test_proposition_conservee_avec_etage_et_confiance(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier("d1")
    repo = PostgresPropositionRepository(engine)
    proposition = ProposedEntry(
        dossier_id=DossierId("d1"),
        transaction_id=TransactionId("tx1"),
        categorie="carburant",
        etage=Etage.ML,
        confiance=0.83,
    )

    repo.enregistrer(EcritureId("d1:categorise-1"), proposition)
    lue = repo.obtenir(DossierId("d1"), EcritureId("d1:categorise-1"))

    assert lue is not None
    assert (lue.categorie, lue.etage, lue.confiance) == ("carburant", Etage.ML, 0.83)
    # Une écriture d'un autre dossier ne doit jamais retrouver cette proposition.
    assert repo.obtenir(DossierId("d2"), EcritureId("d1:categorise-1")) is None


def test_proposition_dun_dossier_inexistant_est_refusee_par_la_base(engine: Engine) -> None:
    metadata.create_all(engine)
    proposition = ProposedEntry(
        dossier_id=DossierId("fantome"),
        transaction_id=TransactionId("tx1"),
        categorie="carburant",
        etage=Etage.ML,
        confiance=0.83,
    )

    with pytest.raises(IntegrityError):
        PostgresPropositionRepository(engine).enregistrer(EcritureId("x:1"), proposition)


def test_la_reconfiguration_sirene_est_relue_a_l_identique(engine: Engine, id_unique: str) -> None:
    """AXE-834 : forme, premier exercice, activité et éléments à confirmer."""
    metadata.create_all(engine)
    repo = PostgresDossierRepository(engine)
    repo.enregistrer_tenant(Tenant(id=TenantId(id_unique), nom="T"))
    dossier = _dossier(id_unique, id_unique)
    repo.enregistrer(dossier)
    assert repo.obtenir(dossier.id) == dossier  # a_confirmer vide, NAF absent par défaut

    reconfigure = dataclasses.replace(
        dossier,
        forme_juridique="SAS",
        exercice_debut=date(2025, 3, 13),
        exercice_fin=date(2025, 12, 31),
        code_naf="49.32Z",
        a_confirmer=("exercice", "forme_juridique"),
    )
    repo.reconfigurer_depuis_sirene(reconfigure)

    assert repo.obtenir(dossier.id) == reconfigure


def test_les_propositions_d_un_dossier_se_lisent_en_une_fois(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    """AXE-823 : la vue « déjà classées » lit toutes les propositions d'un coup."""
    creer_dossier("d1")
    repo = PostgresPropositionRepository(engine)
    for numero, confiance in ((1, 0.97), (2, 0.5)):
        repo.enregistrer(
            EcritureId(f"d1:e{numero}"),
            ProposedEntry(
                dossier_id=DossierId("d1"),
                transaction_id=TransactionId(f"tx{numero}"),
                categorie="carburant",
                etage=Etage.REGLE,
                confiance=confiance,
            ),
        )

    toutes = repo.lister(DossierId("d1"))

    assert {e: p.confiance for e, p in toutes.items()} == {"d1:e1": 0.97, "d1:e2": 0.5}
    assert repo.lister(DossierId("d2")) == {}


def test_le_dernier_verdict_d_une_ecriture_fait_foi(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier("d1")
    depot = PostgresVerdicts(engine)
    le = datetime(2026, 11, 5, tzinfo=UTC)
    depot.noter(DossierId("d1"), EcritureId("d1:e1"), "juste", UserId("louis"), le)
    depot.noter(DossierId("d1"), EcritureId("d1:e1"), "faux", UserId("louis"), le)
    depot.noter(DossierId("d1"), EcritureId("d1:e2"), "juste", UserId("louis"), le)

    assert PostgresVerdicts(engine).derniers(DossierId("d1")) == {"d1:e1": "faux", "d1:e2": "juste"}
