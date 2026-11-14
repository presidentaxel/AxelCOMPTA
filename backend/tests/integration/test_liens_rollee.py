"""AXE-911 : liens Rollee, historique et file « à choisir » en base."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_rollee import UtilisateurRollee
from axelcompta.ingestion.comptes_rollee_postgres import PostgresComptesRollee
from axelcompta.ingestion.liens_rollee import AChoisir, Lien, LienDejaPris
from axelcompta.ingestion.liens_rollee_postgres import PostgresLiensRollee
from axelcompta.ingestion.rapprochement_rollee import Apercu, Candidat

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 13, 9, tzinfo=UTC)
T = TenantId("t-test")


def test_lier_delier_et_historique(engine: Engine, creer_dossier: Callable[[str], None]) -> None:
    creer_dossier("d1")
    creer_dossier("d2")
    liens = PostgresLiensRollee(engine)
    # Un lien posé depuis l'espace chauffeur (AXE-819) a l'origine « cree ».
    PostgresComptesRollee(engine).enregistrer_utilisateur(
        UtilisateurRollee(DossierId("d2"), "u-cree", "b1"), LE
    )
    assert liens.lien(DossierId("d2")) == Lien(DossierId("d2"), "u-cree", "b1", "cree", LE)
    auto = Lien(DossierId("d1"), "u-1", "b1", "auto", LE, "iban")
    liens.lier(auto)
    second = Lien(DossierId("d1"), "u-2", "b1", "manuel", LE, None, "marie")
    liens.lier(second)
    with pytest.raises(LienDejaPris):
        liens.lier(Lien(DossierId("d2"), "u-1", "b1", "manuel", LE, None, "marie"))
    assert [x.rollee_user_id for x in liens.liens(T)] == ["u-1", "u-2", "u-cree"]
    retire_le = LE + timedelta(days=1)
    assert liens.delier(DossierId("d1"), "marie@cabinet.fr", "homonyme", retire_le, "u-1") == auto
    restant = liens.lien(DossierId("d1"))
    assert restant is not None and restant.rollee_user_id == "u-2"
    assert liens.delier(DossierId("d1"), "marie@cabinet.fr", "le second", retire_le) == second
    assert liens.lien(DossierId("d1")) is None
    traces = liens.historique(DossierId("d1"))
    assert {t.motif for t in traces} == {"homonyme", "le second"}
    assert liens.paires_retirees(T) == frozenset({("u-1", "d1"), ("u-2", "d1")})


def test_la_file_a_choisir_se_remplace_et_s_ecarte(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier("d1")
    liens = PostgresLiensRollee(engine)
    attente = AChoisir(
        "u-9",
        T,
        "b1",
        "a_choisir",
        (Candidat("d1", ("même nom",), False),),
        Apercu("K.B.", ("Uber",), "0189"),
        LE,
    )
    liens.remplacer_a_choisir(T, "b1", [attente])
    assert liens.a_choisir(T) == [attente]
    assert liens.ecarter("u-9", LE)
    (ecarte,) = liens.a_choisir(T)
    assert ecarte.etat == "ecarte" and ecarte.candidats == ()
    liens.remplacer_a_choisir(T, "b1", [])
    assert liens.a_choisir(T) == []
    liens.remplacer_a_choisir(T, "b1", [attente])
    liens.retirer_a_choisir("u-9")
    assert liens.a_choisir(T) == []
