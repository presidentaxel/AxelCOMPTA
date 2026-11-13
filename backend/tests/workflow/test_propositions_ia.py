"""AXE-888 : propositions de l'IA, demandées une seule fois par libellé."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from axelcompta.categorize.llm import DemandeIa
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.pseudonymize.detecter import FuiteDetectee
from axelcompta.pseudonymize.prompt import PseudonymizedPrompt
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.propositions_ia import (
    PropositionIa,
    PropositionsIaMemoire,
    categories_proposables,
    demandes_a_envoyer,
    par_lots,
    proposer,
)

DOSSIER = Dossier(
    id=DossierId("d1"),
    tenant_id=TenantId("t"),
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="MK DRIVING",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
)
CATEGORIES = ["carburant", "repas_et_receptions", "non_categorise_a_verifier"]
CONTEXTE = ("claude-fable-5-2", "v-test", datetime(2026, 11, 12, tzinfo=UTC))


class FournisseurEcho:
    nom = "echo"

    def __init__(self, categorie: str = "repas_et_receptions") -> None:
        self.prompts: list[str] = []
        self._categorie = categorie

    def completer(self, prompt: PseudonymizedPrompt) -> str:
        self.prompts.append(prompt.texte)
        rangs = json.loads(prompt.texte.split("Opérations :\n", 1)[1])
        return json.dumps(
            {
                "propositions": [
                    {
                        "id": o["id"],
                        "categorie": self._categorie,
                        "confiance": 0.8,
                        "justification": "ok",
                    }
                    for o in rangs
                ]
            }
        )


def test_un_libelle_deja_connu_ne_repart_pas() -> None:
    operations = [
        ("CB BOULANGERIE PAUL 12/03", -450, "card"),
        ("CB BOULANGERIE PAUL 14/03", -380, "card"),  # même libellé normalisé
        ("CB TOTAL ACCESS", -6000, "card"),
        ("1234", -100, None),  # rien à envoyer : que des chiffres
    ]
    demandes = demandes_a_envoyer(operations, deja={"cb total access"})
    assert [d.cle for d in demandes] == ["cb boulangerie paul"]


def test_la_societe_ne_part_jamais_en_clair() -> None:
    fournisseur = FournisseurEcho()
    demande = DemandeIa("vir mk driving", "VIR MK DRIVING EPARGNE", -10_000, "transfer")
    (proposition,) = proposer(DOSSIER, [demande], fournisseur, CATEGORIES, CONTEXTE)
    assert "MK DRIVING" not in fournisseur.prompts[0]
    assert "{SOCIETE_1}" in fournisseur.prompts[0]
    assert proposition == PropositionIa(
        DOSSIER.id,
        "vir mk driving",
        "v-test",
        "repas_et_receptions",
        0.8,
        "ok",
        "claude-fable-5-2",
        CONTEXTE[2],
    )


def test_a_verifier_est_garde_mais_n_est_pas_propose() -> None:
    (p,) = proposer(
        DOSSIER,
        [DemandeIa("x", "LIBELLE X", -100, None)],
        FournisseurEcho("non_categorise_a_verifier"),
        CATEGORIES,
        CONTEXTE,
    )
    assert not p.proposable


def test_le_depot_garde_la_premiere_reponse_par_version() -> None:
    depot = PropositionsIaMemoire()
    premiere = PropositionIa(DOSSIER.id, "c", "v1", "carburant", 0.9, "", "m", CONTEXTE[2])
    depot.enregistrer([premiere])
    depot.enregistrer(
        [PropositionIa(DOSSIER.id, "c", "v1", "repas_et_receptions", 0.9, "", "m", CONTEXTE[2])]
    )
    assert depot.lister(DOSSIER.id, "v1") == {"c": premiere}
    assert depot.lister(DOSSIER.id, "v2") == {}


def test_les_lots_restent_courts() -> None:
    demandes = [DemandeIa(str(i), str(i), -1, None) for i in range(170)]
    assert [len(lot) for lot in par_lots(demandes)] == [80, 80, 10]


def test_la_taxonomie_ecarte_les_categories_techniques() -> None:
    categories = categories_proposables(["carburant", "dividendes_associes", "repas_et_receptions"])
    assert categories == [
        "carburant",
        "repas_et_receptions",
        "usage_personnel",
        "non_categorise_a_verifier",
    ]


def test_un_prompt_avec_fuite_ne_part_pas() -> None:
    with pytest.raises(FuiteDetectee):
        PseudonymizedPrompt(DOSSIER.id, "VIR MK DRIVING", ("MK DRIVING",))
