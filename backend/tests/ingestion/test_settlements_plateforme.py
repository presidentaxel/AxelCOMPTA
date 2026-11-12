"""AXE-821 : un relevé est gardé une fois par compte et par période."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.providers.base import PlatformSettlement
from axelcompta.ingestion.settlements_plateforme import SettlementsMemoire, cle, fusionner

LE = datetime(2026, 11, 11, tzinfo=UTC)
SEMAINE = PlatformSettlement(
    dossier_id=DossierId("d1"),
    platform="uber",
    period_start=date(2026, 10, 5),
    period_end=date(2026, 10, 11),
    payout_date=date(2026, 10, 11),
    gross_earnings_cts=1_040_00,
    commission_cts=192_00,
    commission_tva_regime="france_20",
    net_payout_cts=848_00,
    currency="EUR",
    source_provider="rollee",
    raw_payload={},
)


def test_nouveau_puis_identique_puis_complete() -> None:
    nouveau = fusionner(None, "acc-1", SEMAINE, LE)
    assert nouveau is not None and (nouveau.id, nouveau.etat) == (
        cle("acc-1", SEMAINE),
        "en_attente_banque",
    )
    assert fusionner(nouveau, "acc-1", SEMAINE, LE) is None
    complete = replace(SEMAINE, gross_earnings_cts=1_100_00, net_payout_cts=908_00)
    suite = fusionner(nouveau, "acc-1", complete, LE)
    assert suite is not None and suite.settlement.net_payout_cts == 908_00
    assert suite.etat == "en_attente_banque"


def test_un_releve_deja_ventile_qui_change_passe_a_verifier_sans_etre_reecrit() -> None:
    nouveau = fusionner(None, "acc-1", SEMAINE, LE)
    assert nouveau is not None
    ventile = replace(nouveau, etat="reconcilie", ecriture_id="S1")
    suite = fusionner(ventile, "acc-1", replace(SEMAINE, net_payout_cts=900_00), LE)
    assert suite is not None and suite.etat == "a_verifier"
    assert suite.settlement.net_payout_cts == 848_00  # la ventilation reste celle écrite


def test_le_depot_en_memoire_trie_par_periode() -> None:
    depot = SettlementsMemoire()
    plus_tot = replace(SEMAINE, period_start=date(2026, 9, 28), period_end=date(2026, 10, 4))
    a, b = fusionner(None, "acc", SEMAINE, LE), fusionner(None, "acc", plus_tot, LE)
    assert a is not None and b is not None
    depot.enregistrer([a, b])
    assert [s.settlement.period_start for s in depot.lister(DossierId("d1"))] == [
        date(2026, 9, 28),
        date(2026, 10, 5),
    ]
