"""AXE-816 : le script de mesure apparie les virements internes comme la synchro."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.packs.vtc_demo import charger_categories_banque, charger_regles

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "mesurer_objectifs.py"
_spec = importlib.util.spec_from_file_location("mesurer_objectifs", _SCRIPT)
assert _spec is not None and _spec.loader is not None
mesurer_objectifs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mesurer_objectifs)


def _paire(compte_sortie: str, compte_entree: str) -> list[dict[str, str]]:
    commun = {"libelle": "carburant", "categorie": "virement_interne", "date": "2026-10-03"}
    return [
        {**commun, "montant_cts": "-15000", "compte_bancaire": compte_sortie},
        {**commun, "montant_cts": "15000", "compte_bancaire": compte_entree},
    ]


def _pipeline() -> RulesAndMlPipeline:
    return RulesAndMlPipeline(
        regles=charger_regles(), categories_banque=charger_categories_banque()
    )


def test_une_enveloppe_entre_deux_comptes_est_un_virement_interne() -> None:
    observations = mesurer_objectifs.observer(_paire("pro", "fiscal"), _pipeline())
    assert [o.proposee for o in observations] == ["virement_interne"] * 2


def test_sans_compte_l_enveloppe_passe_pour_du_carburant() -> None:
    sortie, _entree = mesurer_objectifs.observer(_paire("", ""), _pipeline())
    assert sortie.proposee == "carburant"
