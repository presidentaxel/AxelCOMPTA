"""Sérialisation JSON des fiches officielles et des écarts (AXE-849)."""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any

from axelcompta.core.identite import Adresse

from .models import EcartRegistre
from .registres import FicheOfficielle


def ecarts_vers_json(ecarts: tuple[EcartRegistre, ...]) -> list[dict[str, str]]:
    return [dataclasses.asdict(e) for e in ecarts]


def ecarts_depuis_json(donnees: Any) -> tuple[EcartRegistre, ...]:
    if not isinstance(donnees, list):
        return ()
    return tuple(EcartRegistre(**e) for e in donnees if isinstance(e, dict))


def fiche_vers_json(fiche: FicheOfficielle) -> dict[str, Any]:
    donnees = dataclasses.asdict(fiche)
    donnees["lu_le"] = fiche.lu_le.isoformat()
    donnees["date_creation"] = fiche.date_creation.isoformat() if fiche.date_creation else None
    return donnees


def fiche_depuis_json(donnees: dict[str, Any]) -> FicheOfficielle:
    siege = donnees.get("siege")
    creation = donnees.get("date_creation")
    return FicheOfficielle(
        **{
            **donnees,
            "lu_le": date.fromisoformat(donnees["lu_le"]),
            "sources": tuple(donnees.get("sources") or ()),
            "dirigeants": tuple(donnees.get("dirigeants") or ()),
            "siege": Adresse(**siege) if isinstance(siege, dict) else None,
            "date_creation": date.fromisoformat(creation) if creation else None,
        }
    )
