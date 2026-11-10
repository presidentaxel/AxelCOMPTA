"""AXE-804 : le FEC de l'outil précédent devient un bilan d'ouverture, et un
faux FEC est refusé avec une raison claire."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.closing.ouverture import id_a_nouveaux
from axelcompta.closing.ouverture_fec import FecRefuse, analyser, lire_fec_externe, lire_nom
from axelcompta.core.ids import DossierId
from axelcompta.ledger.models import Journal, Sens
from tests.closing.fec_externe import ECRITURES, NOM, SIREN, fec

DOSSIER = DossierId("D1")
OUVERTURE = date(2026, 1, 1)
AUJOURD_HUI = date(2026, 11, 10)


def _analyse(contenu: str | bytes, nom: str = NOM, siren: str | None = SIREN, **kw: object):  # type: ignore[no-untyped-def]
    brut = contenu.encode() if isinstance(contenu, str) else contenu
    correspondance = kw.get("correspondance", {})
    return analyser(brut, nom, DOSSIER, siren, OUVERTURE, correspondance, AUJOURD_HUI)  # type: ignore[arg-type]


def _soldes(analyse) -> dict[str, int]:  # type: ignore[no-untyped-def]
    assert analyse.a_nouveaux is not None
    return {
        lg.compte: lg.montant.centimes * (1 if lg.sens is Sens.DEBIT else -1)
        for lg in analyse.a_nouveaux.lignes
    }


def test_un_fec_juste_donne_l_a_nouveaux_au_premier_jour() -> None:
    analyse = _analyse(fec())
    assert analyse.refus == ()
    an = analyse.a_nouveaux
    assert an is not None
    assert (an.id, an.journal, an.date) == (id_a_nouveaux(DOSSIER, 2026), Journal.AN, OUVERTURE)
    assert _soldes(analyse) == {
        "10100000": -100000,
        "16400000": -800000,
        "44571000": -500000,
        "51200000": 4400000,
        "120": -3000000,  # bénéfice 50 000 - 20 000
    }
    assert (analyse.resultat, analyse.solde_banque, analyse.capital) == (3000000, 4400000, 100000)
    assert any("Solde de banque au 31/12/2025 : 44 000,00 €" in a for a in analyse.alertes)
    assert "clos le 31/12/2025" in analyse.attestation


def test_variantes_reelles_barre_verticale_lf_windows_1252() -> None:
    texte = fec(separateur="|", fin="\n").replace("Libellé", "Libellé é")
    assert _analyse(texte.encode("cp1252")).refus == ()


def test_variante_montant_et_sens() -> None:
    lignes = lire_fec_externe(
        b"JournalCode\tEcritureNum\tEcritureDate\tCompteNum\tPieceRef\tEcritureLib\tMontant\tSens\tValidDate\r\n"
        b"OD\t1\t20250102\t512\tP\tL\t10.5\tD\t20250102\r\n"
        b"OD\t1\t20250102\t101\tP\tL\t10,50\tC\t20250102\r\n"
    )
    assert [(lg.debit, lg.credit) for lg in lignes] == [(1050, 0), (0, 1050)]


@pytest.mark.parametrize(
    "nom",
    [
        "fec.txt",
        "987142031_FEC_20251231.txt",
        "98714203FEC20251231.txt",
        "987142031FEC20251331.txt",
    ],
)
def test_un_fichier_renomme_n_est_plus_un_fec(nom: str) -> None:
    with pytest.raises(FecRefuse):
        lire_nom(nom)


def test_le_fec_d_une_autre_societe_est_refuse() -> None:
    analyse = _analyse(fec(), siren="123456782")
    assert analyse.a_nouveaux is None
    assert any("SIREN 987142031, pas de cette société" in r for r in analyse.refus)


def test_un_fec_qui_n_est_pas_celui_de_la_veille_est_refuse() -> None:
    analyse = _analyse(fec(), nom=f"{SIREN}FEC20241231.txt")
    assert any("la veille de l'ouverture" in r for r in analyse.refus)


def test_un_fec_desequilibre_est_refuse() -> None:
    faux = [*ECRITURES[:-1], ("AC", "AC0001", "20250915", "51200000", "0,00", "19000,00")]
    analyse = _analyse(fec(faux))
    assert analyse.a_nouveaux is None
    assert any("déséquilibrée" in r and "AC AC0001" in r for r in analyse.refus)


def test_un_compte_inconnu_demande_sa_correspondance() -> None:
    lignes = [lg if lg[3] != "60610000" else (*lg[:3], "CARBU", *lg[4:]) for lg in ECRITURES]
    refuse = _analyse(fec(lignes))
    assert refuse.comptes_inconnus == ("CARBU",)
    assert any("Comptes à faire correspondre" in r for r in refuse.refus)
    accepte = _analyse(fec(lignes), correspondance={"CARBU": "6061"})
    assert accepte.refus == ()
    with pytest.raises(FecRefuse):
        _analyse(fec(lignes), correspondance={"CARBU": "ABC"})


def test_dates_impossibles_refusees() -> None:
    apres = [
        *ECRITURES,
        ("OD", "OD9", "20260105", "51200000", "1,00", "0,00"),
        ("OD", "OD9", "20260105", "10100000", "0,00", "1,00"),
    ]
    assert any("après la clôture" in r for r in _analyse(fec(apres)).refus)
    assert any("date future" in r for r in _analyse(fec(valid="20271231")).refus)
    assert any("validées avant leur date" in a for a in _analyse(fec(valid="20250101")).alertes)


def test_une_ligne_au_debit_et_au_credit_est_refusee() -> None:
    faux = [("OD", "1", "20250102", "51200000", "1,00", "1,00")]
    with pytest.raises(FecRefuse, match="débit et au crédit"):
        _analyse(fec(faux))


def test_en_tete_incomplet_ou_fichier_vide() -> None:
    with pytest.raises(FecRefuse, match="En-tête FEC incomplet"):
        _analyse("JournalCode\tDebit\r\n")
    with pytest.raises(FecRefuse, match="vide"):
        _analyse("")


def test_sans_capital_ni_banque_des_alertes() -> None:
    lignes = [
        ("AC", "1", "20250915", "60610000", "10,00", "0,00"),
        ("AC", "1", "20250915", "40100000", "0,00", "10,00"),
    ]
    alertes = _analyse(fec(lignes)).alertes
    assert any("Aucun capital" in a for a in alertes)
    assert any("Aucun compte de banque" in a for a in alertes)
