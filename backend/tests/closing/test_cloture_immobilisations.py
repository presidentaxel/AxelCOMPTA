"""AXE-802 : la clôture passe la dotation, et la 2033-C la reprend."""

from __future__ import annotations

from datetime import date

from axelcompta.closing.cloture_fiscale import cloturer_fiscalement, ecritures_de_cloture
from axelcompta.closing.controles_tdfc import controler_liasse
from axelcompta.closing.immobilisations import Immobilisation
from axelcompta.closing.models import ParametresCloture
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

D = DossierId("D1")
VEHICULE = Immobilisation("v1", "Toyota", "2182", date(2026, 4, 1), 30_000_00, 60, "achat")


def _ecriture(identifiant: str, jour: date, debit: str, credit: str, centimes: int) -> Ecriture:
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=D,
        journal=Journal.BQ,
        date=jour,
        libelle=identifiant,
        reference_piece=None,
        lignes=(
            LigneEcriture(debit, Sens.DEBIT, Money(centimes)),
            LigneEcriture(credit, Sens.CREDIT, Money(centimes)),
        ),
    )


ECRITURES = (
    _ecriture("apport", date(2026, 1, 2), "512", "101", 31_000_00),
    _ecriture("achat", date(2026, 4, 1), "2182", "512", 30_000_00),
    _ecriture("courses", date(2026, 6, 30), "512", "706", 20_000_00),
)
PARAMETRES = ParametresCloture(
    exercice_debut=date(2026, 1, 1),
    exercice_fin=date(2026, 12, 31),
    forme_juridique="SASU",
    soumis_is=True,
    immobilisations=(VEHICULE,),
)


def test_la_dotation_fait_partie_des_ecritures_de_cloture() -> None:
    ids = [e.id for e in ecritures_de_cloture(D, ECRITURES, PARAMETRES)]
    assert "D1:cloture-immo-2026-dotation-v1" in ids


def test_la_2033_c_reprend_le_bien_et_son_amortissement() -> None:
    liasse = cloturer_fiscalement(D, "2026", ECRITURES, PARAMETRES)
    cases = liasse.cases
    # Matériel de transport : augmentation 30 000, fin 30 000 ; amortissement 4 500.
    assert cases["2033C.462"] == 30_000_00 and cases["2033C.466"] == 30_000_00
    assert cases["2033C.552"] == 4_500_00 and cases["2033C.556"] == 4_500_00
    assert cases["2033B.254"] == 4_500_00
    controler_liasse(liasse)


def test_relancer_la_cloture_ne_compte_pas_la_dotation_deux_fois() -> None:
    premiere = ecritures_de_cloture(D, ECRITURES, PARAMETRES)
    avec_inventaire = ECRITURES + premiere
    assert ecritures_de_cloture(D, avec_inventaire, PARAMETRES) == premiere
