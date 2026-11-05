"""Orchestration multi-dossiers : un dossier en échec ou sans contact ne
bloque pas les autres."""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import date, datetime
from typing import Any, cast

from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_bancaires import CompteBancaireMemoire
from axelcompta.ingestion.consentement import ReleveSante, StatutConsentement
from axelcompta.ingestion.journal import InMemoryJournalIngestion
from axelcompta.ingestion.providers.base import LotTransactions
from axelcompta.ingestion.providers.digifactory import DigifactoryProvider
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie, charger_regles
from axelcompta.synchro_digifactory import (
    ResultatDossier,
    _relever_consentements,
    synchroniser_dossiers,
)
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.propositions import InMemoryPropositionRepository

BASE = Dossier(
    id=DossierId("a"),
    tenant_id=TenantId("t"),
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="franchise",
    nom="A",
    tva_recettes_regime="franchise",
    exercice_debut=date(2026, 1, 1),
    contact_nr="1",
)
PAYLOAD = {
    "acc": [
        {
            "id": "t1",
            "provider_description": "CARTE TOTAL",
            "amount": -10.0,
            "date": "2026-03-01",
            "updated_at": "2026-03-01 10:00:00",
            "deleted": False,
            "future": False,
        }
    ]
}


class _SourceQuiEchoueSurB:
    def __init__(self) -> None:
        self._vraie = DigifactoryProvider(payload=PAYLOAD)

    async def lire_lot(self, dossier: Dossier, depuis_maj: datetime | None) -> LotTransactions:
        if dossier.id == "b":
            raise RuntimeError("Digifactory a répondu 500")
        return await self._vraie.lire_lot(dossier, depuis_maj)


def test_un_dossier_en_echec_ou_sans_contact_ne_bloque_pas_les_autres() -> None:
    dossiers = (
        BASE,
        dataclasses.replace(BASE, id=DossierId("b"), contact_nr="2"),
        dataclasses.replace(BASE, id=DossierId("c"), contact_nr=None),
        dataclasses.replace(BASE, id=DossierId("d"), contact_nr="4"),
    )
    ledger = InMemoryLedgerService()

    resultats = asyncio.run(
        synchroniser_dossiers(
            dossiers,
            _SourceQuiEchoueSurB(),
            InMemoryJournalIngestion(),
            ledger,
            InMemoryPropositionRepository(),
            RulesAndMlPipeline(regles=charger_regles(), modele=None),
            charger_compte_par_categorie(),
        )
    )

    par_id = {r.dossier_id: r for r in resultats}
    resultat_a, resultat_b, resultat_c, resultat_d = (
        par_id[DossierId("a")],
        par_id[DossierId("b")],
        par_id[DossierId("c")],
        par_id[DossierId("d")],
    )
    assert resultat_a.rapport is not None and resultat_a.rapport.nouvelles == 1
    assert resultat_b.erreur is not None and "500" in resultat_b.erreur
    assert resultat_c.ignore is not None
    assert resultat_d.rapport is not None and resultat_d.rapport.nouvelles == 1
    assert len(ledger.grand_livre(DossierId("d"))) == 1


def test_un_lot_vide_est_un_succes_et_un_401_ne_bloque_pas_le_suivant() -> None:
    class _Source:
        async def lire_lot(self, dossier: Dossier, depuis_maj: datetime | None) -> LotTransactions:
            if dossier.id == "a":
                return LotTransactions(transactions=())
            if dossier.id == "b":
                raise RuntimeError("401 sur /transactions/2 — token invalide/révoqué")
            return await DigifactoryProvider(payload=PAYLOAD).lire_lot(dossier, depuis_maj)

    dossiers = (
        BASE,
        dataclasses.replace(BASE, id=DossierId("b"), contact_nr="2"),
        dataclasses.replace(BASE, id=DossierId("c"), contact_nr="3"),
    )
    resultats = asyncio.run(
        synchroniser_dossiers(
            dossiers,
            _Source(),
            InMemoryJournalIngestion(),
            InMemoryLedgerService(),
            InMemoryPropositionRepository(),
            RulesAndMlPipeline(regles=charger_regles(), modele=None),
            charger_compte_par_categorie(),
        )
    )
    par_id = {r.dossier_id: r for r in resultats}
    vide, echec, suivant = (
        par_id[DossierId("a")],
        par_id[DossierId("b")],
        par_id[DossierId("c")],
    )
    assert vide.rapport is not None and vide.rapport.nouvelles == 0
    assert echec.erreur is not None
    assert suivant.rapport is not None and suivant.rapport.nouvelles == 1


class _ClientComptes:
    def __init__(self, reponses: dict[str, object]) -> None:
        self._reponses = reponses

    async def accounts(self, contact_nr: str | int) -> dict[str, Any] | list[Any]:
        reponse = self._reponses[str(contact_nr)]
        if isinstance(reponse, Exception):
            raise reponse
        return cast("dict[str, Any] | list[Any]", reponse)


class _Consentements:
    def __init__(self) -> None:
        self.statuts: dict[DossierId, StatutConsentement] = {}

    def enregistrer(
        self,
        dossier_id: DossierId,
        expire_le: date | None,
        statut: StatutConsentement,
        releve_le: datetime,
        sante: ReleveSante,
    ) -> None:
        self.statuts[dossier_id] = statut


def test_le_releve_garde_le_nom_et_le_solde_de_chaque_compte_bancaire() -> None:
    """AXE-832 : `/accounts` donne nom et solde ; un compte sans transaction
    reçoit quand même son sous-compte. Un échec sur un dossier n'arrête pas
    les autres."""
    b = dataclasses.replace(BASE, id=DossierId("b"), contact_nr="2")
    client = _ClientComptes(
        {
            "1": {
                "67078853": {"id": "67078853", "name": "Compte Courant", "balance": 733.49},
                "67078894": {"id": "67078894", "name": "Compte PRO", "balance": 1.1},
            },
            "2": RuntimeError("Digifactory a répondu 500"),
        }
    )
    consentements = _Consentements()
    comptes = CompteBancaireMemoire()
    resultats = [ResultatDossier(BASE.id), ResultatDossier(b.id)]

    releves = asyncio.run(
        _relever_consentements(
            client, (BASE, b), resultats, (consentements, comptes), date(2026, 11, 5)
        )
    )

    assert [r.dossier_id for r in releves] == ["a", "b"]
    assert BASE.id in consentements.statuts and b.id not in consentements.statuts
    par_id = {c.identifiant: c for c in comptes.lister(BASE.id)}
    assert par_id["67078853"].compte_comptable == "5121"
    assert par_id["67078853"].nom == "Compte Courant"
    assert par_id["67078853"].solde_banque_cts == 73_349
    assert par_id["67078894"].solde_banque_cts == 110
    assert comptes.lister(b.id) == ()
