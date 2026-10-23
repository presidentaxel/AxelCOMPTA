"""Chaque détecteur V1 a son cas, et le vocabulaire reste non juridique."""

from __future__ import annotations

from datetime import date

from axelcompta.anomaly.models import MouvementSurveille
from axelcompta.anomaly.service import analyser
from axelcompta.core.ids import DossierId, EcritureId

DOSSIER = DossierId("d1")


def _mouvement(
    identifiant: str,
    *,
    categorie: str = "carburant",
    montant: int = -5_000,
    jour: int = 1,
    justificatif: str | None = None,
    nature: str | None = None,
    dossier: str = "d1",
) -> MouvementSurveille:
    return MouvementSurveille(
        dossier_id=DossierId(dossier),
        ecriture_id=EcritureId(identifiant),
        date=date(2026, 9, jour),
        libelle=identifiant,
        montant_centimes=montant,
        categorie=categorie,
        justificatif_id=justificatif,
        nature_ticket=nature,
    )


def _codes(mouvements: tuple[MouvementSurveille, ...]) -> set[tuple[str, str]]:
    return {(alerte.ecriture_id, alerte.code) for alerte in analyser(mouvements)}


def test_une_categorie_personnelle_est_a_qualifier() -> None:
    codes = _codes((_mouvement("zara", categorie="usage_personnel_suspect"),))
    assert codes == {("zara", "personnel")}
    libelle = analyser((_mouvement("zara", categorie="usage_personnel_suspect"),))[0].libelle_ui
    assert "abus" not in libelle


def test_une_entree_personnelle_n_est_pas_une_alerte() -> None:
    assert (
        _codes((_mouvement("zara", categorie="usage_personnel_suspect", montant=5_000),)) == set()
    )


def test_enseigne_ambigue_sans_ticket_ou_courses() -> None:
    sans = _mouvement("auchan", categorie="repas_et_receptions")
    courses = _mouvement(
        "auchan-2", categorie="repas_et_receptions", justificatif="t", nature="courses"
    )
    carburant = _mouvement(
        "auchan-3", categorie="repas_et_receptions", justificatif="t2", nature="carburant"
    )
    photo_seule = _mouvement("auchan-4", categorie="repas_et_receptions", justificatif="t3")
    codes = _codes((sans, courses, carburant, photo_seule))
    assert ("auchan", "enseigne_ambigue") in codes
    assert ("auchan-2", "enseigne_ambigue") in codes
    assert ("auchan-3", "enseigne_ambigue") not in codes
    assert ("auchan-4", "enseigne_ambigue") not in codes


def test_ecart_a_une_habitude_constante() -> None:
    habituels = tuple(_mouvement(f"h{i}", montant=-1_000, jour=i) for i in range(1, 7))
    gros = _mouvement("gros", montant=-100_000, jour=7)
    codes = _codes(habituels + (gros,))
    assert ("gros", "ecart_profil") in codes
    assert all(code != "ecart_profil" for _, code in codes if _ != "gros")


def test_pas_d_ecart_sans_assez_d_historique() -> None:
    habituels = tuple(_mouvement(f"h{i}", montant=-1_000, jour=i) for i in range(1, 4))
    gros = _mouvement("gros", montant=-100_000, jour=4)
    assert ("gros", "ecart_profil") not in _codes(habituels + (gros,))


def test_un_autre_dossier_ne_sert_pas_de_profil() -> None:
    habituels = tuple(_mouvement(f"h{i}", montant=-1_000, jour=i) for i in range(1, 7))
    autre = _mouvement("seul", montant=-100_000, dossier="d2")
    assert ("seul", "ecart_profil") not in _codes(habituels + (autre,))


def test_le_meme_justificatif_sur_deux_depenses() -> None:
    premier = _mouvement("a", justificatif="piece-1")
    second = _mouvement("b", justificatif="piece-1", jour=2)
    seul = _mouvement("c", justificatif="piece-2", jour=3)
    codes = _codes((premier, second, seul))
    assert {("a", "doublon_piece"), ("b", "doublon_piece")} <= codes
    assert ("c", "doublon_piece") not in codes


def test_deux_pleins_le_meme_jour() -> None:
    matin = _mouvement("matin", categorie="carburant", jour=3)
    soir = _mouvement("soir", categorie="carburant", jour=3)
    lendemain = _mouvement("demain", categorie="carburant", jour=4)
    codes = _codes((matin, soir, lendemain))
    assert {("matin", "double_plein"), ("soir", "double_plein")} <= codes
    assert ("demain", "double_plein") not in codes
