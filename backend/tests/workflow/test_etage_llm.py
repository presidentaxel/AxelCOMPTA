"""AXE-887 : l'étage LLM de la synchro, avec un faux fournisseur (aucun appel)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from axelcompta.categorize.llm import CATEGORIE_A_VERIFIER, VERSION_PROMPT
from axelcompta.pseudonymize.fournisseur_anthropic import RequeteLot, ResultatLot
from axelcompta.workflow.budget_llm import Plafonds
from axelcompta.workflow.etage_llm import (
    JUSTIFICATION_INCOMPLETE,
    MESSAGE_COUPE_CIRCUIT,
    DepotsLlm,
    DossierATrancher,
    relever,
    soumettre,
)
from axelcompta.workflow.lots_llm import LotsLlmMemoire
from axelcompta.workflow.propositions_ia import PropositionsIaMemoire
from tests.workflow.test_budget_llm import lot
from tests.workflow.test_propositions_ia import CATEGORIES, DOSSIER

MAINTENANT = datetime(2026, 11, 13, 9, tzinfo=UTC)
OPERATIONS = (
    ("CB BOULANGERIE DU PORT 12/11", -450, "carte"),
    ("CB BOULANGERIE DU PORT 13/11", -380, "carte"),
    ("PRLV MK DRIVING ASSURANCE", -9000, "prelevement"),
)
GENEREUX = Plafonds(chauffeur_usd=10, global_usd=100)


class FauxLots:
    """Tient le rôle de l'API Batch : garde les requêtes, rend ce qu'on lui dit."""

    modele = "claude-fable-5-2"
    taille_systeme = 2_000

    def __init__(self) -> None:
        self.requetes: list[RequeteLot] = []
        self.resultats: dict[str, list[ResultatLot] | None] = {}
        self.panne = False

    def soumettre(self, requetes: list[RequeteLot]) -> str:
        if self.panne:
            raise ConnectionError("réseau")
        self.requetes += requetes
        batch_id = f"batch-{len(self.resultats)}"
        self.resultats[batch_id] = None
        return batch_id

    def relever(self, batch_id: str) -> list[ResultatLot] | None:
        return self.resultats[batch_id]

    def repondre(self, batch_id: str, categorie: str = "repas_et_receptions") -> None:
        resultats = []
        for requete in self.requetes:
            rangs = json.loads(requete.prompt.texte.split("Opérations :\n", 1)[1])
            texte = json.dumps(
                {
                    "propositions": [
                        {
                            "id": r["id"],
                            "categorie": categorie,
                            "confiance": 0.9,
                            "justification": "x",
                        }
                        for r in rangs
                    ]
                }
            )
            resultats.append(ResultatLot(requete.custom_id, "termine", texte, 1_000, 200, 800))
        self.resultats[batch_id] = resultats


def _depots() -> DepotsLlm:
    return DepotsLlm(LotsLlmMemoire(), PropositionsIaMemoire())


def _a_trancher() -> list[DossierATrancher]:
    return [DossierATrancher(DOSSIER, OPERATIONS)]


def test_un_lot_par_dossier_libelles_dedoublonnes_et_pseudonymises() -> None:
    depots, fournisseur = _depots(), FauxLots()
    lignes = soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT)
    (requete,) = fournisseur.requetes
    assert "MK DRIVING" not in requete.prompt.texte  # la société du chauffeur
    (reserve,) = depots.lots.lister(MAINTENANT - timedelta(days=1))
    assert reserve.statut == "soumis" and reserve.batch_id == "batch-0"
    assert len(reserve.cles) == 2  # deux boulangeries, un seul libellé normalisé
    assert reserve.estimation_usd > 0
    assert "1 lot(s) soumis" in lignes[-1]


def test_un_second_passage_le_meme_jour_n_envoie_rien() -> None:
    depots, fournisseur = _depots(), FauxLots()
    soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT)
    soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT + timedelta(hours=1))
    assert len(fournisseur.requetes) == 1


def test_les_propositions_relevees_vont_au_cache_et_ne_repartent_plus() -> None:
    depots, fournisseur = _depots(), FauxLots()
    soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT)
    assert relever(depots, fournisseur, CATEGORIES, MAINTENANT) == []  # pas fini
    fournisseur.repondre("batch-0")
    relever(depots, fournisseur, CATEGORIES, MAINTENANT + timedelta(hours=1))
    cache = depots.propositions.lister(DOSSIER.id, VERSION_PROMPT)
    assert {p.categorie for p in cache.values()} == {"repas_et_receptions"}
    (fini,) = depots.lots.lister(MAINTENANT - timedelta(days=1))
    assert fini.statut == "termine" and fini.cout_usd > 0 and fini.jetons_cache == 800
    lendemain = MAINTENANT + timedelta(days=1)
    assert soumettre(depots, fournisseur, _a_trancher(), GENEREUX, lendemain) == []
    assert len(fournisseur.requetes) == 1


def test_une_reponse_invalide_ou_incomplete_devient_a_verifier_sans_nouvel_appel() -> None:
    depots, fournisseur = _depots(), FauxLots()
    soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT)
    (requete,) = fournisseur.requetes
    fournisseur.resultats["batch-0"] = [ResultatLot(requete.custom_id, "termine", "pas du JSON")]
    relever(depots, fournisseur, CATEGORIES, MAINTENANT)
    cache = depots.propositions.lister(DOSSIER.id, VERSION_PROMPT)
    assert len(cache) == 2
    assert all(p.categorie == CATEGORIE_A_VERIFIER for p in cache.values())
    assert all(p.justification == JUSTIFICATION_INCOMPLETE for p in cache.values())


def test_un_refus_laisse_les_libelles_a_l_humain_pour_de_bon() -> None:
    depots, fournisseur = _depots(), FauxLots()
    soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT)
    (requete,) = fournisseur.requetes
    fournisseur.resultats["batch-0"] = [ResultatLot(requete.custom_id, "refus")]
    relever(depots, fournisseur, CATEGORIES, MAINTENANT)
    assert depots.propositions.lister(DOSSIER.id, VERSION_PROMPT) == {}
    soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT + timedelta(days=1))
    assert len(fournisseur.requetes) == 1


def test_un_echec_est_retente_une_fois_le_lendemain_puis_abandonne() -> None:
    depots, fournisseur = _depots(), FauxLots()
    for jour in range(3):
        quand = MAINTENANT + timedelta(days=jour)
        soumettre(depots, fournisseur, _a_trancher(), GENEREUX, quand)
        dernier = fournisseur.requetes[-1]
        fournisseur.resultats[f"batch-{len(fournisseur.resultats) - 1}"] = [
            ResultatLot(dernier.custom_id, "echec")
        ]
        relever(depots, fournisseur, CATEGORIES, quand)
    assert len(fournisseur.requetes) == 2  # la tentative et une nouvelle, pas plus
    assert fournisseur.requetes[0].custom_id != fournisseur.requetes[1].custom_id


def test_une_soumission_en_panne_est_reprise_le_lendemain_avec_le_meme_lot() -> None:
    depots, fournisseur = _depots(), FauxLots()
    fournisseur.panne = True
    lignes = soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT)
    assert "soumission en échec" in lignes[-1]
    (echoue,) = depots.lots.lister(MAINTENANT - timedelta(days=1))
    assert echoue.statut == "echec" and echoue.batch_id is None
    fournisseur.panne = False
    soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT + timedelta(days=1))
    (repris,) = depots.lots.lister(MAINTENANT - timedelta(days=1))
    assert repris.id == echoue.id and repris.batch_id is not None


def test_budget_atteint_aucun_appel_et_les_operations_restent_a_l_humain() -> None:
    depots, fournisseur = _depots(), FauxLots()
    depots.lots.enregistrer([lot("deja", dossier="d1", cout_usd=0.5, soumis_le=MAINTENANT)])
    lignes = soumettre(
        depots, fournisseur, _a_trancher(), Plafonds(0.5, 100), MAINTENANT + timedelta(days=1)
    )
    assert fournisseur.requetes == []
    assert "budget du chauffeur atteint" in lignes[0]


def test_le_coupe_circuit_ouvert_n_envoie_rien() -> None:
    depots, fournisseur = _depots(), FauxLots()
    depots.lots.enregistrer(
        [lot(f"ko{i}", dossier=f"x{i}", statut="echec", soumis_le=MAINTENANT) for i in range(3)]
    )
    assert soumettre(depots, fournisseur, _a_trancher(), GENEREUX, MAINTENANT) == [
        MESSAGE_COUPE_CIRCUIT
    ]
    assert fournisseur.requetes == []


def test_une_reservation_jamais_partie_finit_en_echec() -> None:
    depots, fournisseur = _depots(), FauxLots()
    reserve = lot("r", statut="soumis", batch_id=None, soumis_le=MAINTENANT, termine_le=None)
    depots.lots.enregistrer([reserve])
    relever(depots, fournisseur, CATEGORIES, MAINTENANT + timedelta(hours=3))
    (perime,) = depots.lots.lister(MAINTENANT - timedelta(days=1))
    assert perime.statut == "echec"
    assert replace(perime, statut="soumis", termine_le=None) == reserve
