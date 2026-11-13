"""AXE-821 : revenus Rollee → relevés → rapprochement → ventilation."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ingestion.comptes_rollee import (
    ComptesRolleeMemoire,
    UtilisateurRollee,
    depuis_rollee,
)
from axelcompta.ingestion.journal import InMemoryJournalIngestion
from axelcompta.ingestion.providers.base import PlatformSettlement
from axelcompta.ingestion.settlements_plateforme import (
    SettlementsMemoire,
    SettlementStocke,
    fusionner,
)
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import Periode
from axelcompta.plateformes_rollee import ServicesRollee
from axelcompta.revenus_rollee import (
    MOTIF_DELIE,
    DepotsRevenus,
    delier_revenus,
    rapprocher,
    relever_revenus,
)
from axelcompta.tenants.branchements import BranchementsMemoire, nouveau
from axelcompta.tenants.models import Dossier

T, D = TenantId("t"), DossierId("DIGI_1")
LE = datetime(2026, 11, 11, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 11)
DOSSIER = Dossier(D, T, "SAS", "IS", "reel_normal", "MK", "assujetti_taux_reduit", date(2026, 1, 1))
SEMAINE = PlatformSettlement(
    dossier_id=D,
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


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _virement(id_: str, net: int, compte: str = "706", jour: date = date(2026, 10, 13)) -> Ecriture:
    return Ecriture(
        id=EcritureId(id_),
        dossier_id=D,
        journal=Journal.BQ,
        date=jour,
        libelle="Transfer from STICHTING CUSTODIAN UBER PAY",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(net)),
            LigneEcriture(compte, Sens.CREDIT, Money(net)),
        ),
    )


def _stocke(settlement: PlatformSettlement = SEMAINE) -> SettlementStocke:
    stocke = fusionner(None, "acc-uber", settlement, LE)
    assert stocke is not None
    return stocke


def _rapprocher(stockes: list[SettlementStocke], grand_livre: list[Ecriture]) -> Any:
    return rapprocher(stockes, grand_livre, DOSSIER, (), AUJOURD_HUI, LE)


def test_un_virement_en_recette_est_ventile() -> None:
    resultat = _rapprocher([_stocke()], [_virement("S1", 848_00)])
    ((stocke,), (od,)) = (resultat.stockes, resultat.ecritures)
    assert (stocke.etat, stocke.ecriture_id) == ("reconcilie", "S1")
    assert od.id == "S1:ventilation-plateforme"


def test_un_virement_au_compte_d_attente_attend_d_etre_classe() -> None:
    resultat = _rapprocher([_stocke()], [_virement("S1", 848_00, compte="471")])
    assert [s.etat for s in resultat.stockes] == ["a_classer"] and resultat.ecritures == []


def test_un_virement_classe_ailleurs_est_a_verifier() -> None:
    resultat = _rapprocher([_stocke()], [_virement("S1", 848_00, compte="455")])
    assert resultat.stockes[0].motif == "virement classé en 455" and resultat.ecritures == []


def test_une_periode_pas_finie_ou_sans_virement_ne_bouge_pas() -> None:
    en_cours = _stocke(replace(SEMAINE, period_end=AUJOURD_HUI, payout_date=AUJOURD_HUI))
    assert _rapprocher([en_cours], [_virement("S1", 848_00)]).stockes == []
    sans = _rapprocher([_stocke()], [])
    assert sans.stockes == [] and sans.ecritures == []  # déjà en attente : rien de changé


def test_rejouer_ne_ventile_pas_deux_fois() -> None:
    premier = _rapprocher([_stocke()], [_virement("S1", 848_00)])
    deja = [_virement("S1", 848_00), *premier.ecritures]
    second = _rapprocher(premier.stockes, deja)
    assert second.ecritures == [] and second.stockes == []


def test_deux_releves_pour_un_virement_le_second_est_a_verifier() -> None:
    autre = replace(SEMAINE, period_start=date(2026, 10, 6), period_end=date(2026, 10, 12))
    resultat = _rapprocher([_stocke(), _stocke(autre)], [_virement("S1", 848_00)])
    assert [s.etat for s in resultat.stockes] == ["reconcilie", "a_verifier"]
    assert len(resultat.ecritures) == 1


def test_un_virement_d_un_exercice_clos_n_est_pas_ventile() -> None:
    resultat = rapprocher(
        [_stocke()],
        [_virement("S1", 848_00)],
        DOSSIER,
        ((date(2026, 1, 1), date(2026, 10, 31)),),
        AUJOURD_HUI,
        LE,
    )
    assert resultat.stockes[0].motif == "virement dans un exercice clos"
    assert resultat.ecritures == []


class _Client:
    async def revenus(self, account_id: str, depuis: date, jusqua: date) -> dict[str, Any]:
        return {
            "data": [
                {
                    "time_period_start_date": "2026-10-05",
                    "time_period_type": "weekly",
                    "gross_earnings": 1040.0,
                    "platform_fee": 192.0,
                    "payouts": 848.0,
                    "currency": "EUR",
                },
                {
                    "time_period_start_date": "2026-10-12",
                    "time_period_type": "custom",
                    "currency": "EUR",
                },
            ]
        }

    async def aclose(self) -> None:
        return None


def test_de_bout_en_bout_le_ca_et_la_tva_sont_justes_et_rejouer_ne_cree_rien() -> None:
    branchements = BranchementsMemoire()
    branchements.enregistrer(
        [nouveau([], T, "rollee", "rollee", "Rollee", {"jeton": "j", "environnement": "sandbox"})],
        "admin",
        LE,
    )
    comptes = ComptesRolleeMemoire()
    comptes.enregistrer_utilisateur(
        UtilisateurRollee(D, "user-1", branchements.lister(T)[0].id), LE
    )
    comptes.remplacer_comptes(
        D, [depuis_rollee(D, {"id": "acc-uber", "name": "Uber", "connected": True}, None, LE)]
    )
    services = ServicesRollee(branchements, comptes, fabrique=lambda _b, _g: _Client())  # type: ignore[arg-type,return-value]
    ledger, journal = InMemoryLedgerService(), InMemoryJournalIngestion()
    ledger.enregistrer(_virement("S1", 848_00))
    depots = DepotsRevenus(SettlementsMemoire(), ledger, journal)

    resume = asyncio.run(relever_revenus(services, depots, DOSSIER, AUJOURD_HUI))
    asyncio.run(relever_revenus(services, depots, DOSSIER, AUJOURD_HUI))

    def solde(compte: str) -> int:
        return sum(
            (1 if ligne.sens is Sens.CREDIT else -1) * ligne.montant.centimes
            for e in ledger.grand_livre(D)
            for ligne in e.lignes
            if ligne.compte == compte
        )

    assert len(ledger.grand_livre(D)) == 2  # le virement et une seule ventilation
    assert (solde("706"), solde("44571"), -solde("622"), -solde("44566")) == (
        945_45,
        94_55,
        160_00,
        32_00,
    )
    assert "1 versement(s) ventilé(s)" in resume and "1 en quarantaine" in resume
    (quarantaine,) = journal.lister_quarantaine(D)
    assert "custom" in quarantaine.motif


def _soldes_de(ecritures: list[Ecriture]) -> dict[str, int]:
    soldes: dict[str, int] = {}
    for e in ecritures:
        for x in e.lignes:
            signe = 1 if x.sens is Sens.DEBIT else -1
            soldes[x.compte] = soldes.get(x.compte, 0) + signe * x.montant.centimes
    return {c: v for c, v in soldes.items() if v}


def test_un_virement_ventile_puis_reclasse_perd_sa_ventilation() -> None:
    """AXE-889 : décision sur un virement au 471 → 706 → ventilé → usage personnel."""
    from axelcompta.workflow.reclassement import annulations_liees, reclasser

    comptes: tuple[dict[str, str | None], dict[str, str]] = (
        {"usage_personnel": "455"},
        {"recettes_plateformes": "706"},
    )
    virement = _virement("S1", 848_00, compte="471")
    ecritures: list[Ecriture] = [virement]
    en_recette = reclasser(virement, "recettes_plateformes", ecritures, comptes)
    assert en_recette is not None
    ecritures.append(en_recette)
    resultat = rapprocher([_stocke()], ecritures, DOSSIER, (), AUJOURD_HUI, LE)
    (stocke,) = resultat.stockes
    ecritures += resultat.ecritures
    assert _soldes_de(ecritures)["44571"] < 0  # TVA collectée posée par la ventilation

    perso = reclasser(virement, "usage_personnel", ecritures, comptes)
    assert perso is not None
    ecritures.append(perso)
    (annulation,) = annulations_liees(virement, ecritures)
    ecritures.append(annulation)
    assert _soldes_de(ecritures) == {"512": 848_00, "455": -848_00}

    suite = rapprocher([stocke], ecritures, DOSSIER, (), AUJOURD_HUI, LE)
    (a_verifier,) = suite.stockes
    assert a_verifier.etat == "a_verifier" and "annulée" in (a_verifier.motif or "")
    assert suite.ecritures == []


def test_un_virement_qui_reste_en_recette_garde_sa_ventilation() -> None:
    from axelcompta.workflow.reclassement import annulations_liees

    virement = _virement("S1", 848_00)
    resultat = _rapprocher([_stocke()], [virement])
    assert annulations_liees(virement, [virement, *resultat.ecritures]) == []


def test_la_contrepassation_du_virement_emporte_sa_ventilation() -> None:
    from axelcompta.workflow.reclassement import annuler_reclassements

    virement = _virement("S1", 848_00)
    resultat = _rapprocher([_stocke()], [virement])
    (annulation,) = annuler_reclassements(virement.id, [virement, *resultat.ecritures])
    assert annulation.id.startswith("S1:ventilation-plateforme")


def test_delier_contre_passe_les_ventilations_sans_rien_supprimer() -> None:
    """AXE-911 : le lien Rollee était faux."""
    ventile = _rapprocher([_stocke()], [_virement("S1", 848_00)])
    autre = replace(
        _stocke(replace(SEMAINE, period_start=date(2026, 10, 12), period_end=date(2026, 10, 18))),
    )
    grand_livre = [_virement("S1", 848_00), *ventile.ecritures]
    inverses, delies = delier_revenus(
        [*ventile.stockes, autre], frozenset({"acc-uber"}), grand_livre, (), date(2026, 1, 1), LE
    )
    ((inverse,),) = (inverses,)
    assert inverse.id == "S1:ventilation-plateforme:contrepassation"
    assert [(s.etat, s.motif) for s in delies] == [("delie", MOTIF_DELIE)] * 2
    # Rejoué : déjà délié, déjà contre-passé, rien de plus.
    assert delier_revenus(
        delies, frozenset({"acc-uber"}), [*grand_livre, inverse], (), date(2026, 1, 1), LE
    ) == ([], [])


def test_delier_ne_touche_pas_les_comptes_d_un_autre_lien() -> None:
    ventile = _rapprocher([_stocke()], [_virement("S1", 848_00)])
    grand_livre = [_virement("S1", 848_00), *ventile.ecritures]
    assert delier_revenus(
        ventile.stockes, frozenset({"acc-bolt"}), grand_livre, (), date(2026, 1, 1), LE
    ) == ([], [])


def test_delier_dans_un_exercice_clos_passe_par_l_exercice_ouvert() -> None:
    ventile = _rapprocher([_stocke()], [_virement("S1", 848_00)])
    grand_livre = [_virement("S1", 848_00), *ventile.ecritures]
    clos: tuple[Periode, ...] = ((date(2026, 1, 1), date(2026, 12, 31)),)
    inverses, _ = delier_revenus(
        ventile.stockes, frozenset({"acc-uber"}), grand_livre, clos, date(2027, 1, 1), LE
    )
    assert inverses[0].date == date(2027, 1, 1)
