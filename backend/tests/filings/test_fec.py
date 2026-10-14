from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.filings.fec import (
    COLONNES_FEC,
    FecInvalide,
    exporter_fec,
    libelle_compte,
    nom_fichier_fec,
    valider_fec,
)
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

DOSSIER = DossierId("d1")


def _ecriture_uber() -> Ecriture:
    return Ecriture(
        id=EcritureId("e1"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 9, 3),
        libelle="Règlement Uber",
        reference_piece="PIECE-1",
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(848_00)),
            LigneEcriture("706", Sens.CREDIT, Money(753_45)),
            LigneEcriture("44571", Sens.CREDIT, Money(94_55)),
        ),
    )


def test_len_de_lentete_est_les_18_colonnes_normees() -> None:
    assert len(COLONNES_FEC) == 18


def test_exporte_une_ligne_par_ligne_decriture_avec_entete() -> None:
    fec = exporter_fec((_ecriture_uber(),))
    lignes = fec.rstrip("\r\n").split("\r\n")
    assert lignes[0] == "\t".join(COLONNES_FEC)
    assert len(lignes) == 1 + 3  # entête + 3 lignes d'écriture


def test_champs_debit_credit_et_date_correctement_formates() -> None:
    fec = exporter_fec((_ecriture_uber(),))
    lignes = fec.rstrip("\r\n").split("\r\n")[1:]
    par_compte = {ligne.split("\t")[4]: ligne.split("\t") for ligne in lignes}

    ligne_512 = par_compte["512"]
    assert ligne_512[3] == "20260903"  # EcritureDate, YYYYMMDD
    # A.47 A-1 : « la virgule sépare la fraction entière de la partie décimale ».
    assert ligne_512[11] == "848,00"  # Debit
    assert ligne_512[12] == "0,00"  # Credit

    ligne_706 = par_compte["706"]
    assert ligne_706[11] == "0,00"
    assert ligne_706[12] == "753,45"


def test_libelle_compte_et_journal_renseignes() -> None:
    fec = exporter_fec((_ecriture_uber(),))
    ligne_512 = next(ligne for ligne in fec.split("\r\n") if "\t512\t" in ligne)
    champs = ligne_512.split("\t")
    assert champs[0] == "BQ"
    assert champs[1] == "Banque"
    assert champs[5] == "Banques"  # CompteLib


def test_trie_par_date() -> None:
    plus_recente = Ecriture(
        id=EcritureId("e2"),
        dossier_id=DOSSIER,
        journal=Journal.OD,
        date=date(2026, 9, 10),
        libelle="Plus tard",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(10_00)),
            LigneEcriture("706", Sens.CREDIT, Money(10_00)),
        ),
    )
    fec = exporter_fec((plus_recente, _ecriture_uber()))
    dates = [ligne.split("\t")[3] for ligne in fec.rstrip("\r\n").split("\r\n")[1:]]
    assert dates == sorted(dates)


def _ecriture(identifiant: str, jour: int, journal: Journal = Journal.BQ) -> Ecriture:
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=DOSSIER,
        journal=journal,
        date=date(2026, 9, jour),
        libelle="Libellé\tavec tabulation\net retour",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(1_234_567_89)),
            LigneEcriture("706", Sens.CREDIT, Money(1_234_567_89)),
        ),
    )


def test_ecriture_num_est_une_sequence_continue_et_chronologique() -> None:
    # BOI-CF-IOR-60-40-20 §40 : numérotation sans rupture ni inversion,
    # quels que soient les identifiants internes (« settlement-34 »...).
    fec = exporter_fec((_ecriture("settlement-34", 20), _ecriture("categorise-1", 5)))
    lignes = [ligne.split("\t") for ligne in fec.rstrip("\r\n").split("\r\n")[1:]]
    assert [ligne[2] for ligne in lignes] == ["1", "1", "2", "2"]
    assert [ligne[3] for ligne in lignes] == ["20260905"] * 2 + ["20260920"] * 2


def test_a_nouveaux_en_tete_du_meme_jour() -> None:
    fec = exporter_fec((_ecriture("b", 1), _ecriture("a", 1, Journal.AN)))
    premiere = fec.split("\r\n")[1].split("\t")
    assert premiere[0] == "AN"


def test_enregistrements_crlf_et_zones_sans_separateur() -> None:
    fec = exporter_fec((_ecriture("e1", 1),))
    assert fec.endswith("\r\n")
    for ligne in fec.rstrip("\r\n").split("\r\n"):
        assert "\n" not in ligne and "\r" not in ligne
        assert len(ligne.split("\t")) == 18
    zones = fec.split("\r\n")[1].split("\t")
    assert zones[10] == "Libellé avec tabulation et retour"


def test_montant_sans_separateur_de_milliers() -> None:
    ligne = exporter_fec((_ecriture("e1", 1),)).split("\r\n")[1].split("\t")
    assert ligne[11] == "1234567,89"


def test_zones_obligatoires_toujours_renseignees() -> None:
    # CompteLib, PieceRef, PieceDate, EcritureLib, ValidDate : A.47 A-1.
    ligne = exporter_fec((_ecriture("e1", 1),)).split("\r\n")[1].split("\t")
    for indice in (0, 1, 2, 3, 4, 5, 8, 9, 10, 15):
        assert ligne[indice], COLONNES_FEC[indice]
    assert ligne[8] == "e1"  # PieceRef : l'identifiant interne à défaut de pièce


def test_libelle_compte_remonte_au_prefixe_connu() -> None:
    assert libelle_compte("6712") == "Pénalités, amendes fiscales et pénales"
    assert libelle_compte("401100") == "Fournisseurs et comptes rattachés"
    assert libelle_compte("8") == ""


def test_nom_de_fichier_normalise() -> None:
    assert nom_fichier_fec("987142031", date(2025, 12, 31)) == "987142031FEC20251231.txt"


def test_un_fec_exporte_passe_les_controles_a47() -> None:
    valider_fec(exporter_fec((_ecriture_uber(), _ecriture("e2", 4))))


def test_refuse_une_ecriture_desequilibree() -> None:
    fec = exporter_fec((_ecriture_uber(),))
    with pytest.raises(FecInvalide, match="déséquilibrée"):
        valider_fec(fec.replace("848,00", "1,00", 1))
