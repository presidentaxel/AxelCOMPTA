from datetime import date

from axelcompta.bulletin_connexion import LigneBulletin, alertes, rendre


def _ligne(**changes: object) -> LigneBulletin:
    valeurs: dict[str, object] = {
        "dossier_id": "DIGI_1",
        "nom": "MK DRIVING",
        "contact_nr": "1",
        "operations": 120,
        "premiere": date(2026, 6, 2),
        "derniere": date(2026, 11, 20),
        "comptes": 5,
        "comptes_retenus": 5,
        "comptes_a_decider": 0,
        "sante": "ok",
        "consentement": "actif",
        "expire_le": date(2027, 2, 1),
        "quarantaine": 0,
    }
    valeurs.update(changes)
    return LigneBulletin(**valeurs)  # type: ignore[arg-type]


def test_un_dossier_sain_na_pas_dalerte() -> None:
    assert alertes(_ligne()) == ()


def test_auth_forte_et_zero_operation_sont_signales() -> None:
    assert alertes(_ligne(sante="auth_requise", operations=0, premiere=None, derniere=None)) == (
        "connexion auth_requise",
        "zéro opération",
    )


def test_jamais_synchronise_et_consentement_a_renouveler() -> None:
    assert alertes(_ligne(sante=None, consentement="a_renouveler")) == (
        "jamais synchronisé",
        "consentement a_renouveler",
    )


def test_sans_contact_digifactory_seule_alerte() -> None:
    assert alertes(_ligne(contact_nr=None, operations=0)) == ("pas de contact Digifactory",)


def test_rendu_compte_les_dossiers_prets_et_liste_ceux_a_voir() -> None:
    texte = rendre([_ligne(), _ligne(nom="B'CARS", quarantaine=3)], date(2026, 11, 21))
    assert "2 dossiers retenus pour la synchro, 1 prêts à catégoriser." in texte
    assert "| MK DRIVING (DIGI_1) | 120 | 02/06/2026 → 20/11/2026 | 5 (5) | ok" in texte
    assert "- **B'CARS** : 3 en quarantaine" in texte
