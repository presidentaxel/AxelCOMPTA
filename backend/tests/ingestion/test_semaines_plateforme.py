"""AXE-924 : rapprocher les revenus d'une plateforme semaine par semaine.

Les semaines « réelles » reprennent les montants vérifiés au centime sur la
prod le 14/11 (B'CARS SERVICES et MK DRIVING), sans aucun nom."""

from __future__ import annotations

from datetime import date

from axelcompta.ingestion.ecritures_semaines import compte_creance
from axelcompta.ingestion.semaines_plateforme import (
    Jour,
    Virement,
    libelle_ecart,
    lundi,
    plateforme_du_libelle,
    rapprocher_plateforme,
    virement,
)
from axelcompta.packs.vtc_demo import charger_plateformes, plateforme_de

AUJOURD_HUI = date(2026, 11, 20)


def _jours(debut: date, montants: list[int]) -> list[Jour]:
    return [
        Jour(f"j-{debut.isoformat()}-{i}", "uber", date.fromordinal(debut.toordinal() + i), m)
        for i, m in enumerate(montants)
    ]


def _v(ident: str, le: date, montant: int, libelle: str) -> Virement:
    lu = virement(ident, le, montant, libelle)
    assert lu is not None
    return lu


POP = "POP SVCS, DOB , {} - {}"
INSTANT = "Transfer from STICHTING CUSTODIAN UBER PAYMENTS"


def test_les_libelles_de_plateforme_sont_reconnus() -> None:
    assert plateforme_du_libelle("POP SVCS, DOB , 20261102 - 20261108") == "uber"
    assert plateforme_du_libelle("Stichting Custodian Uber Payments") == "uber"
    assert plateforme_du_libelle("DOC/pid-1388547153/TXT/BOLT FR") == "bolt"
    assert plateforme_du_libelle("TOTAL ENERGIES") is None


def test_chaque_virement_paie_la_bonne_semaine() -> None:
    pop = _v("p", date(2026, 11, 9), 1, POP.format("20261102", "20261108"))
    assert (pop.nature, pop.semaine) == ("hebdomadaire", date(2026, 11, 2))
    sans_periode = _v("p2", date(2026, 11, 9), 1, "POP SVCS")
    assert sans_periode.semaine == date(2026, 11, 2)  # la semaine d'avant
    bolt = _v("b", date(2026, 11, 9), 1, "DOC/pid-1/TXT/BOLT FR")
    assert (bolt.nature, bolt.semaine) == ("hebdomadaire", date(2026, 11, 2))
    instant = _v("i", date(2026, 11, 5), 1, INSTANT)
    assert (instant.nature, instant.semaine) == ("instantane", date(2026, 11, 2))


def test_une_semaine_payee_par_pop_svcs_seul_est_soldee_sans_frais() -> None:
    """B'CARS, 02 → 08/11 : 5 jours = 868,03 € = POP SVCS du 09/11."""
    jours = [
        Jour("a", "uber", date(2026, 11, 2), 7832),
        Jour("b", "uber", date(2026, 11, 3), 7863),
        Jour("c", "uber", date(2026, 11, 5), 15145),
        Jour("d", "uber", date(2026, 11, 7), 13498),
        Jour("e", "uber", date(2026, 11, 8), 42465),
    ]
    pop = _v("pop", date(2026, 11, 9), 86803, POP.format("20261102", "20261108"))
    (semaine,) = rapprocher_plateforme("uber", jours, [pop], AUJOURD_HUI)
    assert (semaine.etat, semaine.du_cts, semaine.frais_cts) == ("solde", 86803, 0)
    assert semaine.virements == ("pop",)


def test_un_retrait_instantane_coute_99_centimes() -> None:
    """B'CARS, 26/10 → 01/11 : 696,40 € = instantané 323,32 + POP 372,09 + 0,99."""
    jours = _jours(date(2026, 10, 26), [17088, 10325, 4818, 5457, 12974, 18978])
    virements = [
        _v("inst", date(2026, 10, 29), 32332, INSTANT),
        _v("pop", date(2026, 11, 2), 37209, POP.format("20261026", "20261101")),
    ]
    (semaine,) = rapprocher_plateforme("uber", jours, virements, AUJOURD_HUI)
    assert (semaine.etat, semaine.frais_cts, semaine.ecart_cts) == ("solde", 99, 0)


def test_cinq_retraits_instantanes_et_un_pop_svcs() -> None:
    """MK DRIVING, 02 → 08/11 : 915,48 € = 5 instantanés + POP 158,08 + 5 × 0,99."""
    jours = _jours(date(2026, 11, 2), [25090, 14133, 9967, 10925, 3062, 12563, 15808])
    virements = [
        _v("i1", date(2026, 11, 2), 17044, INSTANT),
        _v("i2", date(2026, 11, 3), 14469, INSTANT),
        _v("i3", date(2026, 11, 5), 23041, INSTANT),
        _v("i4", date(2026, 11, 6), 8227, INSTANT),
        _v("i5", date(2026, 11, 7), 12464, INSTANT),
        _v("pop", date(2026, 11, 9), 15808, POP.format("20261102", "20261108")),
    ]
    (semaine,) = rapprocher_plateforme("uber", jours, virements, AUJOURD_HUI)
    assert (semaine.etat, semaine.frais_cts) == ("solde", 495)


def test_un_retrait_sans_frais_est_aussi_solde() -> None:
    """Les 0,99 € ne sont pas toujours prélevés."""
    jours = _jours(date(2026, 11, 2), [10000])
    virements = [_v("i1", date(2026, 11, 2), 10000, INSTANT)]
    (semaine,) = rapprocher_plateforme("uber", jours, virements, AUJOURD_HUI)
    assert (semaine.etat, semaine.frais_cts) == ("solde", 0)


def test_un_retrait_qui_emporte_le_reste_de_la_semaine_d_avant() -> None:
    """Semaine 1 : 100 € gagnés, 50 € retirés. Semaine 2 : 100 € gagnés, un
    retrait de 149,01 € emporte tout. Seules, aucune ne tombe juste ;
    ensemble, l'écart est de 2 × 0,99 €."""
    jours = _jours(date(2026, 10, 26), [10000]) + _jours(date(2026, 11, 2), [10000])
    virements = [
        _v("i1", date(2026, 10, 27), 4901, INSTANT),
        _v("i2", date(2026, 11, 3), 14901, INSTANT),
    ]
    semaines = rapprocher_plateforme("uber", jours, virements, AUJOURD_HUI)
    assert [(s.lundi, s.etat, s.frais_cts) for s in semaines] == [
        (date(2026, 10, 26), "solde", 0),
        (date(2026, 11, 2), "solde", 198),
    ]


def test_le_pop_svcs_pas_encore_recu_laisse_la_semaine_en_attente() -> None:
    jours = _jours(date(2026, 11, 9), [5000, 6000])
    (semaine,) = rapprocher_plateforme("uber", jours, [], date(2026, 11, 17))
    assert (semaine.etat, semaine.ecart_cts) == ("en_attente", 11000)


def test_un_ecart_inexplique_est_a_verifier_sans_bloquer_les_suivantes() -> None:
    jours = _jours(date(2026, 10, 19), [10000]) + _jours(date(2026, 10, 26), [7000])
    virements = [
        _v("pop1", date(2026, 10, 26), 9000, POP.format("20261019", "20261025")),
        _v("pop2", date(2026, 11, 2), 7000, POP.format("20261026", "20261101")),
    ]
    vieille, suivante = rapprocher_plateforme("uber", jours, virements, AUJOURD_HUI)
    assert (vieille.etat, vieille.ecart_cts) == ("a_verifier", 1000)
    assert libelle_ecart(vieille) == "10,00 € encore dus par Uber"
    assert suivante.etat == "solde"


def test_une_semaine_pas_finie_n_est_pas_tranchee() -> None:
    jours = _jours(lundi(date(2026, 11, 18)), [5000])
    assert rapprocher_plateforme("uber", jours, [], date(2026, 11, 18)) == []


def test_des_frais_au_dela_du_nombre_de_retraits_ne_sont_pas_inventes() -> None:
    """Un seul retrait instantané : 2 × 0,99 € d'écart n'est pas expliqué."""
    jours = _jours(date(2026, 10, 26), [10000])
    virements = [_v("i1", date(2026, 10, 27), 9802, INSTANT)]
    (semaine,) = rapprocher_plateforme("uber", jours, virements, AUJOURD_HUI)
    assert (semaine.etat, semaine.ecart_cts) == ("a_verifier", 198)


def test_free_now_heetch_et_allocab_sont_reconnus_en_banque() -> None:
    """AXE-933 : Free Now paie la période écrite dans son libellé."""
    assert plateforme_du_libelle("TRANSCOVO SAS FREENOW CREDIT") == "freenow"
    assert plateforme_du_libelle("VIR HEETCH SAS") == "heetch"
    assert plateforme_du_libelle("VIREMENT ALLOCAB") == "allocab"
    lu = virement("f1", date(2026, 10, 7), 56596, "Freenow Credit 700-1 01.10.-04.10.2026")
    assert lu is not None
    assert (lu.plateforme, lu.nature, lu.semaine) == ("freenow", "hebdomadaire", date(2026, 9, 28))
    sans_periode = virement("f2", date(2026, 10, 7), 1000, "TRANSCOVO SAS FREENOW CREDIT")
    assert sans_periode is not None and sans_periode.semaine == date(2026, 9, 28)
    passe_l_an = virement("f3", date(2027, 1, 5), 1000, "Freenow Credit 700-1 28.12.-03.01.2027")
    assert passe_l_an is not None and passe_l_an.semaine == date(2026, 12, 28)


def test_les_plateformes_du_pack() -> None:
    """AXE-933 : un compte Rollee Heetch, Allocab ou Free Now n'est plus mis
    en quarantaine, et chaque plateforme a sa créance."""
    plateformes = charger_plateformes()
    noms = {
        nom: getattr(plateforme_de(nom, plateformes), "nom", None)
        for nom in ("heetch-fleet-rev", "allocab-fleet-rev", "free-now.com-rev", "uber.com-rev")
    }
    assert noms == {
        "heetch-fleet-rev": "heetch",
        "allocab-fleet-rev": "allocab",
        "free-now.com-rev": "freenow",
        "uber.com-rev": "uber",
    }
    assert [compte_creance(n) for n in ("heetch", "allocab", "freenow")] == ["4673", "4674", "4675"]
