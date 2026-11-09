"""Comptes bancaires d'un dossier, en Postgres (AXE-832)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import and_, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine, Row

from axelcompta.core.ids import DossierId, UserId
from axelcompta.core.rls import appliquer_rls
from axelcompta.workflow.audit import ACTE_COMPTE_ECARTE, ACTE_COMPTE_RETENU, noter

from .comptes_bancaires import (
    NOMBRE_MAX_COMPTES,
    CompteBancaire,
    CompteInconnu,
    CompteReleve,
    TropDeComptesBancaires,
    compte_comptable_suivant,
)
from .orm import comptes_bancaires


def _compte(ligne: Row[tuple[object, ...]]) -> CompteBancaire:
    return CompteBancaire(
        dossier_id=DossierId(str(ligne.dossier_id)),
        identifiant=str(ligne.identifiant),
        compte_comptable=str(ligne.compte_comptable),
        nom=ligne.nom,
        solde_banque_cts=ligne.solde_banque_cts,
        solde_releve_le=ligne.solde_releve_le,
        retenu=ligne.retenu,
        a_relire=bool(ligne.a_relire),
    )


class PostgresCompteBancaireRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(self, dossier_id: DossierId) -> tuple[CompteBancaire, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return self._lister(connexion, dossier_id)

    def ajouter(self, compte: CompteBancaire) -> CompteBancaire:
        """Deux synchros simultanées peuvent viser le même numéro : la
        contrainte unique en refuse une, qui reprend au numéro libre suivant.
        Borné par `NOMBRE_MAX_COMPTES` tentatives."""
        candidat = compte
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            for _ in range(NOMBRE_MAX_COMPTES):
                connexion.execute(
                    insert(comptes_bancaires)
                    .values(
                        dossier_id=candidat.dossier_id,
                        identifiant=candidat.identifiant,
                        compte_comptable=candidat.compte_comptable,
                        nom=candidat.nom,
                        retenu=candidat.retenu,
                        cree_le=datetime.now(UTC),
                    )
                    .on_conflict_do_nothing()
                )
                existants = self._lister(connexion, compte.dossier_id)
                for existant in existants:
                    if existant.identifiant == compte.identifiant:
                        return existant
                suivant = compte_comptable_suivant(c.compte_comptable for c in existants)
                candidat = replace(candidat, compte_comptable=suivant)
        raise TropDeComptesBancaires(f"{compte.dossier_id} : numéro de compte introuvable")

    def relever(self, dossier_id: DossierId, releve: CompteReleve, releve_le: datetime) -> None:
        valeurs: dict[str, object] = {
            "solde_banque_cts": releve.solde_cts,
            "solde_releve_le": releve_le,
        }
        if releve.nom is not None:
            valeurs["nom"] = releve.nom
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(comptes_bancaires)
                .where(
                    and_(
                        comptes_bancaires.c.dossier_id == dossier_id,
                        comptes_bancaires.c.identifiant == releve.identifiant,
                    )
                )
                .values(**valeurs)
            )

    def decider(
        self, dossier_id: DossierId, compte_comptable: str, retenu: bool, par: UserId, le: datetime
    ) -> CompteBancaire:
        """Le choix et sa trace dans la même transaction (journal d'audit)."""
        cible = and_(
            comptes_bancaires.c.dossier_id == dossier_id,
            comptes_bancaires.c.compte_comptable == compte_comptable,
        )
        # Retenu après coup : la prochaine synchro relit l'historique.
        relire = or_(
            comptes_bancaires.c.a_relire,
            and_(literal(retenu), comptes_bancaires.c.retenu.is_not(True)),
        )
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                update(comptes_bancaires)
                .where(cible)
                .values(retenu=retenu, a_relire=relire)
                .returning(*comptes_bancaires.c)
            ).first()
            if ligne is None:
                raise CompteInconnu(f"{dossier_id} : pas de compte {compte_comptable}")
            acte = ACTE_COMPTE_RETENU if retenu else ACTE_COMPTE_ECARTE
            noter(connexion, dossier_id, acte, compte_comptable, par, le)
        return _compte(ligne)

    def relu(self, dossier_id: DossierId) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(comptes_bancaires)
                .where(comptes_bancaires.c.dossier_id == dossier_id, comptes_bancaires.c.a_relire)
                .values(a_relire=False)
            )

    @staticmethod
    def _lister(connexion: Connection, dossier_id: DossierId) -> tuple[CompteBancaire, ...]:
        lignes = connexion.execute(
            select(comptes_bancaires).where(comptes_bancaires.c.dossier_id == dossier_id)
        ).all()
        comptes = [_compte(ligne) for ligne in lignes]
        return tuple(sorted(comptes, key=lambda c: (len(c.compte_comptable), c.compte_comptable)))
