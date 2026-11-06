"""Synchronisation d'un dossier réel (workflow/synchro.py) : idempotence,
reprise, quarantaine. Source = `DigifactoryProvider` sur payload injecté, donc
le vrai parseur ; ledger, journal et propositions en mémoire."""

from __future__ import annotations

import asyncio
import dataclasses
from copy import deepcopy
from datetime import date, datetime
from typing import Any

import httpx
import pytest

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.ids import DossierId, TenantId, TransactionId
from axelcompta.ingestion.comptes_bancaires import CompteBancaireMemoire
from axelcompta.ingestion.journal import InMemoryJournalIngestion
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ingestion.providers.digifactory import (
    ContactNonMappeError,
    DigifactoryHttpClient,
    DigifactoryProvider,
)
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie, charger_regles
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.propositions import InMemoryPropositionRepository
from axelcompta.workflow.synchro import RapportSynchro, choisir_compte, synchroniser_dossier

DOSSIER = Dossier(
    id=DossierId("d1"),
    tenant_id=TenantId("t"),
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="Test",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
    contact_nr="42",
)


def _tx(
    id_: str, libelle: str, montant: float, jour: str, maj: str, **extra: Any
) -> dict[str, Any]:
    return {
        "id": id_,
        "provider_description": libelle,
        "amount": montant,
        "date": jour,
        "updated_at": maj,
        "deleted": False,
        "future": False,
        **extra,
    }


PAYLOAD: dict[str, Any] = {
    "acc": [
        _tx("t1", "CARTE TOTAL STATION", -60.0, "2026-03-01", "2026-03-01 10:00:00"),
        _tx("t2", "VIR RECU UBER BV", 848.0, "2026-03-02", "2026-03-02 10:00:00"),
        _tx("t3", "PAIEMENT MYSTERE XYZ", -12.5, "2026-03-03", "2026-03-03 10:00:00"),
    ]
}


def _modifiee() -> dict[str, Any]:
    """t1 réécrite côté fournisseur : même transaction, montant différent."""
    return _tx("t1", "CARTE TOTAL STATION", -75.0, "2026-03-01", "2026-03-05 08:00:00")


class Env:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = deepcopy(payload if payload is not None else PAYLOAD)
        self.ledger = InMemoryLedgerService()
        self.journal = InMemoryJournalIngestion()
        self.propositions = InMemoryPropositionRepository()

    def synchroniser(self) -> RapportSynchro:
        return asyncio.run(
            synchroniser_dossier(
                DOSSIER,
                DigifactoryProvider(payload=self.payload),
                "digifactory",
                self.journal,
                self.ledger,
                self.propositions,
                RulesAndMlPipeline(regles=charger_regles(), modele=None),
                charger_compte_par_categorie(),
            )
        )

    def comptes(self, transaction_id: str) -> set[str]:
        ecriture = next(
            e for e in self.ledger.grand_livre(DOSSIER.id) if e.id.endswith(f"-{transaction_id}")
        )
        return {ligne.compte for ligne in ecriture.lignes} - {"512"}


def test_premiere_synchro_comptabilise_et_envoie_le_doute_au_compte_dattente() -> None:
    env = Env()

    rapport = env.synchroniser()

    assert (rapport.nouvelles, rapport.a_trancher) == (3, 2)
    assert env.comptes("t1") != {"471"}  # règle carburant, haute confiance
    assert env.comptes("t2") == {"471"}  # virement Uber : attente du settlement, jamais 706
    assert env.comptes("t3") == {"471"}  # aucune règle, pas de modèle


def test_relancer_ne_cree_aucun_doublon() -> None:
    env = Env()
    env.synchroniser()

    rapport = env.synchroniser()

    # Reprise au curseur : seule la dernière ligne est relue (recouvrement
    # de la borne inclusive), et elle est reconnue, pas recomptabilisée.
    assert (rapport.nouvelles, rapport.deja_connues) == (0, 1)
    assert len(env.ledger.grand_livre(DOSSIER.id)) == 3


def test_relecture_complete_sans_curseur_ne_cree_aucun_doublon() -> None:
    env = Env()
    env.synchroniser()
    env.journal._curseurs.clear()  # simule une perte du curseur

    rapport = env.synchroniser()

    assert (rapport.nouvelles, rapport.deja_connues) == (0, 3)
    assert len(env.ledger.grand_livre(DOSSIER.id)) == 3


def test_chaque_ecriture_a_une_proposition_dorigine() -> None:
    env = Env()
    env.synchroniser()

    for ecriture in env.ledger.grand_livre(DOSSIER.id):
        assert env.propositions.obtenir(DOSSIER.id, ecriture.id) is not None


def test_le_curseur_avance_et_la_reprise_ne_relit_que_les_mises_a_jour() -> None:
    env = Env()
    env.synchroniser()
    assert env.journal.curseur(DOSSIER.id, "digifactory") == datetime(2026, 3, 3, 10, 0, 0)

    env.payload["acc"].append(_tx("t4", "SANEF PEAGE", -8.0, "2026-03-04", "2026-03-04 09:00:00"))
    rapport = env.synchroniser()

    assert (rapport.nouvelles, rapport.deja_connues) == (1, 1)
    assert env.journal.curseur(DOSSIER.id, "digifactory") == datetime(2026, 3, 4, 9, 0, 0)


def test_une_ligne_illisible_va_en_quarantaine_sans_bloquer_les_autres() -> None:
    env = Env()
    env.payload["acc"].append({"provider_description": "SANS ID", "amount": 5.0})

    rapport = env.synchroniser()

    assert (rapport.nouvelles, rapport.rejets) == (3, 1)
    (entree,) = env.journal.lister_quarantaine(DOSSIER.id)
    assert entree.motif.startswith("ligne_illisible")


def test_montant_modifie_apres_comptabilisation_est_signale_pas_reecrit() -> None:
    env = Env()
    env.synchroniser()
    env.payload["acc"][0] = _tx(
        "t1", "CARTE TOTAL STATION", -75.0, "2026-03-01", "2026-03-05 08:00:00"
    )

    rapport = env.synchroniser()

    assert rapport.modifiees_signalees == 1
    (entree,) = env.journal.lister_quarantaine(DOSSIER.id)
    assert entree.motif == "modifiee_apres_comptabilisation"
    montant_512 = next(
        ligne.montant.centimes
        for e in env.ledger.grand_livre(DOSSIER.id)
        if e.id.endswith("-t1")
        for ligne in e.lignes
        if ligne.compte == "512"
    )
    assert montant_512 == 6000  # l'écriture d'origine n'a pas bougé
    contres = [e for e in env.ledger.grand_livre(DOSSIER.id) if e.id.endswith(":contrepassation")]
    assert len(contres) == 1


def test_le_meme_signalement_nest_pas_repete_a_chaque_synchro() -> None:
    env = Env()
    env.synchroniser()
    env.payload["acc"][0] = _tx(
        "t1", "CARTE TOTAL STATION", -75.0, "2026-03-01", "2026-03-05 08:00:00"
    )
    env.synchroniser()
    env.synchroniser()

    assert len(env.journal.lister_quarantaine(DOSSIER.id)) == 1
    contres = [e for e in env.ledger.grand_livre(DOSSIER.id) if e.id.endswith(":contrepassation")]
    assert len(contres) == 1


def test_ligne_revenue_a_lidentique_apres_contre_passation_nest_pas_deja_connue() -> None:
    env = Env()
    env.synchroniser()
    env.payload["acc"][0] = _modifiee()
    env.synchroniser()
    env.payload["acc"][0] = _tx(
        "t1", "CARTE TOTAL STATION", -60.0, "2026-03-01", "2026-03-07 08:00:00"
    )

    rapport = env.synchroniser()

    assert (rapport.deja_connues, rapport.modifiees_signalees) == (0, 1)
    assert len(env.journal.lister_quarantaine(DOSSIER.id)) == 2
    contres = [e for e in env.ledger.grand_livre(DOSSIER.id) if e.id.endswith(":contrepassation")]
    assert len(contres) == 1


def test_transaction_supprimee_apres_comptabilisation_est_signalee() -> None:
    env = Env()
    env.synchroniser()
    env.payload["acc"][0]["deleted"] = True
    env.payload["acc"][0]["updated_at"] = "2026-03-06 08:00:00"

    rapport = env.synchroniser()

    assert rapport.supprimees_signalees == 1
    assert len(env.ledger.grand_livre(DOSSIER.id)) == 4


def test_transaction_supprimee_avant_comptabilisation_nest_jamais_comptabilisee() -> None:
    env = Env()
    env.payload["acc"][0]["deleted"] = True

    rapport = env.synchroniser()

    assert (rapport.nouvelles, rapport.supprimees_signalees) == (2, 0)


def test_larchive_brute_est_idempotente() -> None:
    env = Env()
    env.synchroniser()
    env.synchroniser()

    assert len(env.journal.brut) == 3


def test_dossier_sans_contact_digifactory_est_refuse() -> None:
    sans_contact = dataclasses.replace(DOSSIER, contact_nr=None)
    with pytest.raises(ContactNonMappeError):
        asyncio.run(DigifactoryProvider(payload=PAYLOAD).lire_lot(sans_contact, None))


def test_appel_reel_utilise_le_contact_du_dossier_et_le_curseur() -> None:
    demandes: list[httpx.Request] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        demandes.append(requete)
        return httpx.Response(200, json=PAYLOAD)

    client = DigifactoryHttpClient(
        "https://exemple.test",
        "jeton",
        client=httpx.AsyncClient(
            base_url="https://exemple.test",
            headers={"X_DIGI_TOKEN": "jeton"},
            transport=httpx.MockTransport(repondre),
        ),
    )

    lot = asyncio.run(
        DigifactoryProvider(client_reel=client).lire_lot(DOSSIER, datetime(2026, 3, 1, 12, 0, 0))
    )

    assert demandes[0].url.path == "/transactions/42"
    assert demandes[0].url.params["since"] == "2026-03-01 12:00:00"
    assert len(lot.transactions) == 3


@pytest.mark.parametrize(
    ("etage", "confiance", "categorie", "attendu_471"),
    [
        (Etage.REGLE, 0.95, "carburant", False),
        (Etage.REGLE, 0.5, "carburant", True),
        (Etage.ML, 0.95, "carburant", False),
        (Etage.ML, 0.80, "carburant", True),
        (Etage.REGLE, 0.95, "recettes_plateformes", True),
        (Etage.REGLE, 0.95, "categorie_inconnue_du_mapping", True),
        (Etage.REVUE_HUMAINE, 1.0, "carburant", True),
    ],
)
def test_politique_dacceptation_automatique(
    etage: Etage, confiance: float, categorie: str, attendu_471: bool
) -> None:
    proposition = ProposedEntry(
        dossier_id=DOSSIER.id,
        transaction_id=TransactionId("x"),
        categorie=categorie,
        etage=etage,
        confiance=confiance,
    )

    compte = choisir_compte(proposition, charger_compte_par_categorie())

    assert (compte == "471") is attendu_471


def _proposition_ml(categorie: str, confiance: float, seuil: float | None) -> ProposedEntry:
    return ProposedEntry(
        dossier_id=DossierId("d"),
        transaction_id=TransactionId("t"),
        categorie=categorie,
        etage=Etage.ML,
        confiance=confiance,
        seuil_imputation=seuil,
    )


def test_le_seuil_propre_a_la_categorie_decide_de_l_imputation() -> None:
    """Modèle calibré : chaque catégorie a son seuil ; `inf`, jamais seule."""
    comptes = {"carburant": "6061", "subventions": "741"}
    assert choisir_compte(_proposition_ml("carburant", 0.96, 0.95), comptes) == "6061"
    assert choisir_compte(_proposition_ml("carburant", 0.94, 0.95), comptes) == "471"
    assert choisir_compte(_proposition_ml("subventions", 0.99, float("inf")), comptes) == "471"
    # Sans calibration, le seuil historique de 0,90.
    assert choisir_compte(_proposition_ml("carburant", 0.91, None), comptes) == "6061"


def test_un_repas_reconnu_par_regle_n_est_jamais_impute_seul() -> None:
    """La règle « repas » signale un usage personnel probable : proposée,
    jamais imputée sans l'indiv (sa confiance reste sous le seuil des règles)."""
    pipeline = RulesAndMlPipeline(regles=charger_regles())
    transaction = NormalizedTransaction(
        id=TransactionId("t"),
        dossier_id=DossierId("d"),
        date=date(2026, 9, 3),
        montant_cts=-3_000,
        libelle="CB CARREFOUR MARKET",
        source_provider="fixture",
        raw_payload={},
    )
    proposition = pipeline.categoriser(DossierId("d"), transaction)
    assert proposition.categorie == "repas_et_receptions"
    assert choisir_compte(proposition, charger_compte_par_categorie()) == "471"


def _synchroniser_avec_comptes(
    env: Env, comptes_bancaires: CompteBancaireMemoire
) -> RapportSynchro:
    return asyncio.run(
        synchroniser_dossier(
            DOSSIER,
            DigifactoryProvider(payload=env.payload),
            "digifactory",
            env.journal,
            env.ledger,
            env.propositions,
            RulesAndMlPipeline(regles=charger_regles(), modele=None),
            charger_compte_par_categorie(),
            comptes_bancaires,
        )
    )


def _banques(env: Env) -> dict[str, str]:
    """Ligne de banque de chaque écriture, par id de transaction."""
    return {
        e.id.rsplit("-", 1)[-1]: next(
            ligne.compte for ligne in e.lignes if ligne.compte.startswith("512")
        )
        for e in env.ledger.grand_livre(DOSSIER.id)
    }


def test_chaque_compte_bancaire_a_son_sous_compte_512() -> None:
    """AXE-832 : MK DRIVING a 5 comptes ; chacun son 512x, pas un 512 commun."""
    env = Env(
        {
            "acc": [
                _tx(
                    "t1",
                    "CARTE TOTAL STATION",
                    -60.0,
                    "2026-03-01",
                    "2026-03-01 10:00:00",
                    account_id="pro",
                ),
                _tx(
                    "t2",
                    "VIR RECU UBER BV",
                    848.0,
                    "2026-03-02",
                    "2026-03-02 10:00:00",
                    account_id="fiscal",
                ),
                _tx(
                    "t3",
                    "PAIEMENT MYSTERE XYZ",
                    -12.5,
                    "2026-03-03",
                    "2026-03-03 10:00:00",
                    account_id="pro",
                ),
                _tx("t4", "SANS COMPTE", -1.0, "2026-03-04", "2026-03-04 10:00:00"),
            ]
        }
    )
    comptes = CompteBancaireMemoire()

    _synchroniser_avec_comptes(env, comptes)

    assert _banques(env) == {"t1": "5121", "t2": "5122", "t3": "5121", "t4": "512"}
    assert {c.identifiant: c.compte_comptable for c in comptes.lister(DOSSIER.id)} == {
        "pro": "5121",
        "fiscal": "5122",
    }
    for ecriture in env.ledger.grand_livre(DOSSIER.id):
        verifier_equilibre(ecriture)


def test_une_resynchro_sur_un_sous_compte_reste_idempotente() -> None:
    """La signature d'une écriture se lit aussi sur un 512x : rien de
    « modifié » à la deuxième lecture."""
    env = Env(
        {
            "acc": [
                _tx(
                    "t1",
                    "CARTE TOTAL STATION",
                    -60.0,
                    "2026-03-01",
                    "2026-03-01 10:00:00",
                    account_id="pro",
                )
            ]
        }
    )
    comptes = CompteBancaireMemoire()
    _synchroniser_avec_comptes(env, comptes)
    env.payload = {"acc": [_modifiee() | {"amount": -60.0, "account_id": "pro"}]}

    rapport = _synchroniser_avec_comptes(env, comptes)

    assert (rapport.nouvelles, rapport.deja_connues, rapport.modifiees_signalees) == (0, 1, 0)


def test_un_montant_modifie_sur_un_sous_compte_est_contre_passe() -> None:
    env = Env(
        {
            "acc": [
                _tx(
                    "t1",
                    "CARTE TOTAL STATION",
                    -60.0,
                    "2026-03-01",
                    "2026-03-01 10:00:00",
                    account_id="pro",
                )
            ]
        }
    )
    comptes = CompteBancaireMemoire()
    _synchroniser_avec_comptes(env, comptes)
    env.payload = {"acc": [_modifiee() | {"account_id": "pro"}]}

    rapport = _synchroniser_avec_comptes(env, comptes)

    assert rapport.modifiees_signalees == 1
    inverses = [e for e in env.ledger.grand_livre(DOSSIER.id) if e.id.endswith(":contrepassation")]
    assert len(inverses) == 1
    assert any(ligne.compte == "5121" for ligne in inverses[0].lignes)
