"""AXE-826 : à la lecture, deux opérations au compte d'attente sur deux
sous-comptes de banque, de montants opposés, sont proposées en virement
interne (cas des opérations de MK DRIVING importées avant AXE-826)."""

from __future__ import annotations

from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.demo_api import get_ledger
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.service import LedgerService
from tests.test_demo_api import (  # noqa: F401 — fixtures autouse réutilisées
    _client_et_stubs,
    _en_tete,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

KARIM = DossierId("DEMO_karim")


def _a_trancher(id_: str, banque: str, montant: int) -> Ecriture:
    sens = Sens.DEBIT if montant > 0 else Sens.CREDIT
    autre = Sens.CREDIT if sens is Sens.DEBIT else Sens.DEBIT
    return Ecriture(
        id=EcritureId(f"DEMO_karim:{id_}"),
        dossier_id=KARIM,
        journal=Journal.BQ,
        date=date(2025, 6, 2),
        libelle="trésorerie (non_categorise_a_verifier)",
        reference_piece=None,
        lignes=(
            LigneEcriture(banque, sens, Money(abs(montant))),
            LigneEcriture("471", autre, Money(abs(montant))),
        ),
    )


def test_les_deux_jambes_sont_proposees_en_virement_interne() -> None:
    client = _client_et_stubs()[0]
    ledger: LedgerService = client.app.dependency_overrides[get_ledger]()  # type: ignore[attr-defined]
    ledger.enregistrer(_a_trancher("sortie", "5121", -13_600))
    ledger.enregistrer(_a_trancher("entree", "5122", 13_600))

    reponse = client.get("/dossiers/DEMO_karim/transactions", headers=_en_tete("DEMO_karim"))

    assert reponse.status_code == 200
    par_id = {t["ecriture_id"]: t for t in reponse.json()}
    for jambe in ("DEMO_karim:sortie", "DEMO_karim:entree"):
        assert par_id[jambe]["proposition"] == "virement_interne"
        assert par_id[jambe]["origine_proposition"] == "regle"
