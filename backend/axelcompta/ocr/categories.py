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


# Ce qu'un document peut être : pour ranger un « Autre », ou voir qu'un
# document est mal rangé (AXE-995). « autre » : rien de tout cela.
NATURES = (
    "liasse",
    "comptes_annuels",
    "balance",
    "grand_livre",
    "declaration_tva",
    "declaration_is",
    "accuse_reception",
    "paiement_impot",
    "piece",
    "emprunt",
    "releve_bancaire",
    "rib",
    "releve_plateforme",
    "kbis",
    "statuts",
    "lettre_comptable",
    "autre",
)
NATURE_CONSTATEE = "nature_constatee"
DESCRIPTION_NATURES = """liasse (liasse fiscale 2033, 2050, 2065, 2031, ou leur synthèse, avec
  ses montants), comptes_annuels (bilan et compte de résultat), balance, grand_livre,
  declaration_tva (CA3, CA12, 3517, ou un récapitulatif de leurs montants), declaration_is (2571,
  2572, relevé d'acompte ou de solde), accuse_reception (accusé de dépôt d'une déclaration, y
  compris un accusé de télétransmission ou de télédéclaration EDI, sans les montants),
  paiement_impot (ordre ou avis de paiement d'un impôt ; pas un mandat de prélèvement SEPA), piece
  (facture, reçu, ticket, note de frais), emprunt (tableau d'amortissement, échéancier de prêt),
  releve_bancaire (relevé de compte), rib, releve_plateforme (récapitulatif ou relevé Uber, Bolt,
  Heetch, Free Now…), kbis, statuts, lettre_comptable (courrier de l'ancien expert-comptable ; pas
  un courrier de banque), autre (tout le reste : tarifs ou conditions d'une banque, mandat SEPA,
  contrat, courrier commercial…)"""

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
    # Une correction sûre avant les contrôles : un signe que l'arithmétique
    # du document prouve (un solde débiteur lu en positif), jamais une devinette.
    corriger: Callable[[dict[str, object]], dict[str, object]] = lambda lu: lu
    controler: Controle = lambda _lu, _ctx: []
    resumer: Resume = lambda _lu: "Lu par l'OCR."
    # Ce que la fiche garde du document, au-delà de la lecture brute
    # (`donnees` d'un document : un récapitulatif devient `recap_plateforme`).
    donnees: Callable[[Mapping[str, object]], dict[str, object]] = lambda _lu: {}
    # Les champs de la fiche que la lecture remplit s'ils sont vides
    # (capital d'un Kbis, déficits d'une liasse), en texte comme une saisie.
    champs_fiche: Callable[[Mapping[str, object]], dict[str, str]] = lambda _lu: {}
    # Pour une pièce d'un exercice : ne remplir la fiche que depuis l'exercice
    # source (la dernière liasse déposée donne les déficits à reporter).
    exercice_source_seul: bool = False
    max_tokens: int = 8_000
    # AXE-995 : la lecture dit aussi ce que le document est vraiment, pour
    # voir qu'il est mal rangé. Le classement d'un « Autre » le dit déjà.
    constater_nature: bool = True

    def schema(self) -> dict[str, Any]:
        base = schema(self.textes, self.montants, self.listes)
        if self.constater_nature:
            base["properties"][NATURE_CONSTATEE] = {"type": "string", "enum": list(NATURES)}
            base["required"].append(NATURE_CONSTATEE)
        return base

    def consigne_complete(self) -> str:
        texte = f"{CONSIGNE_COMMUNE}\n\n{self.consigne}"
        if not self.constater_nature:
            return texte
        return (
            f"{texte}\n- {NATURE_CONSTATEE} : ce qu'est vraiment ce document, parmi "
            f"{DESCRIPTION_NATURES}. Si c'est bien le document décrit plus haut, rends "
            f"« {self.cle} »."
        )


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
