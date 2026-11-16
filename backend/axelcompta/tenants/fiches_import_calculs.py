"""Ce qui se déduit d'une fiche d'import sans le demander (AXE-947). Pur.

* **Exercices** : de la date de création, de la date de clôture (« 31/12 »)
  et, si on la connaît, de la date de première clôture.
* **Exercice en cours** : celui qui contient aujourd'hui.
* **N° de TVA intracommunautaire** : il se calcule depuis le SIREN
  (FR + clé + SIREN, clé = (12 + 3 × (SIREN mod 97)) mod 97). Ni l'INSEE ni
  le RNE ne le donnent.

Une valeur déduite remplace la précédente déduction quand ses données
changent ; elle ne remplace jamais une saisie.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from datetime import date, timedelta

EXERCICES_MAX = 40  # garde-fou : une date de création absurde ne boucle pas


def _cloture_dans(annee: int, jour: int, mois: int) -> date:
    return date(annee, mois, min(jour, calendar.monthrange(annee, mois)[1]))


def bornes(champs: Mapping[str, str], aujourd_hui: date) -> list[tuple[date, date]]:
    """(début, fin) de chaque exercice, de la création à l'exercice en cours."""
    try:
        creation = date.fromisoformat(champs["date_creation"])
        jour, mois = (int(x) for x in champs["cloture"].split("/"))
        premiere = champs.get("premiere_cloture")
        fin = date.fromisoformat(premiere) if premiere else _cloture_dans(creation.year, jour, mois)
    except (KeyError, ValueError):
        return []
    if fin <= creation:
        fin = _cloture_dans(fin.year + 1, jour, mois)
    resultat = [(creation, fin)]
    while fin < aujourd_hui and len(resultat) < EXERCICES_MAX:
        debut, fin = fin + timedelta(days=1), _cloture_dans(fin.year + 1, jour, mois)
        resultat.append((debut, fin))
    return resultat


def numero_tva(siren: str) -> str | None:
    if len(siren) != 9 or not siren.isdigit():
        return None
    return f"FR{(12 + 3 * (int(siren) % 97)) % 97:02d}{siren}"


def deductions(champs: Mapping[str, str], aujourd_hui: date) -> dict[str, str]:
    """Les valeurs déduites des autres champs ; rien pour ce qui ne se
    déduit pas encore."""
    valeurs: dict[str, str] = {}
    tva = numero_tva(champs.get("siren", ""))
    if tva:
        valeurs["numero_tva"] = tva
    exercices = bornes(champs, aujourd_hui)
    if exercices:
        debut, fin = exercices[-1]
        valeurs["exercice_debut"], valeurs["exercice_fin"] = debut.isoformat(), fin.isoformat()
    return valeurs


def appliquer_deductions(
    avant: Mapping[str, str], apres: Mapping[str, str], aujourd_hui: date
) -> dict[str, str]:
    """`apres`, complété : un champ vide, ou qui vaut encore la déduction
    faite avant ce changement, prend la nouvelle déduction."""
    anciennes = deductions(avant, aujourd_hui)
    champs = dict(apres)
    for cle, valeur in deductions(apres, aujourd_hui).items():
        if not champs.get(cle) or champs[cle] == anciennes.get(cle):
            champs[cle] = valeur
    return champs
