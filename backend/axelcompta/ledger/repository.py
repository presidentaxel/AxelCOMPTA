"""Implémentation Postgres de LedgerService (doc 17 semaine 0). Seul endroit
du module qui fait de l'I/O — la validation d'invariant reste pure et vient
de `invariants.py`, appelée avant toute écriture (doc 08 §2.1, §2.4 :
transaction aux bornes explicites).
"""

from __future__ import annotations

import dataclasses
import uuid

from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.core.rls import appliquer_rls

from .invariants import verifier_equilibre
from .models import Ecriture, Journal, LigneEcriture, Sens
from .orm import ecritures, lignes_ecriture
from .periodes import Periode, verifier_hors_periode_close
from .service import LedgerService


class PostgresLedgerService(LedgerService):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer(self, ecriture: Ecriture) -> EcritureId:
        verifier_equilibre(ecriture)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            verifier_hors_periode_close(
                ecriture.date, _periodes_closes(connexion, ecriture.dossier_id)
            )
            connexion.execute(
                ecritures.insert().values(
                    id=ecriture.id,
                    dossier_id=ecriture.dossier_id,
                    journal=ecriture.journal.name,
                    date=ecriture.date,
                    libelle=ecriture.libelle,
                    reference_piece=ecriture.reference_piece,
                )
            )
            connexion.execute(
                lignes_ecriture.insert(),
                [_ligne_vers_ligne(ecriture.id, ligne) for ligne in ecriture.lignes],
            )
        return ecriture.id

    def periodes_closes(self, dossier_id: DossierId) -> tuple[Periode, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return _periodes_closes(connexion, dossier_id)

    def grand_livre(self, dossier_id: DossierId) -> tuple[Ecriture, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            entetes = _lire_entetes(connexion, dossier_id)
            lignes_par_ecriture = _lire_lignes(connexion, tuple(entetes))
        return tuple(
            dataclasses.replace(entete, lignes=tuple(lignes_par_ecriture.get(eid, ())))
            for eid, entete in entetes.items()
        )


def _periodes_closes(connexion: Connection, dossier_id: DossierId) -> tuple[Periode, ...]:
    """`exercices_clos` appartient à tenants/ : lue en SQL, sans importer son
    modèle (ledger ne dépend que de core)."""
    lignes = connexion.execute(
        text("SELECT debut, fin FROM exercices_clos WHERE dossier_id = :d ORDER BY debut"),
        {"d": dossier_id},
    ).all()
    return tuple((debut, fin) for debut, fin in lignes)


def _ligne_vers_ligne(ecriture_id: EcritureId, ligne: LigneEcriture) -> dict[str, object]:
    return {
        "id": str(uuid.uuid4()),
        "ecriture_id": ecriture_id,
        "compte": ligne.compte,
        "sens": ligne.sens.name,
        "montant_centimes": ligne.montant.centimes,
        "devise": ligne.montant.devise,
        "analytique": ligne.analytique,
        "code_tva": ligne.code_tva,
    }


def _lire_entetes(connexion: Connection, dossier_id: DossierId) -> dict[str, Ecriture]:
    resultat = connexion.execute(
        select(ecritures)
        .where(ecritures.c.dossier_id == dossier_id)
        .order_by(ecritures.c.date, ecritures.c.id)
    )
    return {
        ligne.id: Ecriture(
            id=EcritureId(ligne.id),
            dossier_id=DossierId(ligne.dossier_id),
            journal=Journal[ligne.journal],
            date=ligne.date,
            libelle=ligne.libelle,
            reference_piece=ligne.reference_piece,
            lignes=(),
        )
        for ligne in resultat
    }


def _lire_lignes(
    connexion: Connection, ids_ecritures: tuple[str, ...]
) -> dict[str, list[LigneEcriture]]:
    if not ids_ecritures:
        return {}
    resultat = connexion.execute(
        select(lignes_ecriture).where(lignes_ecriture.c.ecriture_id.in_(ids_ecritures))
    )
    par_ecriture: dict[str, list[LigneEcriture]] = {eid: [] for eid in ids_ecritures}
    for row in resultat:
        par_ecriture[row.ecriture_id].append(
            LigneEcriture(
                compte=row.compte,
                sens=Sens[row.sens],
                montant=Money(centimes=row.montant_centimes, devise=row.devise),
                analytique=row.analytique,
                code_tva=row.code_tva,
            )
        )
    return par_ecriture
