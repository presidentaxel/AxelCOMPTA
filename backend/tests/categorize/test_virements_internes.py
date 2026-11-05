from __future__ import annotations

from datetime import date

from axelcompta.categorize.virements_internes import apparier_virements_internes
from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction


def _tx(
    id_: str, montant: int, jour: int, compte: str | None, libelle: str = "trésorerie"
) -> NormalizedTransaction:
    return NormalizedTransaction(
        id=TransactionId(id_),
        dossier_id=DossierId("d"),
        date=date(2026, 9, jour),
        montant_cts=montant,
        libelle=libelle,
        source_provider="digifactory",
        raw_payload={},
        compte_bancaire=compte,
    )


def test_deux_jambes_opposees_sur_deux_comptes_sont_appariees() -> None:
    paires = apparier_virements_internes(
        [_tx("sortie", -6_000, 3, "pro"), _tx("entree", 6_000, 3, "fiscal")]
    )
    assert paires == {"sortie": "entree", "entree": "sortie"}


def test_un_jour_d_ecart_est_toléré_deux_non() -> None:
    assert apparier_virements_internes([_tx("a", -100, 3, "pro"), _tx("b", 100, 4, "fiscal")])
    assert not apparier_virements_internes([_tx("a", -100, 3, "pro"), _tx("b", 100, 5, "fiscal")])


def test_meme_compte_ou_compte_inconnu_jamais_apparie() -> None:
    assert not apparier_virements_internes([_tx("a", -100, 3, "pro"), _tx("b", 100, 3, "pro")])
    assert not apparier_virements_internes([_tx("a", -100, 3, None), _tx("b", 100, 3, "pro")])


def test_montants_differents_ou_meme_sens_jamais_apparies() -> None:
    assert not apparier_virements_internes([_tx("a", -100, 3, "pro"), _tx("b", 101, 3, "x")])
    assert not apparier_virements_internes([_tx("a", -100, 3, "pro"), _tx("b", -100, 3, "x")])
    assert not apparier_virements_internes([_tx("a", 0, 3, "pro"), _tx("b", 0, 3, "x")])


def test_chaque_operation_ne_sert_qu_une_fois_au_plus_proche_puis_meme_libelle() -> None:
    """Trois sorties de 50 €, deux entrées : les deux paires du même jour
    l'emportent, la troisième sortie reste seule."""
    transactions = [
        _tx("s_veille", -5_000, 2, "pro", "cotisation urssaf"),
        _tx("s1", -5_000, 3, "pro", "cotisation urssaf"),
        _tx("s2", -5_000, 3, "pro", "autre"),
        _tx("e1", 5_000, 3, "social", "cotisation urssaf"),
        _tx("e2", 5_000, 3, "fiscal", "autre"),
    ]
    paires = apparier_virements_internes(transactions)
    assert paires["e1"] == "s1"
    assert paires["e2"] == "s2"
    assert "s_veille" not in paires
