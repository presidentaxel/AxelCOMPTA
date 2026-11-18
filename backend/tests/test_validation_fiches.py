"""AXE-989 : un chauffeur importé a des données complètes pour l'exercice à
déclarer, et à jour (Digifactory, Rollee) pour l'exercice en cours."""

from __future__ import annotations

from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId
from axelcompta.couverture_bancaire_fiche import CompteCouvert
from axelcompta.couverture_plateformes import MoisPlateforme, PlateformeCouverte
from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.tenants.couverture_bancaire import Couverture, Periode
from axelcompta.tenants.fiches_import_etat import Exercice
from axelcompta.validation_fiches import (
    Validation,
    plateformes_declarees,
    valider_banque,
    valider_plateformes,
)

D = DossierId("DIGI_24951")
AUJOURD_HUI = date(2026, 11, 18)
CLOS = Exercice(date(2025, 10, 1), date(2026, 9, 30), "a_declarer", date(2027, 1, 15))
EN_COURS = Exercice(date(2026, 10, 1), date(2027, 9, 30), "en_cours", None)
EXERCICES = [CLOS, EN_COURS]


def _bred(releve_le: datetime | None = datetime(2026, 11, 18, 4, tzinfo=UTC)) -> CompteBancaire:
    return CompteBancaire(D, "67499359", "5121", "Bred", 100_000, releve_le, retenu=True)


def _couvert(*periodes: tuple[date, date, str]) -> CompteCouvert:
    couverture = Couverture(
        "digi:67499359",
        tuple(Periode(d, f, e) for d, f, e in periodes),  # type: ignore[arg-type]
    )
    return CompteCouvert("digi:67499359", "Bred", "digifactory", True, couverture)


TOUT_PROUVE = _couvert((date(2025, 10, 1), AUJOURD_HUI, "complet"))


def _echecs(criteres: list) -> list[str]:  # type: ignore[type-arg]
    return [c.libelle for c in criteres if not c.ok]


def test_une_banque_prouvee_et_a_jour_est_validee() -> None:
    assert _echecs(valider_banque(EXERCICES, [_bred()], [TOUT_PROUVE], AUJOURD_HUI)) == []


def test_sans_digifactory_des_releves_ne_suffisent_pas_pour_l_exercice_en_cours() -> None:
    releves = CompteCouvert("doc:qif", "Relevé", "releve", False, TOUT_PROUVE.couverture)
    echecs = _echecs(valider_banque(EXERCICES, [], [releves], AUJOURD_HUI))
    assert echecs == ["Digifactory relié"]


def test_un_digifactory_qui_ne_releve_plus_n_est_pas_a_jour() -> None:
    criteres = valider_banque(
        EXERCICES, [_bred(datetime(2026, 11, 1, tzinfo=UTC))], [TOUT_PROUVE], AUJOURD_HUI
    )
    (echec,) = [c for c in criteres if not c.ok]
    assert (echec.libelle, echec.detail) == (
        "Bred à jour sur Digifactory",
        "Dernier relevé Digifactory le 01/11/2026.",
    )


def test_un_trou_dans_l_exercice_a_declarer_bloque_meme_avec_digifactory() -> None:
    trou = _couvert(
        (date(2025, 10, 1), date(2026, 8, 19), "manquant"),
        (date(2026, 8, 20), AUJOURD_HUI, "complet"),
    )
    criteres = valider_banque(EXERCICES, [_bred()], [trou], AUJOURD_HUI)
    (echec,) = [c for c in criteres if not c.ok]
    assert echec.libelle == "Exercice clos le 30/09/2026 : Bred complet"
    assert echec.detail == "Il manque les relevés du 01/10/2025 au 19/08/2026."


def _uber(*etats: tuple[str, str]) -> PlateformeCouverte:
    return PlateformeCouverte("uber", tuple(MoisPlateforme(m, e) for m, e in etats))  # type: ignore[arg-type]


def test_des_documents_couvrent_l_exercice_clos_mais_rollee_doit_etre_a_jour() -> None:
    uber = _uber(("2025-10", "document"), ("2026-09", "document"), ("2026-11", "rollee"))
    jours = [("uber", date(2026, 11, 15))]
    assert _echecs(valider_plateformes(EXERCICES, [uber], jours, {"uber"}, AUJOURD_HUI)) == []
    vieux = [("uber", date(2026, 10, 2))]
    echecs = _echecs(valider_plateformes(EXERCICES, [uber], vieux, {"uber"}, AUJOURD_HUI))
    assert echecs == ["Uber à jour sur Rollee"]


def test_un_mois_a_completer_bloque_l_exercice_clos() -> None:
    uber = _uber(("2026-03", "a_completer"), ("2026-04", "inconnu"), ("2026-11", "rollee"))
    criteres = valider_plateformes(
        EXERCICES, [uber], [("uber", date(2026, 11, 15))], {"uber"}, AUJOURD_HUI
    )
    (echec,) = [c for c in criteres if not c.ok]
    assert echec.libelle == "Exercice clos le 30/09/2026 : Uber couvert"
    assert echec.detail == "À compléter : mars 2026, avril 2026."


def test_une_plateforme_declaree_sans_rollee_n_est_pas_a_jour() -> None:
    criteres = valider_plateformes([EN_COURS], [], [], {"bolt"}, AUJOURD_HUI)
    assert {c.libelle: c.detail for c in criteres if not c.ok} == {
        "Exercice en cours : Bolt couvert": "Aucune donnée.",
        "Bolt à jour sur Rollee": "Aucun jour Rollee : relier le compte dans Rollee.",
    }


def test_les_plateformes_declarees_et_les_manques_gardes() -> None:
    assert plateformes_declarees({"plateformes": "uber, bolt,autre"}) == {"uber", "bolt"}
    criteres = valider_plateformes([EN_COURS], [], [], {"bolt"}, AUJOURD_HUI)
    validation = Validation(tuple(criteres), datetime(2026, 11, 18, tzinfo=UTC))
    assert not validation.importe and validation.section_ok("banque")
    assert (
        validation.manques("plateformes")[0] == "Exercice en cours : Bolt couvert : Aucune donnée."
    )
