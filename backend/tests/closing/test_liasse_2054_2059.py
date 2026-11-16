"""AXE-484 : détail du 2054, affectation 2058-C et plus-values 2059-A,
codes du formulaire officiel 2050-LIASSE millésime 2026."""

from __future__ import annotations

from datetime import date

from axelcompta.closing.affectation import SituationAffectation, ecriture_affectation
from axelcompta.closing.immobilisations import Cession, Immobilisation
from axelcompta.closing.liasse_2033_annexes import Mouvements
from axelcompta.closing.liasse_2054 import immobilisations_2054
from axelcompta.closing.liasse_2058c import affectation_2058c, credit_bail_2058c
from axelcompta.closing.liasse_2059a import plus_values_2059a
from axelcompta.closing.loa import ContratLoa
from axelcompta.core.ids import DossierId

D = DossierId("DIGI_1")


def test_le_2054_ventile_vehicule_et_informatique_et_garde_le_total() -> None:
    """Un véhicule au bilan d'ouverture (30 000 €), un ordinateur acheté
    (1 200 €), un vieux véhicule sorti (8 000 €)."""
    m = Mouvements(
        ouverture={"2182": 38_000_00},
        debits={"2183": 1_200_00},
        credits={"2182": 8_000_00},
    )
    cases = immobilisations_2054(m)
    # Matériel de transport : début, acquisitions, cessions, fin, origine.
    assert (cases["KY"], cases["LA"], cases["MP"], cases["MQ"], cases["MR"]) == (
        38_000,
        0,
        8_000,
        30_000,
        30_000,
    )
    assert (cases["LB"], cases["LD"], cases["MT"]) == (0, 1_200, 1_200)
    # Total des corporelles (III) et total général.
    assert (cases["LN"], cases["LP"], cases["NG"], cases["NH"]) == (38_000, 1_200, 8_000, 31_200)
    assert (cases["0G"], cases["0J"], cases["0K"], cases["0L"]) == (38_000, 1_200, 8_000, 31_200)
    assert cases["NH"] == cases["0L"]
    # Pas de réévaluation ni de virement de poste à poste.
    assert cases["KZ"] == cases["IV"] == cases["0H"] == cases["I4"] == 0


def test_le_2054_sans_immobilisation_est_neant() -> None:
    assert immobilisations_2054(Mouvements({}, {}, {})) == {}


def _affectation(resultat: int, dividendes: int) -> SituationAffectation:
    return SituationAffectation(
        resultat=resultat,
        capital=1_000_00,
        reserve_legale=0,
        report_a_nouveau=500_00,
        tresorerie=50_000_00,
        dettes=0,
        charges_mensuelles=0,
        gerant_non_salarie=False,
        annee_versement=2026,
    )


def test_le_2058c_reprend_l_affectation_du_resultat_precedent() -> None:
    """Bénéfice 2025 de 10 000 €, 500 € de report à nouveau : 100 € de
    réserve légale (5 % du bénéfice, plafonnée à 10 % du capital de
    1 000 €), 4 000 € de dividendes."""
    situation = _affectation(10_000_00, 4_000_00)
    ecriture = ecriture_affectation(D, 2025, date(2026, 6, 30), situation, 4_000_00)
    m = Mouvements(ouverture={"110": -500_00, "120": -10_000_00}, debits={}, credits={})
    cases = affectation_2058c([ecriture], m)
    assert (cases["0C"], cases["0D"], cases["0E"]) == (500, 10_000, 0)
    assert (cases["ZB"], cases["ZE"], cases["ZF"]) == (100, 4_000, 0)
    assert cases["ZG"] == 500 + 10_000 - 100 - 4_000
    assert cases["0F"] == cases["ZH"] == 10_500


def test_le_2058c_d_une_perte() -> None:
    situation = _affectation(-3_000_00, 0)
    ecriture = ecriture_affectation(D, 2025, date(2026, 6, 30), situation, 0)
    m = Mouvements(ouverture={"110": -500_00}, debits={}, credits={})
    cases = affectation_2058c([ecriture], m)
    assert (cases["0D"], cases["ZG"], cases["ZH"]) == (-3_000, -2_500, -2_500)


def test_sans_affectation_le_2058c_reste_vide() -> None:
    assert affectation_2058c([], Mouvements({}, {}, {})) == {}


def test_le_2058c_reprend_l_engagement_de_loa_mais_pas_le_prix_de_revient() -> None:
    contrat = ContratLoa("l1", "Leaser", "Toyota", date(2026, 1, 1), 36, 400_00, 2_000_00, 9_000_00)
    cases = credit_bail_2058c([contrat], date(2026, 12, 31))
    assert set(cases) == {"YQ"} and cases["YQ"] > 9_000


VEHICULE = Immobilisation("v1", "Toyota", "2182", date(2023, 1, 1), 30_000_00, 60)


def test_le_2059a_d_une_societe_a_l_is_est_a_court_terme() -> None:
    """Acquis 30 000 € le 01/01/2023, amorti sur 5 ans, vendu 15 000 € le
    31/12/2026 : 24 000 € amortis, valeur résiduelle 6 000 €, plus-value
    9 000 €, toute à court terme à l'IS."""
    cede = _vehicule_cede(15_000_00)
    cases = plus_values_2059a([cede], date(2026, 1, 1), date(2026, 12, 31), soumis_is=True)
    assert (cases["L1.C2"], cases["L1.C4"], cases["L1.C6"], cases["L1.C7"]) == (
        30_000,
        24_000,
        6_000,
        15_000,
    )
    assert (cases["L1.C8"], cases["L1.C9"], cases["L1.C10"]) == (9_000, 9_000, 0)
    assert cases["TOTAL.C8"] == 9_000


def test_le_2059a_a_l_ir_partage_court_et_long_terme() -> None:
    """Même vente à l'IR, bien détenu plus de deux ans : la plus-value est à
    court terme à hauteur des amortissements, sans excédent ici ; vendu
    32 000 €, 24 000 € à court terme et 2 000 € à long terme."""
    cede = _vehicule_cede(32_000_00)
    cases = plus_values_2059a([cede], date(2026, 1, 1), date(2026, 12, 31), soumis_is=False)
    assert (cases["L1.C8"], cases["L1.C9"], cases["L1.C10"]) == (26_000, 24_000, 2_000)


def test_le_2059a_detenu_moins_de_deux_ans_est_a_court_terme() -> None:
    cede = Immobilisation(
        "v2",
        "Dacia",
        "2182",
        date(2026, 1, 1),
        20_000_00,
        60,
        cession=Cession(date(2026, 12, 31), 25_000_00),
    )
    cases = plus_values_2059a([cede], date(2026, 1, 1), date(2026, 12, 31), soumis_is=False)
    assert cases["L1.C10"] == 0 and cases["L1.C9"] == cases["L1.C8"]


def test_le_2059a_sans_cession_est_vide() -> None:
    assert plus_values_2059a([VEHICULE], date(2026, 1, 1), date(2026, 12, 31), True) == {}


def _vehicule_cede(prix: int) -> Immobilisation:
    return Immobilisation(
        "v1",
        "Toyota",
        "2182",
        date(2023, 1, 1),
        30_000_00,
        60,
        cession=Cession(date(2026, 12, 31), prix),
    )
