"""AXE-839 : une erreur métier répond 4xx avec sa phrase, jamais 500."""

from __future__ import annotations

import importlib
import pkgutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import axelcompta
from axelcompta.api.erreurs import brancher_erreurs, statut_de
from axelcompta.core.errors import (
    Conflit,
    DomaineError,
    Introuvable,
    InvariantViole,
    SaisieInvalide,
)


def _app_qui_leve(erreur: Exception) -> TestClient:
    app = FastAPI()
    brancher_erreurs(app)

    @app.get("/essai")
    def essai() -> None:
        raise erreur

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("erreur", "statut"),
    [
        (DomaineError("refusé"), 400),
        (Conflit("déjà clos"), 409),
        (Introuvable("absent"), 404),
        (SaisieInvalide("montant négatif"), 422),
    ],
)
def test_chaque_famille_a_son_code_et_garde_sa_phrase(erreur: DomaineError, statut: int) -> None:
    reponse = _app_qui_leve(erreur).get("/essai")
    assert reponse.status_code == statut
    assert reponse.json() == {"detail": str(erreur)}


def test_un_bug_reste_un_500() -> None:
    assert _app_qui_leve(InvariantViole("débit ≠ crédit")).get("/essai").status_code == 500


def _toutes_les_sous_classes(racine: type[DomaineError]) -> set[type[DomaineError]]:
    trouvees: set[type[DomaineError]] = set()
    a_voir = [racine]
    while a_voir:
        for sous in a_voir.pop().__subclasses__():
            if sous not in trouvees:
                trouvees.add(sous)
                a_voir.append(sous)
    return trouvees


def test_toutes_les_erreurs_metier_du_code_repondent_4xx() -> None:
    """Charge tous les modules, puis vérifie chaque sous-classe de
    `DomaineError` : aucune ne peut sortir en 500."""
    for module in pkgutil.walk_packages(axelcompta.__path__, "axelcompta."):
        if module.name.endswith(("__main__", ".ml", ".cli")) or ".ml." in module.name:
            continue
        importlib.import_module(module.name)
    classes = _toutes_les_sous_classes(DomaineError)
    assert len(classes) >= 20  # garde-fou : le parcours a bien chargé le code
    for classe in classes:
        assert 400 <= statut_de(DomaineError.__new__(classe)) < 500, classe


def test_les_erreurs_rattachees_a_une_famille() -> None:
    """Ce que les routes renvoyaient déjà à la main reste identique."""
    from axelcompta.affectations import AffectationImpossible
    from axelcompta.closing.paie import BulletinIncoherent
    from axelcompta.closing.provisions import ProvisionInvalide
    from axelcompta.demo_comptes import CompteDejaInviteError, InvitationAbsente, InvitationFermee
    from axelcompta.ledger.periodes import PeriodeClose
    from axelcompta.tenants.exercices import ExerciceDejaClos

    attendus: dict[type[DomaineError], int] = {
        PeriodeClose: 409,
        ExerciceDejaClos: 409,
        AffectationImpossible: 409,
        CompteDejaInviteError: 409,
        InvitationFermee: 409,
        InvitationAbsente: 404,
        ProvisionInvalide: 422,
        BulletinIncoherent: 422,
    }
    for classe, statut in attendus.items():
        assert statut_de(DomaineError.__new__(classe)) == statut, classe
