"""Agrégats du portefeuille en base (AXE-566, migration `e7b3d9a15c42`).

Ce que les triggers promettent : toute écriture qui concerne un dossier
périme sa ligne, d'où qu'elle vienne, et seulement la sienne. Ce que le
compare-and-set promet : un calcul lent ne remet jamais en base un résultat
déjà périmé. Il faut Alembic (triggers, policies, rôle web), pas seulement
`metadata.create_all`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from axelcompta.categorize.models import Etage
from axelcompta.closing.models import ProvisionCloture
from axelcompta.core.ids import DossierId, EcritureId, TenantId, UserId
from axelcompta.core.money import Money
from axelcompta.core.rls import appliquer_rls, contexte_identite
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants import agregats
from axelcompta.tenants.agregats import AgregatStocke
from axelcompta.tenants.agregats_postgres import PostgresAgregatsRepository
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.provisions_cloture_postgres import PostgresProvisionsClotureRepository
from axelcompta.workflow.decisions import DecisionHumaine
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent
VALEUR = AgregatStocke(120_000, 45_000, 75_000, "2026-01-01", "2026-12-31", None)


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


@pytest.fixture
def depot(engine: Engine) -> PostgresAgregatsRepository:
    command.upgrade(_config(), "head")
    portefeuille = PostgresDossierRepository(engine)
    for tenant_id, dossier_ids in (("tenant-a", ("karim", "sophie")), ("tenant-b", ("yanis",))):
        portefeuille.enregistrer_tenant(Tenant(id=TenantId(tenant_id), nom=tenant_id))
        for dossier_id in dossier_ids:
            portefeuille.enregistrer(
                Dossier(
                    id=DossierId(dossier_id),
                    tenant_id=TenantId(tenant_id),
                    forme_juridique="SASU",
                    regime_imposition="IS",
                    regime_tva="franchise",
                    nom=dossier_id,
                    tva_recettes_regime="franchise",
                    exercice_debut=date(2026, 1, 1),
                )
            )
    return PostgresAgregatsRepository(engine)


@pytest.fixture
def engine_web(engine: Engine, depot: PostgresAgregatsRepository) -> Iterator[Engine]:
    url = make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()


def _ecriture(dossier_id: str, numero: int) -> Ecriture:
    return Ecriture(
        id=EcritureId(f"{dossier_id}-{numero}"),
        dossier_id=DossierId(dossier_id),
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="test",
        reference_piece=None,
        lignes=(
            LigneEcriture(compte="512", sens=Sens.CREDIT, montant=Money(1000)),
            LigneEcriture(compte="471", sens=Sens.DEBIT, montant=Money(1000)),
        ),
    )


def _decision(dossier_id: str, ecriture_id: str) -> DecisionHumaine:
    return DecisionHumaine(
        dossier_id=DossierId(dossier_id),
        ecriture_id=EcritureId(ecriture_id),
        categorie="usage_personnel",
        etage_origine=Etage.REGLE,
        confiance_origine=0.9,
        decide_par=UserId("u1"),
        decide_le=datetime.now(UTC),
    )


def _garder(depot: PostgresAgregatsRepository, dossier_id: str) -> int:
    """Calcule-et-garde comme le fait l'API ; retourne la version de la ligne."""
    tenant = TenantId("tenant-b" if dossier_id == "yanis" else "tenant-a")
    ligne = depot.lire([DossierId(dossier_id)]).get(DossierId(dossier_id))
    version = None if ligne is None else ligne.version
    assert depot.enregistrer(tenant, DossierId(dossier_id), VALEUR, version)
    relue = depot.lire([DossierId(dossier_id)])[DossierId(dossier_id)]
    assert relue.valeur == VALEUR
    return relue.version


def _a_jour(depot: PostgresAgregatsRepository, dossier_id: str) -> bool:
    ligne = depot.lire([DossierId(dossier_id)]).get(DossierId(dossier_id))
    return ligne is not None and ligne.valeur is not None


def test_sans_ligne_il_faut_calculer(depot: PostgresAgregatsRepository) -> None:
    assert depot.lire([DossierId("karim")]) == {}
    assert depot.lire([]) == {}


def test_une_valeur_gardee_se_relit_a_l_identique(depot: PostgresAgregatsRepository) -> None:
    _garder(depot, "karim")
    avec_trous = AgregatStocke(0, 0, 0, None, None, "Seuil proche")
    ligne = depot.lire([DossierId("karim")])[DossierId("karim")]
    assert depot.enregistrer(TenantId("tenant-a"), DossierId("karim"), avec_trous, ligne.version)
    assert depot.lire([DossierId("karim")])[DossierId("karim")].valeur == avec_trous


def test_une_ecriture_perime_la_ligne_de_son_dossier_seulement(
    engine: Engine, depot: PostgresAgregatsRepository
) -> None:
    for dossier_id in ("karim", "sophie", "yanis"):
        _garder(depot, dossier_id)

    PostgresLedgerService(engine).enregistrer(_ecriture("karim", 1))

    assert not _a_jour(depot, "karim")
    assert _a_jour(depot, "sophie")
    assert _a_jour(depot, "yanis")


def test_une_decision_perime_la_ligne(engine: Engine, depot: PostgresAgregatsRepository) -> None:
    PostgresLedgerService(engine).enregistrer(_ecriture("karim", 1))
    _garder(depot, "karim")

    PostgresDecisionRepository(engine).enregistrer_decision(_decision("karim", "karim-1"))

    assert not _a_jour(depot, "karim")


def test_une_provision_perime_la_ligne_a_la_saisie_et_au_remplacement(
    engine: Engine, depot: PostgresAgregatsRepository
) -> None:
    provisions = PostgresProvisionsClotureRepository(engine)
    provision = ProvisionCloture(nature="cca", compte_charge="6226", centimes=5000, libelle="CCA")
    _garder(depot, "karim")
    provisions.remplacer(TenantId("tenant-a"), DossierId("karim"), 2026, (provision,))
    assert not _a_jour(depot, "karim")

    _garder(depot, "karim")
    provisions.remplacer(TenantId("tenant-a"), DossierId("karim"), 2026, ())  # DELETE
    assert not _a_jour(depot, "karim")


def test_un_changement_du_dossier_perime_la_ligne_un_update_sans_effet_non(
    engine: Engine, depot: PostgresAgregatsRepository
) -> None:
    portefeuille = PostgresDossierRepository(engine)
    _garder(depot, "karim")

    portefeuille.poser_forme_juridique(DossierId("karim"), "SASU")  # déjà SASU
    assert _a_jour(depot, "karim")

    portefeuille.poser_forme_juridique(DossierId("karim"), "EURL")
    assert not _a_jour(depot, "karim")


def test_un_calcul_lent_ne_remet_pas_en_base_un_resultat_deja_perime(
    engine: Engine, depot: PostgresAgregatsRepository
) -> None:
    """Le lecteur lit la version, calcule (lentement), pendant ce temps une
    écriture périme la ligne : son enregistrement est refusé."""
    version_lue = _garder(depot, "karim")
    PostgresLedgerService(engine).enregistrer(_ecriture("karim", 1))

    gardee = depot.enregistrer(TenantId("tenant-a"), DossierId("karim"), VALEUR, version_lue)

    assert gardee is False
    assert not _a_jour(depot, "karim")
    # Le calcul suivant, fait sur les données à jour, est gardé.
    nouvelle = depot.lire([DossierId("karim")])[DossierId("karim")].version
    assert depot.enregistrer(TenantId("tenant-a"), DossierId("karim"), VALEUR, nouvelle)
    assert _a_jour(depot, "karim")


def test_une_premiere_ecriture_perime_aussi_quand_aucune_ligne_n_existe(
    engine: Engine, depot: PostgresAgregatsRepository
) -> None:
    """Lecteur : pas de ligne, il calcule. Écrivain : écrit pendant ce temps
    et crée la ligne périmée. L'insertion du lecteur est refusée."""
    assert depot.lire([DossierId("karim")]) == {}
    PostgresLedgerService(engine).enregistrer(_ecriture("karim", 1))

    gardee = depot.enregistrer(TenantId("tenant-a"), DossierId("karim"), VALEUR, None)

    assert gardee is False
    assert not _a_jour(depot, "karim")


def test_un_changement_de_version_de_calcul_rend_les_lignes_perimees(
    depot: PostgresAgregatsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _garder(depot, "karim")
    monkeypatch.setattr(agregats, "VERSION_CALCUL", agregats.VERSION_CALCUL + 1)

    assert not _a_jour(depot, "karim")
    version = depot.lire([DossierId("karim")])[DossierId("karim")].version
    assert depot.enregistrer(TenantId("tenant-a"), DossierId("karim"), VALEUR, version)
    assert _a_jour(depot, "karim")


def test_l_ecriture_d_un_chauffeur_perime_la_ligne_malgre_la_rls(
    engine: Engine, engine_web: Engine, depot: PostgresAgregatsRepository
) -> None:
    """Le chauffeur n'a pas de tenant dans son contexte et ne peut pas écrire
    la table des agrégats : le trigger tourne avec les droits du propriétaire."""
    PostgresLedgerService(engine).enregistrer(_ecriture("karim", 1))
    _garder(depot, "karim")

    with contexte_identite(dossier_id="karim", tenant_id=None):
        PostgresDecisionRepository(engine_web).enregistrer_decision(_decision("karim", "karim-1"))

    assert not _a_jour(depot, "karim")


def test_le_web_ne_lit_ni_n_ecrit_les_agregats_d_un_autre_portefeuille(
    engine_web: Engine, depot: PostgresAgregatsRepository
) -> None:
    _garder(depot, "yanis")
    web = PostgresAgregatsRepository(engine_web)

    with contexte_identite(dossier_id=None, tenant_id="tenant-a"):
        assert web.lire([DossierId("yanis"), DossierId("karim")]) == {}
        assert not web.enregistrer(TenantId("tenant-b"), DossierId("yanis"), VALEUR, 0)


def test_le_web_garde_et_relit_les_agregats_de_son_portefeuille(
    engine_web: Engine, depot: PostgresAgregatsRepository
) -> None:
    web = PostgresAgregatsRepository(engine_web)

    with contexte_identite(dossier_id=None, tenant_id="tenant-a"):
        assert web.enregistrer(TenantId("tenant-a"), DossierId("karim"), VALEUR, None)
        assert web.lire([DossierId("karim")])[DossierId("karim")].valeur == VALEUR


def test_le_web_ne_peut_pas_ranger_un_agregat_sous_le_tenant_d_un_autre(
    engine_web: Engine, depot: PostgresAgregatsRepository
) -> None:
    web = PostgresAgregatsRepository(engine_web)

    with contexte_identite(dossier_id=None, tenant_id="tenant-a"):
        with pytest.raises(Exception, match="row-level security"):
            web.enregistrer(TenantId("tenant-b"), DossierId("karim"), VALEUR, None)


def test_le_web_ne_peut_pas_effacer_les_agregats(
    engine_web: Engine, depot: PostgresAgregatsRepository
) -> None:
    _garder(depot, "karim")
    with contexte_identite(dossier_id=None, tenant_id="tenant-a"):
        with engine_web.begin() as connexion:
            appliquer_rls(connexion)
            with pytest.raises(Exception, match="permission denied"):
                connexion.execute(text("DELETE FROM agregats_dossier"))
