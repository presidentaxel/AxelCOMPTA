"""Lire un document : Haiku, puis Sonnet si un contrôle échoue, puis un
humain (AXE-943). Pur : l'appel au modèle est injecté.

Haiku lit presque tout juste pour une fraction de centime par page, mais
peut inventer un montant ; les contrôles de la catégorie le voient, et
Sonnet relit. Si Sonnet échoue aussi, le document reste « à lire » avec la
raison, en rouge à l'écran : un humain tranche.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

from .categories import Categorie, Contexte

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
MODELES = (HAIKU, SONNET)
# Change quand une consigne ou un schéma change : les lectures d'une version
# précédente restent, mais un document « à vérifier » peut être relu.
VERSION = "ocr-2"  # 19/11 : TVA sans période, signe des soldes, actif net (AXE-996, 997, 1000)
A_VERIFIER = "À vérifier par un humain"


@dataclass(frozen=True, slots=True)
class Appel:
    lu: dict[str, object] | None
    cout_usd: float = 0.0
    erreur: str = ""  # refus, réponse coupée, API indisponible


Appeler = Callable[[str, Categorie, bytes, str], Appel]


@dataclass(frozen=True, slots=True)
class Lecture:
    modele: str
    lu: dict[str, object] | None
    echecs: tuple[str, ...]
    cout_usd: float
    essais: tuple[dict[str, object], ...] = field(default_factory=tuple)

    @property
    def acceptee(self) -> bool:
        return self.lu is not None and not self.echecs


def lire(
    categorie: Categorie, contenu: bytes, media_type: str, ctx: Contexte, appeler: Appeler
) -> Lecture:
    """Haiku, puis Sonnet si Haiku n'est pas accepté."""
    essais: list[dict[str, object]] = []
    cout = 0.0
    derniere = Lecture(HAIKU, None, ("Pas lu.",), 0.0)
    for modele in MODELES:
        appel = appeler(modele, categorie, contenu, media_type)
        cout += appel.cout_usd
        lu = None if appel.lu is None else categorie.corriger(appel.lu)
        echecs = [appel.erreur] if lu is None else categorie.controler(lu, ctx)
        essais.append({"modele": modele, "echecs": echecs})
        derniere = Lecture(modele, lu, tuple(echecs), cout, tuple(essais))
        if derniere.acceptee:
            break
    return derniere


def meta(lecture: Lecture, maintenant: datetime) -> dict[str, object]:
    """Ce que le document garde de sa lecture, sous `donnees["ocr"]`."""
    return {
        "version": VERSION,
        "modele": lecture.modele,
        "le": maintenant.isoformat(timespec="seconds"),
        "cout_usd": round(lecture.cout_usd, 6),
        "a_verifier": not lecture.acceptee,
        "controles": list(lecture.echecs),
        "essais": list(lecture.essais),
    }


def traitement(
    categorie: Categorie,
    lecture: Lecture,
    anciennes: Mapping[str, object] | None,
    maintenant: datetime,
) -> tuple[str, str, dict[str, object]]:
    """(statut, résumé, données) du document après sa lecture."""
    donnees: dict[str, object] = dict(anciennes or {})
    donnees["ocr"] = meta(lecture, maintenant)
    donnees["lu"] = lecture.lu or {}
    if lecture.acceptee and lecture.lu is not None:
        donnees.update(categorie.donnees(lecture.lu))
        return "traite", categorie.resumer(lecture.lu), donnees
    raisons = " ; ".join(lecture.echecs) or "lecture incomplète"
    return "a_traiter", f"{A_VERIFIER} : {raisons}", donnees


def a_verifier(donnees: Mapping[str, object] | None) -> tuple[bool, list[str]]:
    """Pour l'écran : le document attend-il un humain, et pourquoi (sa
    lecture, ou son classement s'il était en « Autre »)."""
    for cle in ("ocr", "ocr_classement"):
        lecture = (donnees or {}).get(cle)
        if isinstance(lecture, dict) and lecture.get("a_verifier"):
            controles = lecture.get("controles")
            return True, [str(c) for c in controles] if isinstance(controles, list) else []
    return False, []
