"""AXE-922 : poser les noms attendus sur les liens Rollee d'avant la PR 170."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from cryptography.fernet import Fernet

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_rollee import UtilisateurRollee
from axelcompta.ingestion.liens_rollee import Lien
from axelcompta.noms_attendus_rollee import a_completer, poser_noms_attendus
from axelcompta.rapprochement_rollee_service import DepotsRapprochement
from tests.test_rapprochement_rollee_service import LE, FauxRollee, T, _depots

D = DossierId("d-iban")  # son contact Digifactory : Elodie MARTIN


class Flotte(FauxRollee):
    """Un user « flotte » qui porte deux comptes Allocab : l'un au nom du
    chauffeur du dossier, l'autre au nom d'un autre chauffeur."""

    async def comptes(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {"id": "acc-elodie", "name": "allocab-fleet-rev", "connected": True},
            {"id": "acc-autre", "name": "allocab-fleet-rev", "connected": True},
        ]

    async def profil(self, compte_id: str) -> dict[str, Any]:
        if compte_id == "acc-elodie":
            return {"full_name": "MARTIN Elodie"}
        return {"full_name": "GABI GALESSAN LEVAH"}


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXELCOMPTA_CLE_INTEGRATIONS", Fernet.generate_key().decode())


def _avec_lien(origine: str = "manuel") -> DepotsRapprochement:
    depots = _depots(Flotte())
    (branchement,) = depots.services.branchements.lister(T)
    lien = Lien(D, "u-flotte", branchement.id, origine, LE, None, "marie")  # type: ignore[arg-type]
    depots.liens.lier(lien)
    depots.services.comptes.enregistrer_utilisateur(
        UtilisateurRollee(D, "u-flotte", branchement.id), LE
    )
    return depots


def test_seuls_les_liens_auto_ou_manuels_sans_noms_sont_a_completer() -> None:
    sans = Lien(D, "u1", "b1", "manuel", LE)
    cree = Lien(D, "u2", "b1", "cree", LE)
    deja = Lien(D, "u3", "b1", "auto", LE, "iban", None, ("x",))
    assert a_completer([sans, cree, deja]) == [sans]


def test_la_simulation_dit_ce_qui_serait_retenu_sans_rien_ecrire() -> None:
    depots = _avec_lien()
    lignes = asyncio.run(poser_noms_attendus(depots, T, False))
    assert lignes[0].endswith("u-flotte… : 2 compte(s), 1 retenu(s), 1 au nom d'un autre chauffeur")
    assert "GABI" not in " ".join(lignes) and "MARTIN" not in " ".join(lignes)
    assert lignes[-1] == "1 lien(s) à compléter (simulation : rien n'est écrit)."
    lien = depots.liens.lien(D)
    assert lien is not None and lien.noms_attendus is None
    assert depots.services.comptes.comptes(D) == []


def test_appliquer_pose_les_noms_et_ne_retient_que_le_compte_du_chauffeur() -> None:
    depots = _avec_lien()
    asyncio.run(poser_noms_attendus(depots, T, True))
    lien = depots.liens.lien(D)
    assert lien is not None and lien.noms_attendus and len(lien.noms_attendus) == 1
    # En base, lien et user Rollee sont la même ligne ; en mémoire, deux dépôts.
    depots.services.comptes.enregistrer_utilisateur(
        UtilisateurRollee(D, "u-flotte", lien.branchement_id, lien.noms_attendus), LE
    )
    asyncio.run(poser_noms_attendus(depots, T, True))  # plus rien à compléter
    from axelcompta.plateformes_rollee import relire_comptes

    (dossier,) = [d for d in depots.dossiers.lister_par_tenant(T) if d.id == D]
    comptes = {c.account_id: c for c in asyncio.run(relire_comptes(depots.services, dossier))}
    assert comptes["acc-elodie"].retenu
    assert "acc-autre" not in comptes  # AXE-923 : ni relié, ni montré


def test_un_lien_cree_par_le_chauffeur_n_est_pas_touche() -> None:
    depots = _avec_lien("cree")
    assert asyncio.run(poser_noms_attendus(depots, T, True)) == ["Aucun lien Rollee à compléter."]
