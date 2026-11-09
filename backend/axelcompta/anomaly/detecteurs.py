"""Détecteurs V1 (doc 05 §6.2bis) : personnel, enseigne ambiguë, 3σ, doublon, double plein."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from .models import Alerte, MouvementSurveille
from .profil import cumuls_par_categorie, ecarte_du_profil

CATEGORIES_PERSONNELLES = frozenset({"usage_personnel_suspect"})
CATEGORIES_AMBIGUES = frozenset({"repas_et_receptions"})
CATEGORIE_CARBURANT = "carburant"
NATURE_COURSES = "courses"
NATURE_CARBURANT = "carburant"
# Double plein : signalé seulement s'il revient au moins ce nombre de jours
# dans le même mois (AXE-836 : deux pleins un jour donné n'ont rien d'anormal
# pour un chauffeur).
JOURS_DOUBLE_PLEIN_PAR_MOIS = 3
VIREMENT = "transfer"
# Un libellé « générique » ne contient que ces mots : pas d'enseigne.
_MOTS_GENERIQUES = frozenset(
    {
        "paiement",
        "achat",
        "depense",
        "dépense",
        "carburant",
        "gazole",
        "gasoil",
        "essence",
        "plein",
        "cb",
        "carte",
        "vir",
        "virement",
        "de",
        "du",
        "le",
        "la",
    }
)
_MOT = re.compile(r"[a-zéèàç]+")


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
        moyen_paiement=mouvement.moyen_paiement,
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


def _carburant_sortant(mouvement: MouvementSurveille) -> bool:
    return _sortie(mouvement) and mouvement.categorie == CATEGORIE_CARBURANT


def detecter_petit_carburant(
    mouvements: tuple[MouvementSurveille, ...], plancher_cts: int | None
) -> tuple[Alerte, ...]:
    """Carburant sous le plancher du pack (AXE-836/837) : café ou boutique de
    station, ou montant faux. Signalé, jamais reclassé."""
    if plancher_cts is None:
        return ()
    return tuple(
        _alerte(
            m, "carburant_petit_montant", "dépense à vérifier", "Montant trop faible pour un plein."
        )
        for m in mouvements
        if _carburant_sortant(m) and -m.montant_centimes < plancher_cts
    )


def libelle_generique(libelle: str) -> bool:
    mots = _MOT.findall(libelle.lower())
    return bool(mots) and all(mot in _MOTS_GENERIQUES for mot in mots)


def detecter_libelle_generique(mouvements: tuple[MouvementSurveille, ...]) -> tuple[Alerte, ...]:
    """Carburant sans enseigne (« Paiement carburant ») : surtout suspect
    payé par virement, l'argent peut partir vers un autre compte."""
    return tuple(
        _alerte(
            m,
            "carburant_libelle_generique",
            "dépense à vérifier",
            "Libellé sans enseigne."
            + (
                " Payé par virement : vérifier le destinataire."
                if m.moyen_paiement == VIREMENT
                else ""
            ),
        )
        for m in mouvements
        if _carburant_sortant(m) and libelle_generique(m.libelle)
    )


def detecter_double_plein(
    mouvements: tuple[MouvementSurveille, ...], plancher_cts: int | None = None
) -> tuple[Alerte, ...]:
    """Deux pleins (au-dessus du plancher) le même jour, **et** au moins
    `JOURS_DOUBLE_PLEIN_PAR_MOIS` jours ainsi dans le mois."""
    pleins = tuple(
        m for m in mouvements if plancher_cts is None or -m.montant_centimes >= plancher_cts
    )
    jours_doubles = [g for g in _grouper(pleins, "plein").values() if len(g) >= 2]
    par_mois: dict[tuple[str, int, int], list[list[MouvementSurveille]]] = defaultdict(list)
    for groupe in jours_doubles:
        premier = groupe[0]
        par_mois[(premier.dossier_id, premier.date.year, premier.date.month)].append(groupe)
    alertes: list[Alerte] = []
    for groupes in par_mois.values():
        if len(groupes) < JOURS_DOUBLE_PLEIN_PAR_MOIS:
            continue
        detail = f"Deux pleins le même jour, {len(groupes)} jours ce mois-ci."
        alertes.extend(
            _alerte(m, "double_plein", "dépense atypique", detail) for g in groupes for m in g
        )
    return tuple(alertes)
