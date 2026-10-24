"""Deux implémentations, même contrat : mémoire et fichier, cloisonnés par tenant."""

from __future__ import annotations

from pathlib import Path

import pytest

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.demo_justificatifs import (
    FichierJustificatifRepository,
    InMemoryJustificatifRepository,
    JustificatifRepository,
)

TENANT = TenantId("tenant-demo")
KARIM = DossierId("DEMO_karim")
SOPHIE = DossierId("DEMO_sophie")
ECRITURE = EcritureId("ecriture-1")
AUTRE = EcritureId("ecriture-2")


@pytest.fixture(params=["memoire", "fichier"])
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> JustificatifRepository:
    if request.param == "memoire":
        return InMemoryJustificatifRepository()
    return FichierJustificatifRepository(tmp_path)


def test_aucun_justificatif_au_depart(repo: JustificatifRepository) -> None:
    assert repo.a_un_justificatif(TENANT, KARIM, ECRITURE) is False


def test_enregistrer_rend_a_un_justificatif_vrai(repo: JustificatifRepository) -> None:
    repo.enregistrer(TENANT, KARIM, ECRITURE, b"contenu-photo", ".jpg")
    assert repo.a_un_justificatif(TENANT, KARIM, ECRITURE) is True


def test_une_autre_ecriture_reste_sans_justificatif(repo: JustificatifRepository) -> None:
    repo.enregistrer(TENANT, KARIM, ECRITURE, b"contenu-photo", ".jpg")
    assert repo.a_un_justificatif(TENANT, KARIM, AUTRE) is False


def test_presents_ne_liste_que_le_dossier(repo: JustificatifRepository) -> None:
    repo.enregistrer(TENANT, KARIM, ECRITURE, b"contenu-photo", ".jpg")
    repo.enregistrer(TENANT, SOPHIE, AUTRE, b"autre-photo", ".jpg")
    assert repo.presents(TENANT, KARIM) == frozenset({ECRITURE})


def test_un_autre_dossier_ou_tenant_reste_sans_justificatif(repo: JustificatifRepository) -> None:
    repo.enregistrer(TENANT, KARIM, ECRITURE, b"contenu-photo", ".jpg")
    assert repo.a_un_justificatif(TENANT, SOPHIE, ECRITURE) is False
    assert repo.a_un_justificatif(TenantId("autre-tenant"), KARIM, ECRITURE) is False


def test_fichier_repository_ecrit_vraiment_sur_disque(tmp_path: Path) -> None:
    repo = FichierJustificatifRepository(tmp_path)
    repo.enregistrer(TENANT, KARIM, ECRITURE, b"contenu-photo", ".jpg")
    chemin = tmp_path / "tenant-demo" / "DEMO_karim" / "ecriture-1.jpg"
    assert chemin.read_bytes() == b"contenu-photo"
