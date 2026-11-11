"""AXE-872 : chaque dossier se synchronise par son branchement Digifactory,
et les contacts de tous les branchements du portefeuille sont lus."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

import pytest

from axelcompta import worker
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.synchro_digifactory import repartir_par_branchement
from axelcompta.tenants.branchements import Branchement, BranchementsMemoire, nouveau
from axelcompta.tenants.models import Dossier
from axelcompta.worker import CLE_BRANCHEMENT, contacts_du_portefeuille

T, AUTRE = TenantId("t"), TenantId("autre")
LE = datetime(2026, 11, 11)


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _dossier(id_: str, tenant: TenantId = T) -> Dossier:
    return Dossier(
        DossierId(id_),
        tenant,
        "SAS",
        "IS",
        "reel_normal",
        id_,
        "assujetti_taux_reduit",
        date(2026, 1, 1),
        contact_nr=id_,
    )


def _digi(depot: BranchementsMemoire, nom: str, jeton: str) -> Branchement:
    cree = nouveau(depot.lister(T), T, "digifactory", "digifactory", nom, {"jeton": jeton})
    depot.enregistrer([cree], "admin", LE)
    return cree


def test_les_dossiers_sont_regroupes_par_branchement_et_sans_branchement_par_l_env() -> None:
    depot = BranchementsMemoire()
    principal, second = _digi(depot, "Compte 1", "j1"), _digi(depot, "Compte 2", "j2")
    depot.choisir_pour_dossier(T, DossierId("b"), "digifactory", second.id)
    dossiers = (_dossier("a"), _dossier("b"), _dossier("c"), _dossier("z", AUTRE))

    groupes = repartir_par_branchement(dossiers, depot)

    vus = {(b.nom if b else None): [d.id for d in g] for b, g in groupes}
    assert vus == {"Compte 1": ["a", "c"], "Compte 2": ["b"], None: ["z"]}
    assert principal.par_defaut


class _Client:
    def __init__(self, contacts: dict[str, Any]) -> None:
        self._contacts = contacts

    async def contacts(self) -> dict[str, Any]:
        return self._contacts

    async def aclose(self) -> None:
        return None


def test_les_contacts_de_chaque_compte_sont_lus_et_le_second_garde_son_origine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    depot = BranchementsMemoire()
    _digi(depot, "Compte 1", "j1")
    second = _digi(depot, "Compte 2", "j2")
    par_jeton = {
        "j1": {"1": {"nr": 1}, "2": {"nr": 2}},
        "j2": {"2": {"nr": 2, "doublon": True}, "3": {"nr": 3}},
    }
    monkeypatch.setattr(
        worker,
        "client_digifactory",
        lambda b: _Client(par_jeton[b.parametres()["jeton"]]),
    )

    contacts = asyncio.run(contacts_du_portefeuille(depot.lister(T)))

    assert set(contacts) == {"1", "2", "3"}
    assert CLE_BRANCHEMENT not in contacts["1"] and "doublon" not in contacts["2"]
    assert contacts["3"][CLE_BRANCHEMENT] == second.id
