"""AXE-934 : dire ce qui manque pour rapprocher Rollee et la banque."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from axelcompta.core.ids import DossierId
from axelcompta.explication_semaines import MOTIF_SANS_BANQUE, JourVu, SemaineVue
from axelcompta.ingestion.comptes_rollee import CompteRelie
from axelcompta.manques_rollee import euros, manques
from axelcompta.packs.vtc_demo import charger_plateformes

D = DossierId("D1")
LE = datetime(2026, 11, 15, tzinfo=UTC)
PLATEFORMES = charger_plateformes()
UBER = CompteRelie("acc-u", D, "uber.com-rev", True, False, LE, LE)
JOUR = JourVu(date(2026, 10, 5), 100_00, 0, 100_00, 0, 100_00)


def _semaine(
    plateforme: str = "uber",
    etat: str = "a_verifier",
    du: int = 100_00,
    paye: int = 0,
    motif: str | None = None,
    jours: bool = True,
) -> SemaineVue:
    lundi = date(2026, 10, 5)
    return SemaineVue(
        plateforme,
        lundi,
        lundi + timedelta(days=6),
        etat,
        du,
        paye,
        0,
        du - paye,
        motif,
        (JOUR,) if jours else (),
        (),
    )


def test_euros() -> None:
    assert (euros(123456), euros(-200)) == ("1 234,56 €", "−2,00 €")


def test_sans_compte_rollee() -> None:
    assert manques([], [], PLATEFORMES, None) == [
        "Aucun compte Rollee n'est relié à cette entreprise : rien à rapprocher."
    ]


def test_comptes_a_reconnecter_et_plateforme_inconnue() -> None:
    eteint = replace(UBER, connecte=False)
    inconnus = [replace(UBER, account_id=f"acc-{k}", nom="lecab-rev") for k in range(3)]
    autre = replace(UBER, account_id="acc-y", titulaire_autre=True, connecte=False)
    assert manques([], [eteint, *inconnus, autre], PLATEFORMES, None) == [
        "lecab-rev (3 comptes) : plateforme pas encore prise en charge, "
        "ses jours Rollee sont mis de côté.",
        "uber.com-rev : compte Rollee à reconnecter, ses revenus ne sont plus lus.",
    ]


def test_sans_banque_tout_est_dit() -> None:
    vues = [_semaine(etat="en_attente", motif=MOTIF_SANS_BANQUE)]
    (phrase,) = manques(vues, [UBER], PLATEFORMES, None)
    assert phrase.startswith("Aucun relevé bancaire : 1 semaine(s) Rollee (100,00 € dus)")


def test_une_banque_qui_commence_apres_rollee() -> None:
    vues = [_semaine(etat="en_attente", motif=MOTIF_SANS_BANQUE)]
    (phrase,) = manques(vues, [UBER], PLATEFORMES, date(2026, 11, 2))
    assert phrase.startswith("La banque commence le 02/11/2026 : les 1 semaine(s)")


def test_plateforme_payee_sans_jour_ou_gagnee_sans_virement() -> None:
    vues = [
        _semaine("bolt", du=0, paye=57_31, jours=False),
        _semaine("uber", du=1089_34),
        _semaine("uber", du=962_42, paye=957_49),
        _semaine("uber", etat="en_attente"),  # virement encore attendu : pas un manque
    ]
    assert manques(vues, [UBER], PLATEFORMES, date(2026, 6, 1)) == [
        "Bolt : 1 semaine(s) payée(s) en banque (57,31 €) sans aucun jour Rollee. "
        "Reliez Bolt dans Rollee.",
        "Uber : aucun virement trouvé en banque pour 1 semaine(s) (1 089,34 € dus). "
        "Le compte bancaire qui reçoit Uber manque peut-être.",
        "Uber : 1 semaine(s) à vérifier, écart total 4,93 €.",
    ]


def test_tout_est_rapproche() -> None:
    vues = [_semaine(etat="solde", paye=100_00)]
    assert manques(vues, [UBER], PLATEFORMES, date(2026, 6, 1)) == []


def test_une_plateforme_reliee_sans_jour_est_a_signaler_a_rollee() -> None:
    """DIGI_4952 : comptes Uber de flotte reliés et connectés, aucun jour."""
    vues = [_semaine("uber", du=0, paye=500_00, jours=False)]
    (phrase,) = manques(vues, [UBER], PLATEFORMES, date(2026, 6, 1))
    assert phrase.endswith("Rollee ne remonte aucun jour pour ces semaines : à signaler à Rollee.")


def test_une_plateforme_deconnectee_est_a_reconnecter() -> None:
    vues = [_semaine("uber", du=0, paye=500_00, jours=False)]
    eteint = replace(UBER, connecte=False)
    phrases = manques(vues, [eteint], PLATEFORMES, date(2026, 6, 1))
    assert phrases[-1].endswith("Reconnectez Uber dans Rollee.")
