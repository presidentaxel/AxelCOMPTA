"""PostgresSignatureRepository contre un vrai Postgres."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, UserId
from axelcompta.workflow.signature import DocumentSigne, SignatureRepository
from axelcompta.workflow.signature_postgres import PostgresSignatureRepository

pytestmark = pytest.mark.integration


def _document(quand: datetime, pdf: bytes = b"%PDF-1.4 a") -> DocumentSigne:
    return DocumentSigne(
        contenu_pdf=pdf,
        signataire=UserId("u_test"),
        signe_le=quand,
        provider="demo",
        qualifie=False,
    )


def test_signature_enregistree_puis_relue(
    engine: Engine, id_unique: str, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier(id_unique)
    repo = PostgresSignatureRepository(engine)
    document = _document(datetime(2026, 9, 24, 10, 0, tzinfo=UTC))

    repo.enregistrer(DossierId(id_unique), "greffe_inpi", document)

    assert repo.dernier(DossierId(id_unique), "greffe_inpi") == document


def test_nouvelle_signature_devient_derniere_sans_effacer_historique(
    engine: Engine, id_unique: str, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier(id_unique)
    repo = PostgresSignatureRepository(engine)
    premiere = _document(datetime(2026, 9, 24, 10, 0, tzinfo=UTC), b"%PDF-1.4 un")
    seconde = _document(datetime(2026, 9, 24, 11, 0, tzinfo=UTC), b"%PDF-1.4 deux")
    repo.enregistrer(DossierId(id_unique), "greffe_inpi", premiere)
    repo.enregistrer(DossierId(id_unique), "greffe_inpi", seconde)

    assert repo.dernier(DossierId(id_unique), "greffe_inpi") == seconde
    assert repo.lister(DossierId(id_unique), "greffe_inpi") == (premiere, seconde)


def test_signatures_isolees_par_type_de_document(
    engine: Engine, id_unique: str, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier(id_unique)
    repo = PostgresSignatureRepository(engine)
    repo.enregistrer(
        DossierId(id_unique),
        "greffe_inpi",
        _document(datetime(2026, 9, 24, 10, 0, tzinfo=UTC)),
    )

    assert repo.dernier(DossierId(id_unique), "autre") is None


def test_types_presents_en_une_lecture_comme_le_defaut_du_contrat(
    engine: Engine, id_unique: str, creer_dossier: Callable[[str], None]
) -> None:
    premier, second = f"{id_unique}-a", f"{id_unique}-b"
    creer_dossier(premier)
    creer_dossier(second)
    repo = PostgresSignatureRepository(engine)
    quand = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)
    repo.enregistrer(DossierId(premier), "cloture", _document(quand))
    repo.enregistrer(DossierId(premier), "cloture", _document(quand.replace(hour=11)))
    repo.enregistrer(DossierId(premier), "greffe_inpi", _document(quand))
    repo.enregistrer(DossierId(premier), "hors_frise", _document(quand))
    ids = [DossierId(premier), DossierId(second)]
    types = ["cloture", "validation_comptes", "greffe_inpi"]

    presents = repo.types_presents(ids, types)

    assert presents == {DossierId(premier): {"cloture", "greffe_inpi"}, DossierId(second): set()}
    assert presents == SignatureRepository.types_presents(repo, ids, types)
    assert repo.types_presents([], types) == {}
