"""Détecteurs V1 (doc 05 §6.2bis) : personnel, enseigne ambiguë, 3σ, doublon, double plein."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from .models import Alerte, MouvementSurveille
from .profil import cumuls_par_categorie, ecarte_du_profil

CATEGORIES_PERSONNELLES = frozenset({"usage_personnel_suspect"})
CATEGORIES_AMBIGUES = frozenset({"repas_et_receptions"})
CATEGORIE_CARBURANT = "carburant"
NATURE_COURSES = "courses"
NATURE_CARBURANT = "carburant"


def _alerte(mouvement: MouvementSurveille, code: str, libelle_ui: str, detail: str) -> Alerte:
    return Alerte(
        id=f"{code}:{mouvement.ecriture_id}",
        dossier_id=mouvement.dossier_id,
        ecriture_id=mouvement.ecriture_id,
        code=code,
        libelle_ui=libelle_ui,
        detail=detail,
        libelle_mouvement=mouvement.libelle,
        montant_centimes=mouvement.montant_centimes,
        date=mouvement.date,
    )


def _sortie(mouvement: MouvementSurveille) -> bool:
    return mouvement.montant_centimes < 0


def detecter_personnel(
    mouvements: tuple[MouvementSurveille, ...],
    categories: frozenset[str] = CATEGORIES_PERSONNELLES,
) -> tuple[Alerte, ...]:
    return tuple(
        _alerte(
            mouvement, "personnel", "usage personnel possible", f"Catégorie {mouvement.categorie}."
        )
        for mouvement in mouvements
        if _sortie(mouvement) and mouvement.categorie in categories
    )


def _enseigne_a_signaler(mouvement: MouvementSurveille, categories: frozenset[str]) -> bool:
    if not _sortie(mouvement) or mouvement.categorie not in categories:
        return False
    if mouvement.justificatif_id is None:
        return True
    if mouvement.nature_ticket == NATURE_CARBURANT:
        return False
    return mouvement.nature_ticket == NATURE_COURSES


def _detail_enseigne(mouvement: MouvementSurveille) -> str:
    if mouvement.justificatif_id is None:
        return "Enseigne ambiguë, sans ticket."
    return "Le ticket liste des courses."


def detecter_enseigne_ambigue(
    mouvements: tuple[MouvementSurveille, ...],
    categories: frozenset[str] = CATEGORIES_AMBIGUES,
) -> tuple[Alerte, ...]:
    return tuple(
        _alerte(mouvement, "enseigne_ambigue", "dépense à justifier", _detail_enseigne(mouvement))
        for mouvement in mouvements
        if _enseigne_a_signaler(mouvement, categories)
    )


def detecter_ecart_profil(mouvements: tuple[MouvementSurveille, ...]) -> tuple[Alerte, ...]:
    groupes = cumuls_par_categorie(mouvements)
    alertes: list[Alerte] = []
    for mouvement in mouvements:
        if not _sortie(mouvement):
            continue
        cumul = groupes.get((mouvement.dossier_id, mouvement.categorie))
        if cumul is not None and ecarte_du_profil(cumul, -mouvement.montant_centimes):
            alertes.append(
                _alerte(
                    mouvement,
                    "ecart_profil",
                    "dépense atypique",
                    "Au-delà de l'habitude de ce dossier.",
                )
            )
    return tuple(alertes)


def _grouper(
    mouvements: tuple[MouvementSurveille, ...], cle: str
) -> dict[tuple[str, str | date], list[MouvementSurveille]]:
    groupes: dict[tuple[str, str | date], list[MouvementSurveille]] = defaultdict(list)
    for mouvement in mouvements:
        if cle == "justificatif" and mouvement.justificatif_id:
            groupes[(mouvement.dossier_id, mouvement.justificatif_id)].append(mouvement)
        elif cle == "plein" and _sortie(mouvement) and mouvement.categorie == CATEGORIE_CARBURANT:
            groupes[(mouvement.dossier_id, mouvement.date)].append(mouvement)
    return groupes


def _alertes_groupees(
    groupes: dict[tuple[str, str | date], list[MouvementSurveille]],
    code: str,
    libelle_ui: str,
    detail: str,
) -> tuple[Alerte, ...]:
    alertes: list[Alerte] = []
    for groupe in groupes.values():
        if len(groupe) < 2:
            continue
        alertes.extend(_alerte(mouvement, code, libelle_ui, detail) for mouvement in groupe)
    return tuple(alertes)


def detecter_doublons(mouvements: tuple[MouvementSurveille, ...]) -> tuple[Alerte, ...]:
    return _alertes_groupees(
        _grouper(mouvements, "justificatif"),
        "doublon_piece",
        "dépense à justifier",
        "Le même justificatif est posé sur plusieurs dépenses.",
    )


def detecter_double_plein(mouvements: tuple[MouvementSurveille, ...]) -> tuple[Alerte, ...]:
    return _alertes_groupees(
        _grouper(mouvements, "plein"),
        "double_plein",
        "dépense atypique",
        "Deux pleins le même jour.",
    )
