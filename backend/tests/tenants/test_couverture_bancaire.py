"""AXE-973 : une banque est complète quand le solde le prouve."""

from __future__ import annotations

from datetime import date, timedelta

from axelcompta.tenants.couverture_bancaire import (
    Solde,
    SourceOperations,
    correspondance,
    couverture,
    phrase,
)

DEBUT, FIN = date(2022, 1, 3), date(2022, 9, 30)
# Une opération de 10 € tous les 3 jours, à partir du 25/01.
OPS = tuple((date(2022, 1, 25) + timedelta(days=3 * i), 1000) for i in range(80))
TOTAL = sum(m for j, m in OPS if j <= FIN)
SOLDES = [Solde("q", date(2022, 1, 2), 0, "création"), Solde("q", FIN, TOTAL, "FEC 2022")]


def _etats(sources: list[SourceOperations], fin: date = FIN) -> list[tuple[str, date, date]]:
    return [(p.etat, p.debut, p.fin) for p in couverture("q", sources, SOLDES, DEBUT, fin).periodes]


def test_le_solde_qui_tombe_juste_prouve_aussi_les_jours_sans_donnees() -> None:
    releve = SourceOperations("q", "QIF", date(2022, 1, 25), FIN, OPS)
    assert _etats([releve]) == [("complet", DEBUT, FIN)]


def test_apres_le_dernier_solde_les_donnees_ne_sont_pas_prouvees() -> None:
    releve = SourceOperations("q", "QIF", DEBUT, date(2022, 10, 5), OPS)
    fin = date(2022, 12, 31)
    assert _etats([releve], fin) == [
        ("complet", DEBUT, FIN),
        ("couvert", date(2022, 10, 1), date(2022, 10, 5)),
        ("manquant", date(2022, 10, 6), fin),
    ]


def test_une_operation_perdue_donne_un_ecart_chiffre() -> None:
    perdue = OPS[30]
    releve = SourceOperations("q", "QIF", DEBUT, FIN, tuple(o for o in OPS if o != perdue))
    (periode,) = couverture("q", [releve], SOLDES, DEBUT, FIN).periodes
    assert (periode.etat, periode.ecart_cts) == ("ecart", 1000)
    assert phrase(periode).startswith("Écart de 10,00 € du 03/01/2022 au 30/09/2022")


def test_des_jours_sans_donnees_avant_un_ecart_sont_un_trou() -> None:
    """Rien ne dit qu'un compte n'était pas encore ouvert : sans source, les
    jours d'avant la première donnée portent l'écart."""
    releve = SourceOperations("q", "QIF", date(2022, 6, 1), FIN, OPS[40:])
    trou, apres = couverture("q", [releve], SOLDES, DEBUT, FIN).periodes
    assert (trou.etat, trou.debut, trou.fin) == ("manquant", DEBUT, date(2022, 5, 31))
    assert trou.ecart_cts == sum(m for _, m in OPS[:40])
    assert apres.etat == "couvert"


def test_un_mois_sans_releve_porte_l_ecart() -> None:
    avant_juin = tuple(o for o in OPS if o[0] < date(2022, 6, 1))
    apres_juin = tuple(o for o in OPS if o[0] >= date(2022, 7, 1))
    juin = sum(m for j, m in OPS if j.month == 6)
    sources = [
        SourceOperations("q", "A", DEBUT, date(2022, 5, 31), avant_juin),
        SourceOperations("q", "B", date(2022, 7, 1), FIN, apres_juin),
    ]
    periodes = couverture("q", sources, SOLDES, DEBUT, FIN).periodes
    assert [p.etat for p in periodes] == ["couvert", "manquant", "couvert"]
    manquant = periodes[1]
    assert (manquant.debut, manquant.fin, manquant.ecart_cts) == (
        date(2022, 6, 1),
        date(2022, 6, 30),
        juin,
    )


def test_un_releve_qui_couvre_un_mois_vide_donne_un_indice() -> None:
    sans_juin = tuple(o for o in OPS if o[0].month != 6)
    releve = SourceOperations("q", "QIF", DEBUT, FIN, sans_juin)
    (periode,) = couverture("q", [releve], SOLDES, DEBUT, FIN).periodes
    assert periode.etat == "ecart"
    assert any("06/2022" in i for i in periode.indices)


def test_deux_sources_qui_se_recouvrent_ne_comptent_qu_une_fois() -> None:
    fec = SourceOperations("q", "FEC 2022", DEBUT, FIN, OPS)
    qif = SourceOperations("q", "QIF", date(2022, 1, 25), FIN, OPS)
    assert _etats([fec, qif]) == [("complet", DEBUT, FIN)]


def test_deux_soldes_differents_le_meme_jour_sont_signales() -> None:
    soldes = [*SOLDES, Solde("q", FIN, TOTAL + 1, "relevé")]
    releve = SourceOperations("q", "QIF", DEBUT, FIN, OPS)
    (incoherence,) = couverture("q", [releve], soldes, DEBUT, FIN).incoherences
    assert incoherence.startswith("Le 30/09/2022 : FEC 2022 dit")


def test_un_qif_se_reconnait_a_ses_operations() -> None:
    assert correspondance(OPS[:10], OPS) == 1.0
    assert correspondance(((DEBUT, 5),), OPS) == 0.0
