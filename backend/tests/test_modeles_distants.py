"""AXE-847 : le modèle de catégorisation vit dans un bucket privé, versionné,
avec son empreinte ; il se récupère sur un poste vide."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from axelcompta.categorize.ml_fallback import (
    ModeleMlCorrompu,
    chemin_modele,
    version_attendue,
)
from axelcompta.modeles_distants import (
    DepotS3,
    ModeleDistantIntrouvable,
    VersionDejaPubliee,
    a_publier,
    assurer_modele,
    depot_depuis_env,
    present_et_intact,
    publier,
    recuperer,
)

VERSION = "tfidf_logreg_v9"
CONTENU = b"modele-serialise"


class DepotMemoire:
    def __init__(self) -> None:
        self.objets: dict[str, bytes] = {}
        self.lectures: list[str] = []

    def lire(self, cle: str) -> bytes | None:
        self.lectures.append(cle)
        return self.objets.get(cle)

    def ecrire(self, cle: str, contenu: bytes) -> None:
        self.objets[cle] = contenu


def _empreinte(contenu: bytes) -> bytes:
    return f"{hashlib.sha256(contenu).hexdigest()}  {VERSION}.joblib\n".encode()


def _poste_avec_modele(dossier: Path, contenu: bytes = CONTENU) -> Path:
    """Ce qu'écrit `entrainer_modele.py` : modèle, empreinte, calibration."""
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"{VERSION}.joblib").write_bytes(contenu)
    (dossier / f"{VERSION}.joblib.sha256").write_bytes(_empreinte(contenu))
    (dossier / f"{VERSION}.calibration.json").write_text('{"seuil": 0.6}')
    return dossier


def _depot_publie(tmp_path: Path) -> DepotMemoire:
    source = _poste_avec_modele(tmp_path / "source")
    depot = DepotMemoire()
    publier(VERSION, depot, a_publier(VERSION, source))
    return depot


def test_la_version_attendue_est_un_reglage() -> None:
    assert version_attendue({}) == "tfidf_logreg_v2"
    assert version_attendue({"AXELCOMPTA_MODELE_VERSION": " tfidf_logreg_v3 "}) == "tfidf_logreg_v3"
    assert chemin_modele("x", Path("/m")) == Path("/m/x.joblib")


def test_publier_envoie_un_dossier_par_version_empreinte_en_dernier(tmp_path: Path) -> None:
    source = _poste_avec_modele(tmp_path / "source")
    rapport = tmp_path / "rapport.txt"
    rapport.write_text("ECE 0,03")
    depot = DepotMemoire()
    publier(VERSION, depot, a_publier(VERSION, source, rapport))
    assert set(depot.objets) == {
        f"{VERSION}/{VERSION}.joblib",
        f"{VERSION}/{VERSION}.joblib.sha256",
        f"{VERSION}/{VERSION}.calibration.json",
        f"{VERSION}/rapport.txt",
    }
    # Écrite en dernier : un envoi interrompu n'est jamais récupéré.
    assert list(depot.objets)[-1] == f"{VERSION}/{VERSION}.joblib.sha256"


def test_une_version_publiee_ne_se_remplace_pas(tmp_path: Path) -> None:
    depot = _depot_publie(tmp_path)
    with pytest.raises(VersionDejaPubliee):
        publier(VERSION, depot, a_publier(VERSION, tmp_path / "source"))


def test_on_ne_publie_pas_un_modele_sans_empreinte_ou_altere(tmp_path: Path) -> None:
    dossier = _poste_avec_modele(tmp_path / "source")
    (dossier / f"{VERSION}.joblib").write_bytes(b"autre chose")
    with pytest.raises(ModeleMlCorrompu):
        a_publier(VERSION, dossier)
    (dossier / f"{VERSION}.joblib.sha256").unlink()
    with pytest.raises(ModeleDistantIntrouvable):
        a_publier(VERSION, dossier)


def test_sur_un_poste_vide_le_modele_est_recupere_et_verifie(tmp_path: Path) -> None:
    depot = _depot_publie(tmp_path)
    poste = tmp_path / "poste"
    assert recuperer(VERSION, depot, poste) is True
    assert (poste / f"{VERSION}.joblib").read_bytes() == CONTENU
    assert (poste / f"{VERSION}.calibration.json").is_file()
    assert present_et_intact(VERSION, poste)
    assert not list(poste.glob("*.partiel"))


def test_un_modele_deja_present_et_intact_ne_se_retelecharge_pas(tmp_path: Path) -> None:
    depot = _depot_publie(tmp_path)
    poste = _poste_avec_modele(tmp_path / "poste")
    depot.lectures.clear()
    assert recuperer(VERSION, depot, poste) is False
    assert depot.lectures == []


def test_un_modele_local_altere_est_remplace_par_la_version_publiee(tmp_path: Path) -> None:
    depot = _depot_publie(tmp_path)
    poste = _poste_avec_modele(tmp_path / "poste")
    (poste / f"{VERSION}.joblib").write_bytes(b"abime")
    assert recuperer(VERSION, depot, poste) is True
    assert (poste / f"{VERSION}.joblib").read_bytes() == CONTENU


def test_un_telechargement_altere_n_est_jamais_ecrit(tmp_path: Path) -> None:
    depot = _depot_publie(tmp_path)
    depot.objets[f"{VERSION}/{VERSION}.joblib"] = b"altere en route"
    poste = tmp_path / "poste"
    with pytest.raises(ModeleMlCorrompu):
        recuperer(VERSION, depot, poste)
    assert not (poste / f"{VERSION}.joblib").exists()


def test_une_version_absente_ou_sans_empreinte_n_est_pas_recuperee(tmp_path: Path) -> None:
    depot = _depot_publie(tmp_path)
    with pytest.raises(ModeleDistantIntrouvable):
        recuperer("tfidf_logreg_v404", depot, tmp_path / "poste")
    del depot.objets[f"{VERSION}/{VERSION}.joblib.sha256"]
    with pytest.raises(ModeleDistantIntrouvable):
        recuperer(VERSION, depot, tmp_path / "poste")


def test_sans_stockage_configure_rien_n_est_tente(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert depot_depuis_env({}) is None
    assurer_modele({"AXELCOMPTA_MODELE_VERSION": VERSION}, tmp_path)
    assert "stockage S3 non configuré" in capsys.readouterr().err


def test_au_demarrage_une_erreur_de_stockage_est_signalee_sans_lever(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "axelcompta.modeles_distants.depot_depuis_env", lambda environ=None: DepotMemoire()
    )
    assurer_modele({"AXELCOMPTA_MODELE_VERSION": VERSION}, tmp_path)
    assert "non récupéré du stockage" in capsys.readouterr().err


class _ClientS3Factice:
    """Ce que `DepotS3` attend de boto3 : get_object, put_object, NoSuchKey."""

    class exceptions:  # noqa: N801 — même forme que boto3
        class NoSuchKey(Exception):
            pass

    def __init__(self) -> None:
        self.objets: dict[tuple[str, str], bytes] = {}

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if (Bucket, Key) not in self.objets:
            raise self.exceptions.NoSuchKey()
        contenu = self.objets[(Bucket, Key)]

        class _Corps:
            def read(self) -> bytes:
                return contenu

        return {"Body": _Corps()}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803
        self.objets[(Bucket, Key)] = Body


def test_le_depot_s3_lit_ecrit_et_dit_absent() -> None:
    client = _ClientS3Factice()
    depot = DepotS3(client, "modeles")
    assert depot.lire("v/x") is None
    depot.ecrire("v/x", b"abc")
    assert depot.lire("v/x") == b"abc"
    assert ("modeles", "v/x") in client.objets
