"""Un document mal rangé, vu par l'OCR (AXE-995). Pur.

Chaque lecture dit ce que le document est vraiment (`nature_constatee`).
Quand ce n'est pas sa catégorie, le passage le relit dans la catégorie
constatée :

* si cette lecture passe **ses contrôles**, le document change de catégorie
  tout seul (« Reclassé par l'OCR : était Liasse ») ; la confiance annoncée
  par le modèle ne suffit pas, il faut que le document tienne dans sa
  nouvelle catégorie ;
* sinon, il ne bouge pas et l'écran propose de le ranger ailleurs en un clic.

Un document rangé à la main (« Ranger dans ») n'est jamais déplacé d'office :
la proposition seule s'affiche, sans relecture.
"""

from __future__ import annotations

from collections.abc import Mapping

from axelcompta.tenants.fiches_import import CATEGORIES_DOCUMENTS, DocumentImport

from .categories import NATURE_CONSTATEE
from .lecture import Lecture

RANGE_PAR = "range_par"  # « humain » : rangé par « Ranger dans »
PROPOSITION = "proposition_ocr"
RECLASSEMENT = "ocr_reclassement"


def nature_differente(
    categorie: str, lecture: Lecture, connues: Mapping[str, object]
) -> str | None:
    """La catégorie constatée par la lecture, si elle diffère de celle du
    document et que l'OCR sait la lire ; `None` sinon."""
    nature = (lecture.lu or {}).get(NATURE_CONSTATEE)
    if not isinstance(nature, str) or nature in ("", "autre", categorie):
        return None
    return nature if nature in connues else None


def range_a_la_main(document: DocumentImport) -> bool:
    return (document.donnees or {}).get(RANGE_PAR) == "humain"


def libelle(categorie: str) -> str:
    return CATEGORIES_DOCUMENTS.get(categorie, categorie)


def proposition(donnees: Mapping[str, object] | None) -> str | None:
    """La catégorie que l'OCR propose pour ce document, s'il en propose une."""
    valeur = (donnees or {}).get(PROPOSITION)
    return valeur if isinstance(valeur, str) and valeur in CATEGORIES_DOCUMENTS else None


def phrase_proposition(categorie: str) -> str:
    return f"Ce document semble être : {libelle(categorie)}."
