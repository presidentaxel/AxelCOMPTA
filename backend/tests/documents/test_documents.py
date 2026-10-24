"""Refus et cloisonnement, sans Postgres."""

from __future__ import annotations

from pathlib import Path

import pytest

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.documents.memoire import StockageMemoire
from axelcompta.documents.preparer import TAILLE_MAX_OCTETS, JustificatifRefuse, preparer

TENANT = TenantId("tenant-a")
DOSSIER = DossierId("dossier-1")
ECRITURE = EcritureId("ecriture-1")


def test_une_photo_vide_est_refusee() -> None:
    with pytest.raises(JustificatifRefuse):
        preparer(TENANT, DOSSIER, ECRITURE, b"", ".jpg")


def test_un_identifiant_avec_slash_est_refuse() -> None:
    with pytest.raises(JustificatifRefuse):
        preparer(TENANT, DossierId("../autre"), ECRITURE, b"photo", ".jpg")


def test_au_dela_de_8_mo_est_refuse() -> None:
    with pytest.raises(JustificatifRefuse):
        preparer(TENANT, DOSSIER, ECRITURE, b"x" * (TAILLE_MAX_OCTETS + 1), ".jpg")


def test_un_autre_tenant_ne_voit_pas_la_photo() -> None:
    photo = preparer(TENANT, DOSSIER, ECRITURE, b"photo", ".jpg")
    stockage = StockageMemoire()
    stockage.poser(photo, b"photo")
    assert stockage.contient(TenantId("tenant-b"), DOSSIER, ECRITURE) is False
    assert stockage.lire(TENANT, DOSSIER, ECRITURE) == b"photo"


def test_le_fichier_reste_sous_la_racine(tmp_path: Path) -> None:
    from axelcompta.documents.fichier import StockageFichier

    stockage = StockageFichier(tmp_path)
    photo = preparer(TENANT, DOSSIER, ECRITURE, b"photo", ".JPG")
    stockage.poser(photo, b"photo")
    chemin = tmp_path / "tenant-a" / "dossier-1" / "ecriture-1.jpg"
    assert chemin.read_bytes() == b"photo"
    assert stockage.contient(TENANT, DOSSIER, ECRITURE) is True
