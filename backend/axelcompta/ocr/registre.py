"""Les catégories que l'OCR sait lire, toutes sections réunies (AXE-943)."""

from __future__ import annotations

from .banque import BANQUE
from .categories import Categorie
from .documents import CLASSEMENT, DOCUMENTS
from .plateformes import PLATEFORMES_OCR
from .reprise import REPRISE

REGISTRE: dict[str, Categorie] = {**DOCUMENTS, **REPRISE, **BANQUE, **PLATEFORMES_OCR}


def categorie_ocr(cle: str) -> Categorie | None:
    """La lecture d'une catégorie ; « autre » se classe d'abord."""
    return CLASSEMENT if cle == "autre" else REGISTRE.get(cle)
