"""Un humain corrige ou valide une lecture que l'OCR n'a pas pu valider (AXE-991). Pur.

La lecture corrigée repasse les contrôles de sa catégorie. S'ils passent, le
document devient « traité » comme une lecture acceptée. Sinon, il ne passe
qu'avec une raison écrite. Dans les deux cas, on garde qui, quand, la raison
et la lecture d'origine de l'OCR.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from axelcompta.core.errors import SaisieInvalide
from axelcompta.tenants.fiches_import import DocumentImport

from .categories import Contexte
from .registre import REGISTRE


class LectureRefusee(SaisieInvalide):
    """Les contrôles échouent et aucune raison n'est donnée."""


def valider_lecture(
    document: DocumentImport,
    lu: Mapping[str, object],
    ctx: Contexte,
    raison: str,
    par: str,
    maintenant: datetime,
) -> DocumentImport:
    categorie = REGISTRE.get(document.categorie)
    if categorie is None or document.statut_traitement != "a_traiter":
        raise SaisieInvalide("Ce document n'attend pas de validation.")
    # Seuls les champs du schéma de la catégorie sont gardés (frontière de confiance).
    attendus = categorie.schema()["properties"]
    lecture = categorie.corriger({k: v for k, v in lu.items() if k in attendus})
    erreurs = categorie.controler(lecture, ctx)
    raison = raison.strip()
    if erreurs and not raison:
        raise LectureRefusee(
            " ".join(erreurs) + " Corrigez la lecture, ou validez avec une raison."
        )
    donnees = dict(document.donnees or {})
    origine = donnees.get("lu")
    ocr = donnees.get("ocr")
    if isinstance(ocr, dict):
        donnees["ocr"] = {**ocr, "a_verifier": False}
    donnees.update(categorie.donnees(lecture))
    donnees["lu"] = lecture
    donnees["validation"] = {
        "par": par,
        "le": maintenant.isoformat(timespec="seconds"),
        "raison": raison,
        "controles": erreurs,
        "lu_ocr": origine,
    }
    resume = categorie.resumer(lecture)
    suffixe = (
        f" Validé par {par} malgré les contrôles : {raison}" if erreurs else f" Validé par {par}."
    )
    return replace(document, statut_traitement="traite", resume=resume + suffixe, donnees=donnees)
