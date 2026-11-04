from __future__ import annotations

from dataclasses import replace

import pytest

import axelcompta.demo_seed as demo_seed
from axelcompta.agregats_portefeuille import Rapport, recalculer, verifier
from axelcompta.core.ids import DossierId
from axelcompta.demo_chauffeurs_type import construire_ledger
from axelcompta.demo_seed import TENANT_DEMO
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.tenants.agregats import InMemoryAgregatsRepository
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.provisions_cloture import InMemoryProvisionsClotureRepository
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository
from axelcompta.workflow.propositions import InMemoryPropositionRepository

SOPHIE = DossierId("DEMO_sophie")


@pytest.fixture(autouse=True)
def _ledger_calcule_une_seule_fois(monkeypatch: pytest.MonkeyPatch) -> None:
    cache: dict[object, object] = {}
    monkeypatch.setattr(
        demo_seed,
        "construire_ledger",
        lambda profil: cache.setdefault(profil, construire_ledger(profil)),
    )


class _Portefeuille:
    def __init__(self) -> None:
        depot = InMemoryDossierRepository()
        self.base = InMemoryLedgerService()
        demo_seed.amorcer_demo(depot, self.base, InMemoryPropositionRepository())
        self.dossiers: tuple[Dossier, ...] = tuple(depot.lister_par_tenant(TENANT_DEMO))
        self.decisions = InMemoryDecisionRepository()
        self.provisions = InMemoryProvisionsClotureRepository()
        self.agregats = InMemoryAgregatsRepository()

    def recalculer(self, tout: bool = False) -> int:
        return recalculer(
            self.dossiers, self.base, self.decisions, self.provisions, self.agregats, tout
        )

    def verifier(self) -> Rapport:
        return verifier(self.dossiers, self.base, self.decisions, self.provisions, self.agregats)


def test_recalculer_remplit_les_dossiers_jamais_calcules_puis_ne_refait_rien() -> None:
    portefeuille = _Portefeuille()

    assert portefeuille.recalculer() == 3
    assert portefeuille.recalculer() == 0


def test_recalculer_ne_refait_que_les_dossiers_perimes() -> None:
    portefeuille = _Portefeuille()
    portefeuille.recalculer()
    portefeuille.agregats.invalider(SOPHIE)

    assert portefeuille.recalculer() == 1
    assert portefeuille.recalculer() == 0


def test_recalculer_tout_refait_meme_les_dossiers_a_jour() -> None:
    portefeuille = _Portefeuille()
    portefeuille.recalculer()

    assert portefeuille.recalculer(tout=True) == 3


def test_verifier_ne_trouve_aucun_ecart_apres_un_recalcul() -> None:
    portefeuille = _Portefeuille()
    portefeuille.recalculer()

    rapport = portefeuille.verifier()

    assert (rapport.a_jour, rapport.perimes, rapport.modifies_pendant) == (3, 0, 0)
    assert rapport.divergences == ()


def test_verifier_ne_juge_pas_un_dossier_perime_ni_jamais_calcule() -> None:
    portefeuille = _Portefeuille()
    portefeuille.recalculer()
    portefeuille.agregats.invalider(SOPHIE)

    rapport = portefeuille.verifier()

    assert (rapport.a_jour, rapport.perimes) == (2, 1)
    assert rapport.divergences == ()


def test_verifier_signale_un_agregat_garde_qui_n_est_plus_le_bon() -> None:
    """Une invalidation manquée : la ligne est à jour mais ne dit plus la vérité."""
    portefeuille = _Portefeuille()
    portefeuille.recalculer()
    ligne = portefeuille.agregats.lire([SOPHIE])[SOPHIE]
    assert ligne.valeur is not None
    faux = replace(ligne.valeur, ca_ht_cts=ligne.valeur.ca_ht_cts + 100)
    assert portefeuille.agregats.enregistrer(TENANT_DEMO, SOPHIE, faux, ligne.version)

    rapport = portefeuille.verifier()

    assert [ecart.dossier_id for ecart in rapport.divergences] == [SOPHIE]
    assert rapport.divergences[0].gardee == faux
    assert rapport.a_jour == 2


def test_verifier_ne_modifie_rien() -> None:
    portefeuille = _Portefeuille()
    portefeuille.agregats.invalider(SOPHIE)
    avant = portefeuille.agregats.lire([d.id for d in portefeuille.dossiers])

    portefeuille.verifier()

    assert portefeuille.agregats.lire([d.id for d in portefeuille.dossiers]) == avant
