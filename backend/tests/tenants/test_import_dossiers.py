"""AXE-809 : créer les dossiers d'un portefeuille depuis un fichier CSV."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.import_dossiers import (
    COLONNES,
    FichierIllisible,
    lire_csv,
    rapport,
    siren_valide,
)
from axelcompta.tenants.sirene import FicheSirene

T = TenantId("t")


def _siren(n: int) -> str:
    """Le n-ième SIREN à clé de Luhn valide (8 chiffres + clé)."""
    base = f"{100_000_00 + n:08d}"
    for cle in range(10):
        if siren_valide(base + str(cle)):
            return base + str(cle)
    raise AssertionError


def _ligne(n: int, **autres: str) -> dict[str, str]:
    ligne = {
        "siren": _siren(n),
        "nom": f"Société {n}",
        "forme_juridique": "SASU",
        "regime_imposition": "IS",
        "regime_tva": "reel_normal",
        "tva_recettes_regime": "assujetti_taux_reduit",
        "exercice_debut": "2026-01-01",
        "exercice_fin": "2026-12-31",
        "option_ir_debut": "",
        "contact_digifactory": "",
    }
    return ligne | autres


def test_la_cle_du_siren_est_verifiee() -> None:
    assert siren_valide("552100554")  # SIREN réel public
    assert not siren_valide("552100555")
    assert not siren_valide("55210055")


def test_deux_cents_lignes_dont_cinq_fausses_et_aucun_doublon_au_second_depot() -> None:
    """Critère du ticket."""
    lignes = [_ligne(n) for n in range(195)]
    lignes += [
        _ligne(195, siren="123456789"),  # clé fausse
        _ligne(196, regime_imposition="IR"),  # SASU à l'IR hors option : refusée
        _ligne(197, exercice_debut="01/01/2026"),  # date illisible
        _ligne(198, exercice_fin="2025-06-30"),  # fin avant le début
        _ligne(0),  # deux fois dans le fichier
    ]

    premier = rapport(T, lignes, existants=())
    second = rapport(T, lignes, existants=[d.id for d in premier.valides])

    assert (len(premier.valides), premier.en_erreur) == (195, 5)
    raisons = [e for ligne in premier.lignes for e in ligne.erreurs]
    assert any("SIREN invalide" in r for r in raisons)
    assert any("une SASU ne peut pas être au régime « IR »" in r for r in raisons)
    assert any("Deux fois dans le fichier" in r for r in raisons)
    assert len(second.valides) == 0
    assert premier.lignes[0].numero == 2  # la ligne 1 est l'en-tête


def test_le_contact_digifactory_donne_l_identifiant_du_dossier() -> None:
    (ligne,) = rapport(T, [_ligne(1, contact_digifactory="22755")], ()).lignes
    assert ligne.dossier is not None and ligne.dossier.id == DossierId("DIGI_22755")
    assert ligne.dossier.contact_nr == "22755"


def test_sirene_signale_un_ecart_sans_bloquer() -> None:
    fiche = FicheSirene(_siren(1), "5710", "49.32Z", "A", date(2020, 1, 1))  # SAS
    (ligne,) = rapport(T, [_ligne(1, forme_juridique="EURL")], (), lambda _s: fiche).lignes
    assert ligne.dossier is not None
    assert ligne.avertissements == ("Forme EURL dans le fichier, SAS chez Sirene.",)


def test_le_csv_francais_se_lit_et_un_fichier_sans_colonnes_est_refuse() -> None:
    texte = ";".join(COLONNES) + "\n" + ";".join(_ligne(1).values()) + "\n"
    assert lire_csv(("﻿" + texte).encode())[0]["nom"] == "Société 1"
    with pytest.raises(FichierIllisible, match="Colonnes manquantes"):
        lire_csv(b"nom,siren\nx,1\n")
