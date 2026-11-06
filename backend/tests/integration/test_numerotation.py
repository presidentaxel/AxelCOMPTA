"""Invariant I3 en base (AXE-807, migration a3e8c1f5b297) : une séquence par
dossier et par exercice, dans l'ordre de validation, sans trou."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.filings.fec import SEPARATEUR_ZONE, exporter_fec
from axelcompta.ledger.balance import ecarts
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService, soldes_par_journal
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def _ecriture(dossier: str, rang: int, jour: date, journal: Journal = Journal.BQ) -> Ecriture:
    return Ecriture(
        id=EcritureId(f"{dossier}:e{rang:04d}"),
        dossier_id=DossierId(dossier),
        journal=journal,
        date=jour,
        libelle=f"Opération {rang}",
        reference_piece=None,
        lignes=(
            LigneEcriture("625", Sens.DEBIT, Money(12_00)),
            LigneEcriture("512", Sens.CREDIT, Money(12_00)),
        ),
    )


def _dossier(engine: Engine, identifiant: str) -> None:
    depot = PostgresDossierRepository(engine)
    depot.enregistrer_tenant(Tenant(id=TenantId("t-i3"), nom="T"))
    depot.enregistrer(
        Dossier(
            id=DossierId(identifiant),
            tenant_id=TenantId("t-i3"),
            forme_juridique="SASU",
            regime_imposition="IS",
            regime_tva="franchise",
            nom="I3",
            tva_recettes_regime="franchise",
            exercice_debut=date(2026, 1, 1),
        )
    )


def _numeros(engine: Engine, dossier: str) -> dict[str, int]:
    with engine.connect() as connexion:
        lignes = connexion.execute(
            text("SELECT id, numero FROM ecritures WHERE dossier_id = :d"), {"d": dossier}
        ).all()
    return {identifiant: numero for identifiant, numero in lignes}


def test_la_reprise_numerote_dans_l_ordre_du_fec_d_avant(engine: Engine, id_unique: str) -> None:
    command.upgrade(_config(), "e9c2a7f14b63")
    _dossier(engine, id_unique)
    ledger = PostgresLedgerService(engine)
    ecrites = (
        _ecriture(id_unique, 3, date(2026, 3, 2)),
        _ecriture(id_unique, 2, date(2026, 3, 1)),
        _ecriture(id_unique, 1, date(2026, 1, 1), Journal.AN),
        _ecriture(id_unique, 4, date(2026, 1, 1)),
    )
    for ecriture in ecrites:
        ledger.enregistrer(ecriture)
    avant = exporter_fec(ecrites)  # le FEC d'avant : numéros calculés à l'export

    command.upgrade(_config(), "head")

    assert _numeros(engine, id_unique) == {
        f"{id_unique}:e0001": 1,  # à-nouveaux d'abord le même jour
        f"{id_unique}:e0004": 2,
        f"{id_unique}:e0002": 3,
        f"{id_unique}:e0003": 4,
    }
    assert exporter_fec(ledger.grand_livre(DossierId(id_unique))) == avant


def test_une_ecriture_antidatee_ne_change_pas_les_numeros_anciens(
    engine: Engine, id_unique: str
) -> None:
    """Critère du ticket : FEC exporté deux fois, une écriture antidatée entre
    les deux ; les anciennes gardent leur numéro, la nouvelle vient après."""
    command.upgrade(_config(), "head")
    _dossier(engine, id_unique)
    ledger = PostgresLedgerService(engine)
    for rang, jour in ((1, date(2026, 3, 1)), (2, date(2026, 3, 5))):
        ledger.enregistrer(_ecriture(id_unique, rang, jour))
    premier = _numeros(engine, id_unique)

    ledger.enregistrer(_ecriture(id_unique, 3, date(2026, 2, 1)))  # antidatée

    second = _numeros(engine, id_unique)
    assert {k: second[k] for k in premier} == premier
    assert second[f"{id_unique}:e0003"] == 3
    fec = exporter_fec(ledger.grand_livre(DossierId(id_unique)))  # valide (ValidDate croissante)
    assert fec.splitlines()[-1].split(SEPARATEUR_ZONE)[2] == "3"


def test_mille_ecritures_concurrentes_sans_trou_ni_doublon(engine: Engine, id_unique: str) -> None:
    command.upgrade(_config(), "head")
    _dossier(engine, id_unique)
    ledger = PostgresLedgerService(engine)

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(
            pool.map(
                lambda r: ledger.enregistrer(_ecriture(id_unique, r, date(2026, 5, 1))), range(1000)
            )
        )
    # Un échec après attribution du numéro (identifiant en double) : rollback,
    # le numéro est rendu.
    with pytest.raises(IntegrityError):
        ledger.enregistrer(_ecriture(id_unique, 0, date(2026, 5, 1)))
    ledger.enregistrer(_ecriture(id_unique, 1000, date(2026, 5, 1)))

    assert sorted(_numeros(engine, id_unique).values()) == list(range(1, 1002))


def test_un_exercice_suivant_a_sa_propre_sequence(engine: Engine, id_unique: str) -> None:
    """Une opération de 2027 arrivée avant la clôture de 2026 ouvre la
    séquence de l'exercice suivant."""
    command.upgrade(_config(), "head")
    _dossier(engine, id_unique)
    ledger = PostgresLedgerService(engine)
    ledger.enregistrer(_ecriture(id_unique, 1, date(2026, 12, 30)))
    ledger.enregistrer(_ecriture(id_unique, 2, date(2027, 1, 3)))
    ledger.enregistrer(_ecriture(id_unique, 3, date(2026, 12, 31)))
    assert _numeros(engine, id_unique) == {
        f"{id_unique}:e0001": 1,
        f"{id_unique}:e0002": 1,
        f"{id_unique}:e0003": 2,
    }


def test_un_desequilibre_injecte_en_base_est_trouve(engine: Engine, id_unique: str) -> None:
    """Critère I7 : une ligne ajoutée hors du grand livre (connexion
    propriétaire) déséquilibre la balance ; le contrôle la trouve."""
    command.upgrade(_config(), "head")
    _dossier(engine, id_unique)
    PostgresLedgerService(engine).enregistrer(_ecriture(id_unique, 1, date(2026, 3, 1)))
    assert not [e for e in ecarts(soldes_par_journal(engine)) if e.dossier_id == id_unique]

    with engine.begin() as connexion:
        connexion.execute(
            text(
                "INSERT INTO lignes_ecriture (id, ecriture_id, compte, sens, montant_centimes, devise) "
                "VALUES (:id, :e, '625', 'DEBIT', 100, 'EUR')"
            ),
            {"id": f"{id_unique}-x", "e": f"{id_unique}:e0001"},
        )

    trouves = [e for e in ecarts(soldes_par_journal(engine)) if e.dossier_id == id_unique]
    assert [(e.journal, e.debit_cts, e.credit_cts) for e in trouves] == [
        ("BQ", 1300, 1200),
        (None, 1300, 1200),
    ]
