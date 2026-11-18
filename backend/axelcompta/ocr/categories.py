"""Ce que l'OCR lit dans chaque catégorie de document (AXE-943). Pur.

Une catégorie donne au modèle une consigne et un schéma JSON imposé, puis
contrôle ce qu'il a rendu et en fait un résumé pour l'écran. Le schéma n'a
pas de champ « texte ou null » (l'API en limite le nombre) : un texte absent
vaut "", un montant absent n'est pas listé.

Les catégories de chaque section de la fiche sont dans leur module
(`ocr/documents.py`, …) et réunies dans `REGISTRE`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

CONSIGNE_COMMUNE = """Tu lis un document d'une petite société française (souvent un chauffeur VTC).
Rends uniquement ce qui est écrit dans le document : un texte absent vaut "", un montant absent
n'est pas listé. Ne devine jamais, ne calcule pas un montant qui n'est pas imprimé.
Montants en centimes entiers : 1 234,56 € -> 123456 ; un montant imprimé en euros entiers, 7 008 €
-> 700800. Une perte, un solde créditeur ou un crédit sont négatifs ; des frais, un impôt, une TVA
due sont positifs.
Dates au format AAAA-MM-JJ. SIREN : 9 chiffres sans espace (les 9 premiers chiffres d'un SIRET)."""


@dataclass(frozen=True, slots=True)
class Contexte:
    """Ce que la fiche sait déjà, pour recouper une lecture."""

    siren: str | None = None
    exercice: int | None = None
    # Le FEC lu du même exercice (`donnees` d'AXE-970) : résultat, soldes.
    fec: Mapping[str, object] | None = None
    # Les champs de la fiche, pour les préremplissages.
    champs: Mapping[str, str] = field(default_factory=dict)


Controle = Callable[[Mapping[str, object], Contexte], list[str]]
Resume = Callable[[Mapping[str, object]], str]


@dataclass(frozen=True, slots=True)
class Categorie:
    cle: str
    consigne: str
    textes: tuple[str, ...] = ()
    montants: tuple[str, ...] = ()
    # Une liste d'objets : nom -> {champ: "string" | "integer"}.
    listes: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    controler: Controle = lambda _lu, _ctx: []
    resumer: Resume = lambda _lu: "Lu par l'OCR."
    # Ce que la fiche garde du document, au-delà de la lecture brute
    # (`donnees` d'un document : un récapitulatif devient `recap_plateforme`).
    donnees: Callable[[Mapping[str, object]], dict[str, object]] = lambda _lu: {}
    max_tokens: int = 8_000

    def schema(self) -> dict[str, Any]:
        return schema(self.textes, self.montants, self.listes)

    def consigne_complete(self) -> str:
        return f"{CONSIGNE_COMMUNE}\n\n{self.consigne}"


def schema(
    textes: tuple[str, ...],
    montants: tuple[str, ...] = (),
    listes: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Un objet strict : chaque texte, la liste des montants présents, et
    les listes d'objets demandées."""
    proprietes: dict[str, Any] = {t: {"type": "string"} for t in textes}
    if montants:
        proprietes["montants"] = {
            "type": "array",
            "items": _objet(
                {
                    "nom": {"type": "string", "enum": list(montants)},
                    "valeur_cts": {"type": "integer"},
                }
            ),
        }
    for nom, champs in (listes or {}).items():
        proprietes[nom] = {
            "type": "array",
            "items": _objet({c: {"type": t} for c, t in champs.items()}),
        }
    return _objet(proprietes)


def _objet(proprietes: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(proprietes),
        "properties": proprietes,
    }
