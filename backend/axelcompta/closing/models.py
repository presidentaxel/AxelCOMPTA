"""LiassePivot — modèle indépendant du format de sortie (doc 02 §5, doc 06 §6) :
la télédéclaration EDI est un renderer qu'on branche plus tard, pas une refonte.
Squelette de structure uniquement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from axelcompta.core.identite import IdentiteEntreprise
from axelcompta.core.ids import DossierId


@dataclass(frozen=True, slots=True)
class LiassePivot:
    """Sous-ensemble réduit pour la démo (doc 17 semaine 3) : bilan simplifié +
    compte de résultat + une case-clé 2065. La V1 couvre le jeu de formulaires
    complet.

    `exercice_debut`/`exercice_fin` : les vraies bornes de l'exercice, dérivées
    des dates d'écriture réelles quand elles sont connues (un dossier réel
    peut avoir un exercice partiel — création en cours d'année — pas
    forcément aligné sur l'année civile). `None` si on ne les connaît pas
    (ex. `LiassePivot` construite à la main dans un test) — les renderers
    retombent alors sur l'année civile de `exercice`.
    """

    dossier_id: DossierId
    exercice: str  # ex. "2026"
    cases: dict[str, int] = field(default_factory=dict)  # code case → centimes
    exercice_debut: date | None = None
    exercice_fin: date | None = None
    # Renseignés seulement par une clôture avec `ParametresCloture` (liasse
    # fiscale complète, cases `2033A.xxx`, `2033B.xxx`... en plus des cases
    # historiques ci-dessus).
    identite: IdentiteEntreprise | None = None
    forme_juridique: str = ""
    # Faux à l'IR : la déclaration de résultat est la 2031, pas la 2065.
    soumis_is: bool = True
    # Faux pour une entreprise individuelle : ni associés (2031-bis cadre E)
    # ni composition du capital (2033-F).
    associes: bool = True


@dataclass(frozen=True, slots=True)
class ProvisionCloture:
    """Estimation fournie par l'indiv (doc 06 §5, point 5). `centimes` est
    un entier positif. `nature` vaut ``cca`` ou ``fnp``."""

    nature: str
    compte_charge: str
    centimes: int
    libelle: str


@dataclass(frozen=True, slots=True)
class ParametresCloture:
    """Ce que la clôture fiscale doit savoir du dossier, au-delà de ses
    écritures : bornes déclarées de l'exercice (pas les dates des écritures),
    identité pour les en-têtes, report des déficits de l'exercice précédent
    (2033-D ligne 870, en euros) et effectif salarié moyen (2033-E)."""

    exercice_debut: date
    exercice_fin: date
    forme_juridique: str
    identite: IdentiteEntreprise | None = None
    deficits_anterieurs: int = 0
    effectif_moyen: int = 0
    # Colonne de la matrice doc 06 §7 : faux quand le résultat est imposé à
    # l'IR chez l'exploitant ou les associés (ni écriture d'IS, ni 2065).
    soumis_is: bool = True
    # Colonne de la matrice : la déclaration liste-t-elle des associés ?
    associes: bool = True
    # "2033" : régime simplifié, liasse servie aujourd'hui. "2050" : y ajoute
    # le réel normal (bilan 2050/2051 et compte de résultat 2052/2053), sans
    # remplacer la 2033 ni produire de PDF.
    regime_liasse: str = "2033"
    # Estimations saisies (CCA, FNP). Vide : le moteur n'en invente pas.
    provisions: tuple[ProvisionCloture, ...] = ()
