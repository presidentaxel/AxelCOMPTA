"""Chaque détecteur V1 a son cas, et le vocabulaire reste non juridique."""

from __future__ import annotations

import dataclasses
from datetime import date

from axelcompta.anomaly.detecteurs import libelle_generique
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


def test_deux_pleins_un_seul_jour_ne_sont_pas_signales() -> None:
    """AXE-836 : pour un chauffeur, deux pleins un jour donné n'ont rien
    d'anormal ; c'est la répétition qui l'est."""
    matin = _mouvement("matin", jour=3)
    soir = _mouvement("soir", jour=3)
    assert not {code for _, code in _codes((matin, soir))} & {"double_plein"}


def test_deux_pleins_le_meme_jour_trois_jours_du_mois_sont_signales() -> None:
    mouvements = tuple(
        _mouvement(f"{moment}{jour}", jour=jour) for jour in (3, 10, 17) for moment in ("m", "s")
    ) + (_mouvement("seul", jour=4),)
    codes = _codes(mouvements)
    assert {("m3", "double_plein"), ("s17", "double_plein")} <= codes
    assert ("seul", "double_plein") not in codes
    detail = next(a.detail for a in analyser(mouvements) if a.code == "double_plein")
    assert detail == "Deux pleins le même jour, 3 jours ce mois-ci."


def test_le_double_plein_ignore_les_petits_montants() -> None:
    """Un café à 1,50 € le même jour qu'un plein n'en fait pas deux."""
    mouvements = tuple(
        m
        for jour in (3, 10, 17)
        for m in (
            _mouvement(f"p{jour}", jour=jour),
            _mouvement(f"c{jour}", montant=-150, jour=jour),
        )
    )
    codes = {a.code for a in analyser(mouvements, plancher_carburant_cts=500)}
    assert "double_plein" not in codes


def test_un_petit_montant_carburant_est_signale() -> None:
    alertes = analyser(
        (_mouvement("cafe", montant=-150), _mouvement("plein", montant=-6_000)),
        plancher_carburant_cts=500,
    )
    assert [(a.ecriture_id, a.detail) for a in alertes if a.code == "carburant_petit_montant"] == [
        ("cafe", "Montant trop faible pour un plein.")
    ]
    assert not [
        a
        for a in analyser((_mouvement("cafe", montant=-150),))
        if a.code == "carburant_petit_montant"
    ]


def test_un_libelle_sans_enseigne_est_signale_surtout_par_virement() -> None:
    generique = MouvementSurveille(
        dossier_id=DossierId("d1"),
        ecriture_id=EcritureId("g"),
        date=date(2026, 9, 1),
        libelle="Paiement carburant",
        montant_centimes=-100,
        categorie="carburant",
        moyen_paiement="transfer",
    )
    marque = dataclasses.replace(
        generique, ecriture_id=EcritureId("t"), libelle="CB TOTAL ACCESS A6"
    )
    alertes = [a for a in analyser((generique, marque)) if a.code == "carburant_libelle_generique"]
    assert [(a.ecriture_id, a.moyen_paiement) for a in alertes] == [("g", "transfer")]
    assert "vérifier le destinataire" in alertes[0].detail
    assert libelle_generique("GAZOLE") and not libelle_generique("ESSO EXPRESS")
    # Tel qu'écrit par la synchro : la catégorie entre parenthèses ne compte pas.
    assert libelle_generique("Paiement carburant (carburant)")
    assert not libelle_generique("CB TOTAL ACCESS A6 (carburant)")
