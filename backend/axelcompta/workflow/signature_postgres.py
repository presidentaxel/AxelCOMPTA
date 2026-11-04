"""Implémentation Postgres de SignatureRepository. Seul endroit qui fait
de l'I/O pour les signatures — `signature.py` reste pur, comme
`decisions_postgres.py` vis-à-vis de `decisions.py`.

Append-only : `enregistrer` ne fait qu'un INSERT. L'historique est la
preuve, jamais écrasé.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import DossierId, UserId
from axelcompta.core.rls import appliquer_rls

from .audit import noter
from .orm import documents_signes
from .signature import DocumentSigne, SignatureRepository


class PostgresSignatureRepository(SignatureRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer(
        self, dossier_id: DossierId, type_document: str, document: DocumentSigne
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            identifiant = str(uuid.uuid4())
            connexion.execute(
                documents_signes.insert().values(
                    id=identifiant,
                    dossier_id=dossier_id,
                    type_document=type_document,
                    contenu_pdf=document.contenu_pdf,
                    signataire=document.signataire,
                    signe_le=document.signe_le,
                    provider=document.provider,
                    qualifie=document.qualifie,
                )
            )
            noter(
                connexion,
                dossier_id,
                "signature",
                identifiant,
                document.signataire,
                document.signe_le,
            )

    def dernier(self, dossier_id: DossierId, type_document: str) -> DocumentSigne | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(documents_signes)
                .where(
                    documents_signes.c.dossier_id == dossier_id,
                    documents_signes.c.type_document == type_document,
                )
                .order_by(documents_signes.c.signe_le.desc())
                .limit(1)
            ).fetchone()
        return _ligne_vers_document(ligne) if ligne is not None else None

    def types_presents(
        self, dossier_ids: Sequence[DossierId], types_document: Sequence[str]
    ) -> dict[DossierId, set[str]]:
        presents: dict[DossierId, set[str]] = {dossier_id: set() for dossier_id in dossier_ids}
        if not dossier_ids or not types_document:
            return presents
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(documents_signes.c.dossier_id, documents_signes.c.type_document)
                .where(
                    documents_signes.c.dossier_id.in_(list(dossier_ids)),
                    documents_signes.c.type_document.in_(list(types_document)),
                )
                .distinct()
            )
            for ligne in lignes:
                presents[DossierId(ligne.dossier_id)].add(ligne.type_document)
        return presents

    def lister(self, dossier_id: DossierId, type_document: str) -> tuple[DocumentSigne, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            resultat = connexion.execute(
                select(documents_signes)
                .where(
                    documents_signes.c.dossier_id == dossier_id,
                    documents_signes.c.type_document == type_document,
                )
                .order_by(documents_signes.c.signe_le)
            )
            return tuple(_ligne_vers_document(ligne) for ligne in resultat)


def _ligne_vers_document(ligne: Row[tuple[object, ...]]) -> DocumentSigne:
    contenu = ligne.contenu_pdf
    return DocumentSigne(
        contenu_pdf=bytes(contenu),
        signataire=UserId(ligne.signataire),
        signe_le=ligne.signe_le,
        provider=ligne.provider,
        qualifie=ligne.qualifie,
    )
