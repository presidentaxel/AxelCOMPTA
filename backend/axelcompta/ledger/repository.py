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

from .balance import SoldeJournal
from .invariants import verifier_equilibre
from .models import Ecriture, Journal, LigneEcriture, Sens
from .orm import ecritures, lignes_ecriture
from .periodes import Periode, verifier_hors_periode_close
from .service import LedgerService


class PostgresLedgerService(LedgerService):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer(self, ecriture: Ecriture) -> EcritureId:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            inserer_ecriture(connexion, ecriture)
        return ecriture.id

    def periodes_closes(self, dossier_id: DossierId) -> tuple[Periode, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return _periodes_closes(connexion, dossier_id)

    def grand_livre(self, dossier_id: DossierId) -> tuple[Ecriture, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            entetes = _lire_entetes(connexion, dossier_id)
            lignes_par_ecriture = _lire_lignes(connexion, dossier_id)
        return tuple(
            dataclasses.replace(entete, lignes=tuple(lignes_par_ecriture.get(eid, ())))
            for eid, entete in entetes.items()
        )


def inserer_ecriture(connexion: Connection, ecriture: Ecriture) -> None:
    """Écrit une écriture dans la transaction de l'appelant, après les mêmes
    contrôles que `enregistrer` : équilibre (I1) et période ouverte (I4).
    Sert à écrire une écriture avec un autre fait, tout ou rien (AXE-852).
    Le contexte RLS doit déjà être posé sur `connexion`."""
    verifier_equilibre(ecriture)
    verifier_hors_periode_close(ecriture.date, _periodes_closes(connexion, ecriture.dossier_id))
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
            numero=ligne.numero,
            valide_le=ligne.valide_le,
        )
        for ligne in resultat
    }


def _lire_lignes(connexion: Connection, dossier_id: DossierId) -> dict[str, list[LigneEcriture]]:
    """Les lignes du dossier par jointure (index `ecritures(dossier_id)` et
    `lignes_ecriture(ecriture_id)`), plutôt qu'une liste `IN` de tous les
    identifiants du dossier (AXE-824)."""
    resultat = connexion.execute(
        select(lignes_ecriture)
        .join(ecritures, ecritures.c.id == lignes_ecriture.c.ecriture_id)
        .where(ecritures.c.dossier_id == dossier_id)
    )
    par_ecriture: dict[str, list[LigneEcriture]] = {}
    for row in resultat:
        par_ecriture.setdefault(row.ecriture_id, []).append(
            LigneEcriture(
                compte=row.compte,
                sens=Sens[row.sens],
                montant=Money(centimes=row.montant_centimes, devise=row.devise),
                analytique=row.analytique,
                code_tva=row.code_tva,
            )
        )
    return par_ecriture


def soldes_par_journal(engine: Engine) -> list[SoldeJournal]:
    """Débits et crédits par dossier et par journal, toute la base, en une
    requête (contrôle I7 des tâches planifiées, connexion propriétaire)."""
    requete = text(
        """
        SELECT e.dossier_id, e.journal,
               COALESCE(SUM(l.montant_centimes) FILTER (WHERE l.sens = 'DEBIT'), 0),
               COALESCE(SUM(l.montant_centimes) FILTER (WHERE l.sens = 'CREDIT'), 0)
          FROM ecritures e JOIN lignes_ecriture l ON l.ecriture_id = e.id
         GROUP BY e.dossier_id, e.journal
         ORDER BY e.dossier_id, e.journal
        """
    )
    with engine.connect() as connexion:
        return [
            SoldeJournal(DossierId(dossier), journal, int(debit), int(credit))
            for dossier, journal, debit, credit in connexion.execute(requete)
        ]
