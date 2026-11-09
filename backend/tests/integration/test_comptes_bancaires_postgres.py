"""AXE-832 contre un vrai Postgres : registre des comptes bancaires,
synchro qui pose les sous-comptes 512x, puis ventilation des écritures
restées au 512."""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.ingestion.comptes_bancaires import (
    CompteBancaire,
    CompteInconnu,
    CompteReleve,
    compte_de,
    relever_comptes,
)
from axelcompta.ingestion.comptes_bancaires_postgres import PostgresCompteBancaireRepository
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.ingestion.providers.digifactory import DigifactoryProvider
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie, charger_regles
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.orm import journal_audit
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.synchro import synchroniser_dossier
from axelcompta.workflow.ventilation_bancaire import ventilation_du_dossier

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 5, 4, 12, tzinfo=UTC)


def _tx(id_: str, montant: float, compte: str | None) -> dict[str, object]:
    ligne: dict[str, object] = {
        "id": id_,
        "provider_description": "CARTE TOTAL STATION",
        "amount": montant,
        "date": "2026-06-01",
        "updated_at": f"2026-06-01 10:00:0{id_[-1]}",
        "deleted": False,
        "future": False,
    }
    if compte is not None:
        ligne["account_id"] = compte
    return ligne


def _ancienne_ecriture(dossier_id: DossierId) -> Ecriture:
    return Ecriture(
        id=EcritureId(f"{dossier_id}:digifactory-t0"),
        dossier_id=dossier_id,
        journal=Journal.BQ,
        date=date(2026, 5, 2),
        libelle="ANCIENNE",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.CREDIT, Money(1_000)),
            LigneEcriture("471", Sens.DEBIT, Money(1_000)),
        ),
    )


def _soldes(ecritures: tuple[Ecriture, ...]) -> dict[str, int]:
    soldes: dict[str, int] = {}
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            signe = 1 if ligne.sens is Sens.DEBIT else -1
            soldes[ligne.compte] = soldes.get(ligne.compte, 0) + signe * ligne.montant.centimes
    return soldes


def test_le_registre_numerote_et_releve(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    dossier = DossierId(id_unique)
    depot = PostgresCompteBancaireRepository(engine)

    assert compte_de(depot, dossier, "pro") == "5121"
    assert compte_de(depot, dossier, "fiscal") == "5122"
    assert compte_de(depot, dossier, "pro") == "5121"
    comptes = relever_comptes(depot, dossier, [CompteReleve("pro", "Compte PRO", 110)], LE)

    pro = next(c for c in comptes if c.identifiant == "pro")
    assert (pro.nom, pro.solde_banque_cts, pro.solde_releve_le) == ("Compte PRO", 110, LE)
    relever_comptes(depot, dossier, [CompteReleve("pro", None, 220)], LE)
    pro = next(c for c in depot.lister(dossier) if c.identifiant == "pro")
    assert (pro.nom, pro.solde_banque_cts) == ("Compte PRO", 220)


def test_un_numero_deja_pris_passe_au_suivant(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    """Deux synchros simultanées visent le même numéro : la seconde repart
    au numéro libre suivant, sans erreur."""
    creer_dossier(id_unique)
    dossier = DossierId(id_unique)
    depot = PostgresCompteBancaireRepository(engine)
    depot.ajouter(CompteBancaire(dossier, "a", "5121"))

    second = depot.ajouter(CompteBancaire(dossier, "b", "5121"))

    assert second.compte_comptable == "5122"
    assert depot.ajouter(CompteBancaire(dossier, "a", "5129")).compte_comptable == "5121"


def test_la_base_refuse_un_compte_qui_n_est_pas_un_sous_compte_de_banque(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    with pytest.raises(IntegrityError):
        PostgresCompteBancaireRepository(engine).ajouter(
            CompteBancaire(DossierId(id_unique), "a", "512")
        )


def test_synchro_puis_ventilation_sur_postgres(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    dossier = PostgresDossierRepository(engine).obtenir(DossierId(id_unique))
    assert dossier is not None
    dossier = dataclasses.replace(dossier, contact_nr="42")
    ledger = PostgresLedgerService(engine)
    journal = PostgresJournalIngestion(engine)
    comptes = PostgresCompteBancaireRepository(engine)
    # Deux comptes pro, déjà retenus par le dirigeant (AXE-729).
    for identifiant, numero in (("pro", "5121"), ("fiscal", "5122")):
        comptes.ajouter(CompteBancaire(dossier.id, identifiant, numero, retenu=True))
    payload = {"acc": [_tx("t1", -60.0, "pro"), _tx("t2", 848.0, "fiscal")]}
    # Une écriture plus ancienne, posée au 512 avant AXE-832.
    journal.archiver(dossier.id, "digifactory", "t0", None, {"id": "t0", "account_id": "pro"})
    ledger.enregistrer(_ancienne_ecriture(dossier.id))

    asyncio.run(
        synchroniser_dossier(
            dossier,
            DigifactoryProvider(payload=payload),
            "digifactory",
            journal,
            ledger,
            PostgresPropositionRepository(engine),
            RulesAndMlPipeline(regles=charger_regles(), modele=None),
            charger_compte_par_categorie(),
            comptes,
        )
    )
    reclassements = ventilation_du_dossier(
        dossier.id, ledger.grand_livre(dossier.id), journal, comptes, "digifactory"
    )
    for reclassement in reclassements:
        ledger.enregistrer(reclassement)

    soldes = _soldes(ledger.grand_livre(dossier.id))
    assert soldes["5121"] == -6_000 - 1_000
    assert soldes["5122"] == 84_800
    assert soldes.get("512", 0) == 0
    assert len(reclassements) == 1  # seule l'ancienne écriture était au 512
    assert (
        ventilation_du_dossier(
            dossier.id, ledger.grand_livre(dossier.id), journal, comptes, "digifactory"
        )
        == []
    )


def test_decider_ecrit_le_choix_et_le_trace(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    """AXE-729 : retenu, « à relire » si retenu après coup, acte au journal d'audit."""
    creer_dossier(id_unique)
    dossier_id = DossierId(id_unique)
    comptes = PostgresCompteBancaireRepository(engine)
    releves = [CompteReleve("pro", "Compte PRO", 100), CompteReleve("perso", "Livret", 50)]
    relever_comptes(comptes, dossier_id, releves, LE)
    assert [c.retenu for c in comptes.lister(dossier_id)] == [None, None]

    comptes.decider(dossier_id, "5121", True, UserId("dirigeant"), LE)
    comptes.decider(dossier_id, "5122", False, UserId("dirigeant"), LE)

    pro, perso = comptes.lister(dossier_id)
    assert (pro.retenu, pro.a_relire, perso.retenu, perso.a_relire) == (True, True, False, False)
    comptes.relu(dossier_id)
    assert not comptes.lister(dossier_id)[0].a_relire
    with engine.connect() as connexion:
        actes = connexion.execute(
            select(journal_audit.c.type_acte, journal_audit.c.reference)
            .where(journal_audit.c.dossier_id == dossier_id)
            .order_by(journal_audit.c.reference)
        ).all()
    assert [tuple(a) for a in actes] == [
        ("compte_bancaire_retenu", "5121"),
        ("compte_bancaire_ecarte", "5122"),
    ]
    with pytest.raises(CompteInconnu):
        comptes.decider(dossier_id, "5129", True, UserId("dirigeant"), LE)
