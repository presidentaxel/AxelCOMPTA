"""AXE-973 : la couverture bancaire d'une fiche, de toutes ses sources."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.couverture_bancaire_fiche import a_completer, couverture_de_la_fiche
from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.tenants.fiches_import import DocumentImport, document_import, nouvelle_fiche
from axelcompta.traitement_documents_import import traiter

LE = datetime(2026, 11, 18, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 18)
FICHE = replace(
    nouvelle_fiche("f", TenantId("T"), "Konate", "K", "908771033", "a", LE),
    champs={
        "date_creation": "2022-01-03",
        "cloture": "30/09",
        "premiere_cloture": "2022-09-30",
        "debut_historique": "2026-08-20",
    },
)
FEC = (
    b"JournalCode\tEcritureNum\tEcritureDate\tCompteNum\tCompteLib\tPieceRef\tEcritureLib"
    b"\tDebit\tCredit\tValidDate\r\n"
    b"BQ1\t1\t20220125\t5120010\tCompte Bancaire QONTO\tP\tCapital\t1000,00\t0,00\t20220125\r\n"
    b"BQ1\t1\t20220125\t1013100\tCapital\tP\tCapital\t0,00\t1000,00\t20220125\r\n"
    b"BQ1\t2\t20220301\t5120010\tCompte Bancaire QONTO\tP\tFrais\t0,00\t455,28\t20220301\r\n"
    b"BQ1\t2\t20220301\t6278000\tFrais\tP\tFrais\t455,28\t0,00\t20220301\r\n"
)
QIF = b"!Type:Bank\nD25/01/2022\nT1000.00\nPCapital\n^\nD01/03/2022\nT-455.28\nPFrais\n^\n"


def _document(id_: str, emplacement: str, nom: str, contenu: bytes) -> DocumentImport:
    document = document_import(id_, FICHE, emplacement, nom, "", contenu, "a", LE)
    lu = traiter(document.categorie, nom, contenu)
    return replace(document, donnees=lu.donnees)


def _ecriture(jour: date, centimes: int) -> Ecriture:
    sens = Sens.DEBIT if centimes > 0 else Sens.CREDIT
    autre = Sens.CREDIT if centimes > 0 else Sens.DEBIT
    return Ecriture(
        id=EcritureId(f"e-{jour}"),
        dossier_id=DossierId("DIGI_24951"),
        journal=Journal.BQ,
        date=jour,
        libelle="op",
        reference_piece=None,
        lignes=(
            LigneEcriture("5121", sens, Money(abs(centimes))),
            LigneEcriture("706", autre, Money(abs(centimes))),
        ),
    )


BRED = CompteBancaire(
    DossierId("DIGI_24951"),
    "67499359",
    "5121",
    "Kerfice Service - Bred",
    solde_banque_cts=870360,
    solde_releve_le=LE,
    retenu=True,
)
PERSO = replace(BRED, identifiant="perso", compte_comptable="5122", retenu=None)


def test_fec_qif_et_digifactory_disent_ce_qui_manque_et_ce_qui_est_prouve() -> None:
    documents = [
        _document("d1", "reprise:fec:2022", "90877103300010FEC20220930.csv", FEC),
        _document("d2", "banque:releve_bancaire", "qonto.qif", QIF),
    ]
    ecritures = [_ecriture(date(2026, 8, 20), 50000), _ecriture(date(2026, 10, 1), -20000)]
    comptes = couverture_de_la_fiche(
        FICHE,
        documents,
        [BRED, PERSO],
        ecritures,
        AUJOURD_HUI,
    )

    bred, qonto = comptes  # le compte de l'activité d'abord ; pas le compte perso
    assert (bred.cle, bred.suivi, qonto.cle) == ("digi:67499359", True, "fec:5120010")
    # Qonto : le QIF s'est rattaché seul au compte du FEC, le solde le prouve.
    assert [p.etat for p in qonto.couverture.periodes] == ["complet"]
    assert set(qonto.couverture.periodes[0].sources) == {"FEC 2022", "Relevé qonto.qif"}
    # Bred : rien entre la création et Digifactory ; depuis, des données.
    etats = [(p.etat, p.debut) for p in bred.couverture.periodes]
    assert etats[0] == ("manquant", date(2022, 1, 3))
    assert etats[-1][0] == "couvert" and etats[-1][1] == date(2026, 8, 20)
    # Seul ce qui touche l'exercice tenu est demandé : depuis le 01/10/2025.
    assert a_completer(bred) == [(date(2025, 10, 1), date(2026, 8, 19), "manquant")]
    assert a_completer(qonto) == []
