"""Appels réels à Digifactory. Hors CI : `pytest -m digifactory`.

Le jeton est celui du branchement Digifactory du portefeuille de démo
(Intégrations), pas une variable d'environnement. Ne conserve aucun
libellé, IBAN ni nom. Vérifie seulement que le parseur accepte le
payload du jour et sort des centimes entiers.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId
from axelcompta.ingestion.digifactory_contacts import TENANT_DEMO
from axelcompta.ingestion.providers.digifactory import (
    DigifactoryHttpClient,
    DigifactoryProvider,
    parser_lot,
)
from axelcompta.synchro_digifactory import TYPE_DIGIFACTORY, client_digifactory
from axelcompta.tenants.branchements import choisir
from axelcompta.tenants.branchements_postgres import PostgresBranchements

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

pytestmark = pytest.mark.digifactory


def _client() -> DigifactoryHttpClient:
    if not os.environ.get("DATABASE_URL") or not os.environ.get("AXELCOMPTA_CLE_INTEGRATIONS"):
        pytest.skip("branchement Digifactory : base ou clé absente")
    branchement = choisir(
        PostgresBranchements(engine_depuis_env()).lister(TENANT_DEMO),
        TYPE_DIGIFACTORY,
        None,
    )
    if branchement is None:
        pytest.skip("aucun branchement Digifactory actif")
    return client_digifactory(branchement)


def test_le_token_ouvre_les_contacts_et_les_comptes() -> None:
    async def lire() -> tuple[int, int]:
        client = _client()
        try:
            sante = await DigifactoryProvider(client_reel=client).health()
            assert sante.ok, sante.message
            contacts = await client.contacts()
            assert isinstance(contacts, dict) and contacts
            comptes_dictionnaire = 0
            for nr, contact in contacts.items():
                assert isinstance(contact, dict)
                assert str(contact.get("nr")) == str(nr)
                comptes = await client.accounts(nr)
                assert isinstance(comptes, dict | list)
                if isinstance(comptes, dict) and comptes:
                    comptes_dictionnaire += 1
            return len(contacts), comptes_dictionnaire
        finally:
            await client.aclose()

    nb_contacts, avec_banque = asyncio.run(lire())
    assert nb_contacts >= 1
    assert avec_banque >= 1


def test_les_transactions_reelles_sont_des_centimes_entiers() -> None:
    async def lire() -> tuple[int, int]:
        client = _client()
        try:
            contacts = await client.contacts()
            total = 0
            rejets = 0
            for nr in contacts:
                lot = parser_lot(await client.transactions(nr), DossierId(f"probe-{nr}"))
                total += len(lot.transactions)
                rejets += len(lot.rejets)
                assert all(isinstance(t.montant_cts, int) for t in lot.transactions)
                assert len({t.id for t in lot.transactions}) == len(lot.transactions)
            return total, rejets
        finally:
            await client.aclose()

    total, rejets = asyncio.run(lire())
    assert total > 0
    assert rejets == 0
