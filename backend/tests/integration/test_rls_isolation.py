"""Suite de tests d'isolation RLS (doc 12 §1.1, migration `87fc7238e52e`).

Contrairement aux autres tests d'intégration de ce dossier, celui-ci a
besoin des objets posés par Alembic en SQL brut (rôle, policies) — pas
seulement des tables (`metadata.create_all`, ce que fait la fixture
`engine` de `conftest.py`). D'où `command.upgrade(cfg, "head")` explicite,
comme `test_migrations.py`.

Le rôle `axelcompta_web` est un objet de *cluster* Postgres (partagé entre
`axelcompta_dev` et `axelcompta_test`, doc de la migration) : on le
retrouve tel quel, pas besoin de le créer ici, seulement une connexion qui
l'utilise sur la même base que l'`engine` (admin) de la fixture.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, ProgrammingError

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, TenantId, UserId
from axelcompta.core.money import Money
from axelcompta.core.rls import appliquer_rls, contexte_identite
from axelcompta.documents.postgres import PostgresJustificatifRepository
from axelcompta.ingestion.consentement import ReleveSante, SanteConnexion, StatutConsentement
from axelcompta.ingestion.consentement_postgres import PostgresConsentementRepository
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.affectations import AffectationDejaDecidee, DecisionAffectation
from axelcompta.tenants.affectations_postgres import PostgresAffectationRepository
from axelcompta.tenants.avenants import AvenantRegime, MotifAvenant
from axelcompta.tenants.avenants_postgres import PostgresAvenantRegimeRepository
from axelcompta.tenants.exercices import ExerciceClos, ExerciceDejaClos
from axelcompta.tenants.exercices_postgres import PostgresExerciceRepository
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.statuts import RegimeImposition
from axelcompta.workflow.decisions import DecisionHumaine
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.notifications import NotificationEnvoyee
from axelcompta.workflow.notifications_postgres import PostgresNotificationRepository
from axelcompta.workflow.signature import DocumentSigne
from axelcompta.workflow.signature_postgres import PostgresSignatureRepository

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


@pytest.fixture
def migrations_appliquees(engine: Engine) -> None:
    """Rôle + policies ne sont posés qu'en SQL brut par Alembic (doc en
    tête de fichier) — indépendant de la fixture `engine` qui ne fait que
    `metadata.create_all`. Utilisé par toute fixture/test qui a besoin des
    tables ET du rôle web, pas seulement des tables."""
    command.upgrade(_config(), "head")


@pytest.fixture
def engine_web(engine: Engine, migrations_appliquees: None) -> Iterator[Engine]:
    """Même base que `engine` (admin), rôle `axelcompta_web` — celui que
    `demo_api.py` utilise en réalité (`DATABASE_URL_WEB`)."""
    url = make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()


@pytest.fixture
def deux_tenants_trois_dossiers(engine: Engine, migrations_appliquees: None) -> None:
    """Karim/Sophie chez le tenant A, Yanis chez le tenant B — de quoi
    prouver l'isolation à la fois entre indivs et entre portefeuilles."""
    depot = PostgresDossierRepository(engine)
    depot.enregistrer_tenant(Tenant(id=TenantId("tenant-a"), nom="A"))
    depot.enregistrer_tenant(Tenant(id=TenantId("tenant-b"), nom="B"))
    for dossier_id, tenant_id in (
        ("karim", "tenant-a"),
        ("sophie", "tenant-a"),
        ("yanis", "tenant-b"),
    ):
        depot.enregistrer(
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
        PostgresLedgerService(engine).enregistrer(
            Ecriture(
                id=EcritureId(f"{dossier_id}-1"),
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
        )


def _dossiers_visibles(
    engine_web: Engine, dossier_id: str | None, tenant_id: str | None
) -> set[str]:
    with contexte_identite(dossier_id=dossier_id, tenant_id=tenant_id):
        with engine_web.connect() as connexion:
            appliquer_rls(connexion)
            return {row.id for row in connexion.execute(text("SELECT id FROM dossiers"))}


def _nb_ecritures_visibles(
    engine_web: Engine, dossier_id: str | None, tenant_id: str | None
) -> int:
    with contexte_identite(dossier_id=dossier_id, tenant_id=tenant_id):
        with engine_web.connect() as connexion:
            appliquer_rls(connexion)
            return int(connexion.execute(text("SELECT count(*) FROM ecritures")).scalar_one())


def test_sans_contexte_rien_nest_visible(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    assert _dossiers_visibles(engine_web, dossier_id=None, tenant_id=None) == set()
    assert _nb_ecritures_visibles(engine_web, dossier_id=None, tenant_id=None) == 0


def test_indiv_ne_voit_que_son_propre_dossier(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    assert _dossiers_visibles(engine_web, dossier_id="karim", tenant_id=None) == {"karim"}
    assert _nb_ecritures_visibles(engine_web, dossier_id="karim", tenant_id=None) == 1


def test_gestionnaire_voit_tout_son_portefeuille_et_rien_dautre(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    # Tenant A : karim + sophie, jamais yanis (tenant B).
    assert _dossiers_visibles(engine_web, dossier_id=None, tenant_id="tenant-a") == {
        "karim",
        "sophie",
    }
    assert _nb_ecritures_visibles(engine_web, dossier_id=None, tenant_id="tenant-a") == 2


def test_ecriture_dun_autre_dossier_jamais_dans_le_grand_livre(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Le test qui compte vraiment : même si `PostgresLedgerService` ou une
    future route oublie un `WHERE dossier_id = ...`, la base ne rend pas
    les lignes d'un autre dossier — pas seulement une vérification sur le
    nombre de lignes, sur le contenu réel."""
    with contexte_identite(dossier_id="karim", tenant_id=None):
        with engine_web.connect() as connexion:
            appliquer_rls(connexion)
            libelles = {
                row.dossier_id
                for row in connexion.execute(text("SELECT dossier_id FROM ecritures"))
            }
    assert libelles == {"karim"}


def test_ecriture_liee_isolee_via_sa_transaction_parente(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """`lignes_ecriture` n'a pas de `dossier_id` propre (doc de la
    migration) : sa policy passe par `ecritures`, on vérifie que ça
    marche vraiment, pas seulement sur le papier."""
    with contexte_identite(dossier_id="karim", tenant_id=None):
        with engine_web.connect() as connexion:
            appliquer_rls(connexion)
            nb: int = connexion.execute(text("SELECT count(*) FROM lignes_ecriture")).scalar_one()
            assert nb == 2  # les 2 lignes de l'écriture de karim, jamais celles de yanis

    with contexte_identite(dossier_id="yanis", tenant_id=None):
        with engine_web.connect() as connexion:
            appliquer_rls(connexion)
            nb = connexion.execute(text("SELECT count(*) FROM lignes_ecriture")).scalar_one()
            assert nb == 2


def test_ecrire_une_decision_hors_de_son_dossier_est_refuse(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Le `WITH CHECK` protège aussi l'écriture, pas seulement la lecture :
    Sophie ne peut pas insérer une décision pour le dossier de Karim, même
    si un bug applicatif le tentait."""
    decision = DecisionHumaine(
        dossier_id=DossierId("karim"),
        ecriture_id=EcritureId("karim-1"),
        categorie="usage_personnel",
        etage_origine=Etage.REGLE,
        confiance_origine=0.9,
        decide_par=UserId("u1"),
        decide_le=datetime.now(UTC),
    )
    with contexte_identite(dossier_id="sophie", tenant_id=None):
        with pytest.raises((ProgrammingError, DBAPIError)):
            PostgresDecisionRepository(engine_web).enregistrer_decision(decision)


def test_signer_hors_de_son_dossier_est_refuse(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Même barrière que les décisions : Sophie ne peut pas enregistrer une
    signature sur le dossier de Karim."""
    document = DocumentSigne(
        contenu_pdf=b"%PDF-1.4 demo",
        signataire=UserId("sophie"),
        signe_le=datetime.now(UTC),
        provider="demo",
        qualifie=False,
    )
    with contexte_identite(dossier_id="sophie", tenant_id=None):
        with pytest.raises((ProgrammingError, DBAPIError)):
            PostgresSignatureRepository(engine_web).enregistrer(
                DossierId("karim"), "greffe_inpi", document
            )


def test_notifications_lues_seulement_dans_son_dossier_et_rien_dautre_modifiable(
    engine: Engine, engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """La cloche de Sophie ne voit ni ne marque celles de Karim, et le rôle
    web ne peut changer que `lue_le` (migration `e8c4f1a93b27`)."""
    depot_admin = PostgresNotificationRepository(engine)
    for id_, dossier_id in (("n-sophie", "sophie"), ("n-karim", "karim")):
        depot_admin.enregistrer(
            NotificationEnvoyee(
                id=id_,
                dossier_id=DossierId(dossier_id),
                type="a_trancher",
                envoye_le=datetime(2026, 9, 26, 9, 0),
                ecriture_ids=(EcritureId(f"{dossier_id}-1"),),
            )
        )
    depot_web = PostgresNotificationRepository(engine_web)
    with contexte_identite(dossier_id="sophie", tenant_id=None):
        assert [n.id for n in depot_web.lister(DossierId("karim"), limite=5)] == []
        assert depot_web.marquer_lues(DossierId("karim"), datetime(2026, 9, 26, 10, 0)) == 0
        assert depot_web.marquer_lues(DossierId("sophie"), datetime(2026, 9, 26, 10, 0)) == 1
        with engine_web.begin() as connexion:
            appliquer_rls(connexion)
            with pytest.raises((ProgrammingError, DBAPIError)):
                connexion.execute(text("UPDATE notifications_envoyees SET type = 'autre'"))

    assert depot_admin.lister(DossierId("karim"), limite=5)[0].lue_le is None


def test_avenants_de_regime_lus_par_dossier_et_jamais_modifies(
    engine: Engine, engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Append-only même pour le propriétaire (trigger), et Sophie ne voit
    pas les avenants de Karim (migration `a4d7e2c9b518`)."""
    PostgresAvenantRegimeRepository(engine).enregistrer(
        AvenantRegime(
            id="av-karim",
            dossier_id=DossierId("karim"),
            exercice_effet=2027,
            regime_imposition=RegimeImposition.IS,
            option_ir_debut=None,
            motif=MotifAvenant.FIN_OPTION_IR,
            enregistre_le=datetime(2026, 9, 26, 12, 0),
            enregistre_par="systeme",
        )
    )
    with contexte_identite(dossier_id="sophie", tenant_id=None):
        assert PostgresAvenantRegimeRepository(engine_web).lister(DossierId("karim")) == ()
    with contexte_identite(dossier_id="karim", tenant_id=None):
        (avenant,) = PostgresAvenantRegimeRepository(engine_web).lister(DossierId("karim"))
    assert avenant.exercice_effet == 2027
    with engine.begin() as connexion, pytest.raises((ProgrammingError, DBAPIError)):
        connexion.execute(text("UPDATE avenants_regime SET exercice_effet = 2026"))


def test_exercices_clos_append_only_isoles_et_ouverture_du_suivant(
    engine: Engine, engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Historique des exercices (migration `b8e3f5a1c762`) : verrou en
    base, un seul exercice clos par début, isolé par dossier ; puis le
    dossier s'ouvre sur l'exercice suivant."""
    exercices = PostgresExerciceRepository(engine)
    clos = ExerciceClos(
        dossier_id=DossierId("karim"),
        debut=date(2026, 1, 1),
        fin=date(2026, 12, 31),
        clos_le=datetime(2027, 3, 1, 9, 0),
        clos_par="test",
        changements=("régime d'imposition : option_IR → IS",),
    )
    exercices.enregistrer(clos)
    with pytest.raises(ExerciceDejaClos):
        exercices.enregistrer(clos)
    assert exercices.lister(DossierId("karim")) == (clos,)
    with contexte_identite(dossier_id="sophie", tenant_id=None):
        assert PostgresExerciceRepository(engine_web).lister(DossierId("karim")) == ()
    with engine.begin() as connexion, pytest.raises((ProgrammingError, DBAPIError)):
        connexion.execute(text("DELETE FROM exercices_clos"))

    depot = PostgresDossierRepository(engine)
    karim = depot.obtenir(DossierId("karim"))
    assert karim is not None
    depot.ouvrir_exercice(dataclasses.replace(karim, exercice_debut=date(2027, 1, 1)))
    rouvert = depot.obtenir(DossierId("karim"))
    assert rouvert is not None and rouvert.exercice_debut == date(2027, 1, 1)


def test_la_cloture_par_l_api_n_ecrit_que_dans_le_dossier_du_chauffeur(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Migration `c5f2a8d3e914` : l'API peut poser les écritures de clôture
    et ouvrir l'exercice suivant, mais seulement pour le dossier de
    l'identité, et sans toucher aux autres colonnes du dossier."""
    montant = Money(100)

    def _ecriture(dossier_id: str) -> Ecriture:
        return Ecriture(
            id=EcritureId(f"{dossier_id}-an"),
            dossier_id=DossierId(dossier_id),
            journal=Journal.AN,
            date=date(2027, 1, 1),
            libelle="À-nouveaux",
            reference_piece="AN-2027",
            lignes=(
                LigneEcriture(compte="512", sens=Sens.DEBIT, montant=montant),
                LigneEcriture(compte="120", sens=Sens.CREDIT, montant=montant),
            ),
        )

    with contexte_identite(dossier_id="karim", tenant_id=None):
        PostgresLedgerService(engine_web).enregistrer(_ecriture("karim"))
        with pytest.raises((ProgrammingError, DBAPIError)):
            PostgresLedgerService(engine_web).enregistrer(_ecriture("sophie"))
        with engine_web.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                text("UPDATE dossiers SET exercice_debut = '2027-01-01' WHERE id = 'karim'")
            )
        with engine_web.begin() as connexion, pytest.raises((ProgrammingError, DBAPIError)):
            appliquer_rls(connexion)
            connexion.execute(text("UPDATE dossiers SET nom = 'x' WHERE id = 'karim'"))


def test_affectation_decidee_par_le_chauffeur_seulement_dans_son_dossier(
    engine: Engine, engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Migration `d6a9c4e17b83` : décision append-only, isolée par dossier,
    tracée au journal d'audit dans la même transaction."""
    decision = DecisionAffectation(
        dossier_id=DossierId("karim"),
        annee_exercice=2025,
        scenario="prudent",
        dividendes_cts=500_00,
        reserve_legale_cts=10_00,
        decide_le=datetime(2026, 3, 1, 9, 0),
        decide_par="user-karim",
    )
    with contexte_identite(dossier_id="sophie", tenant_id=None):
        with pytest.raises((ProgrammingError, DBAPIError)):
            PostgresAffectationRepository(engine_web).enregistrer(decision)
    with contexte_identite(dossier_id="karim", tenant_id=None):
        PostgresAffectationRepository(engine_web).enregistrer(decision)
        with pytest.raises(AffectationDejaDecidee):
            PostgresAffectationRepository(engine_web).enregistrer(decision)
        assert PostgresAffectationRepository(engine_web).obtenir(DossierId("karim"), 2025) == (
            decision
        )
    with engine.begin() as connexion:
        actes = connexion.execute(
            text("SELECT count(*) FROM journal_audit WHERE type_acte = 'affectation_resultat'")
        ).scalar_one()
        assert actes == 1
    with engine.begin() as connexion, pytest.raises((ProgrammingError, DBAPIError)):
        connexion.execute(text("UPDATE affectations_resultat SET dividendes_cts = 0"))


def test_le_role_administrateur_nest_jamais_soumis_aux_policies(
    engine: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """`user` (celui de `demo_seed`/`synchro_digifactory`/`notifier`, doc
    de la migration) reste propriétaire des tables : les scripts
    d'administration continuent de voir tout le monde, sans contexte à
    poser — sinon `demo_seed` casserait au prochain amorçage."""
    with engine.connect() as connexion:
        assert connexion.execute(text("SELECT count(*) FROM dossiers")).scalar_one() == 3


def test_relances_de_connexion_reglees_par_le_gestionnaire_de_son_portefeuille(
    engine: Engine, engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Migration `e2b9d7c41f05` : le rôle web règle le mode de son portefeuille
    et de ses dossiers, pas celui d'un autre ; une valeur inconnue est refusée
    par la base elle-même ; le relevé des connexions reste isolé."""
    PostgresConsentementRepository(engine).enregistrer(
        DossierId("karim"),
        date(2026, 10, 31),
        StatutConsentement.A_RENOUVELER,
        datetime(2026, 9, 27, 8, 0, tzinfo=UTC),
        ReleveSante(SanteConnexion.OK, False, True, None),
    )
    with contexte_identite(dossier_id=None, tenant_id="tenant-a"):
        depot = PostgresDossierRepository(engine_web)
        depot.regler_relance_tenant(TenantId("tenant-a"), "manuel")
        depot.regler_relance_dossier(DossierId("karim"), "auto")
        depot.regler_relance_dossier(DossierId("yanis"), "manuel")  # hors portefeuille : sans effet
        releves = PostgresConsentementRepository(engine_web).lister(
            [DossierId("karim"), DossierId("yanis")]
        )
        assert set(releves) == {DossierId("karim")}
        assert releves[DossierId("karim")].expire_le == date(2026, 10, 31)
    admin = PostgresDossierRepository(engine)
    tenant = admin.obtenir_tenant(TenantId("tenant-a"))
    assert tenant is not None and tenant.relance_consentement == "manuel"
    karim, yanis = admin.obtenir(DossierId("karim")), admin.obtenir(DossierId("yanis"))
    assert karim is not None and karim.relance_consentement == "auto"
    assert yanis is not None and yanis.relance_consentement is None
    with engine.begin() as connexion, pytest.raises((ProgrammingError, DBAPIError)):
        connexion.execute(text("UPDATE tenants SET relance_consentement = 'sms'"))


def test_un_justificatif_reste_dans_son_dossier(
    engine_web: Engine, deux_tenants_trois_dossiers: None
) -> None:
    """Migration `a8c3e1d94b20` : Karim voit sa photo, Sophie et l'autre
    portefeuille non. Sophie ne peut pas en déposer une chez Karim."""
    repo = PostgresJustificatifRepository(engine_web)
    photo = EcritureId("photo-1")
    with contexte_identite(dossier_id="karim", tenant_id=None):
        repo.enregistrer(TenantId("tenant-a"), DossierId("karim"), photo, b"photo", ".jpg")
        assert repo.a_un_justificatif(TenantId("tenant-a"), DossierId("karim"), photo)
    with contexte_identite(dossier_id="sophie", tenant_id=None):
        assert repo.a_un_justificatif(TenantId("tenant-a"), DossierId("karim"), photo) is False
        with pytest.raises((ProgrammingError, DBAPIError)):
            repo.enregistrer(
                TenantId("tenant-a"), DossierId("karim"), EcritureId("photo-2"), b"x", ".jpg"
            )
    with contexte_identite(dossier_id=None, tenant_id="tenant-b"):
        assert repo.a_un_justificatif(TenantId("tenant-a"), DossierId("karim"), photo) is False
    with contexte_identite(dossier_id=None, tenant_id="tenant-a"):
        assert repo.a_un_justificatif(TenantId("tenant-a"), DossierId("karim"), photo) is True
