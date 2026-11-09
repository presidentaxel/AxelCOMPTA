"""AXE-825 : sans modèle, la synchro s'arrête et le dit."""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import pytest

from axelcompta.categorize.ml_fallback import ModeleMlCorrompu, charger_modele, verifier_empreinte
from axelcompta.categorize.modele_requis import (
    MESSAGE_ABSENT,
    MESSAGE_CORROMPU,
    SynchroSansModele,
    charger,
    modele_pour_synchro,
)


def test_sans_modele_la_synchro_refuse_de_tourner(tmp_path: Path) -> None:
    with pytest.raises(SynchroSansModele, match="synchro arrêtée"):
        modele_pour_synchro(tmp_path / "absent.joblib", environ={})


def test_le_repli_sur_les_regles_doit_etre_demande(tmp_path: Path) -> None:
    absent = tmp_path / "absent.joblib"
    assert modele_pour_synchro(absent, environ={"AXELCOMPTA_SANS_MODELE": "1"}) is None
    with pytest.raises(SynchroSansModele):
        modele_pour_synchro(absent, environ={"AXELCOMPTA_SANS_MODELE": "oui"})


def test_l_etat_dit_pourquoi_la_categorisation_est_degradee(tmp_path: Path) -> None:
    etat = charger(tmp_path / "tfidf_logreg_v2.joblib").etat
    assert (etat.modele_charge, etat.fichier, etat.raison) == (
        False,
        "tfidf_logreg_v2.joblib",
        MESSAGE_ABSENT,
    )


def _modele(tmp_path: Path) -> Path:
    chemin = tmp_path / "modele.joblib"
    chemin.write_bytes(pickle.dumps({"factice": True}))
    return chemin


def test_une_empreinte_differente_refuse_le_modele(tmp_path: Path) -> None:
    chemin = _modele(tmp_path)
    (tmp_path / "modele.joblib.sha256").write_text("0" * 64 + "  modele.joblib\n")
    with pytest.raises(ModeleMlCorrompu):
        charger_modele(chemin)
    assert charger(chemin).etat.raison == MESSAGE_CORROMPU


def test_une_empreinte_juste_ou_absente_laisse_passer(tmp_path: Path) -> None:
    chemin = _modele(tmp_path)
    verifier_empreinte(chemin)  # pas d'empreinte : modèle d'avant AXE-825
    empreinte = hashlib.sha256(chemin.read_bytes()).hexdigest()
    (tmp_path / "modele.joblib.sha256").write_text(f"{empreinte}  modele.joblib\n")
    verifier_empreinte(chemin)
