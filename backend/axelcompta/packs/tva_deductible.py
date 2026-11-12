"""TVA déductible estimée d'une dépense venue de la banque (AXE-831).

La banque donne un montant TTC, jamais la TVA. Sans justificatif, on l'estime
d'après la catégorie : `tva_deductible.toml` donne le taux supposé et la part
récupérable, avec la source de chaque règle.

Pur : pas de base, pas d'horloge. Une dépense payée à l'étranger reste un cas
à corriger avec le justificatif : la TVA étrangère ne se déduit pas en France,
et la banque ne dit pas toujours où l'achat a eu lieu.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path

CHEMIN_TABLE = Path(__file__).with_name("tva_deductible.toml")
COMPTE_TVA_DEDUCTIBLE = "44566"  # TVA déductible sur autres biens et services
REGIME_FRANCHISE = "franchise"


@dataclass(frozen=True, slots=True)
class RegleTva:
    """La TVA supposée d'une catégorie : `taux` en %, `recuperable` en %."""

    taux: Decimal
    recuperable: int
    compte: str = COMPTE_TVA_DEDUCTIBLE
    source: str = ""

    @property
    def code(self) -> str:
        """Le code TVA posé sur les lignes : estimée, pas lue sur une facture."""
        return f"deductible_estimee_{self.taux.normalize():f}"


@dataclass(frozen=True, slots=True)
class _Version:
    debut: date
    categories: dict[str, RegleTva]


@cache
def _versions(chemin: Path = CHEMIN_TABLE) -> tuple[_Version, ...]:
    with chemin.open("rb") as fichier:
        brut = tomllib.load(fichier)
    versions = [
        _Version(
            debut=v["debut"],
            categories={
                nom: RegleTva(
                    taux=Decimal(r["taux"]),
                    recuperable=int(r["recuperable"]),
                    compte=r.get("compte", COMPTE_TVA_DEDUCTIBLE),
                    source=r.get("source", ""),
                )
                for nom, r in v.get("categories", {}).items()
            },
        )
        for v in brut["versions"]
    ]
    return tuple(sorted(versions, key=lambda v: v.debut))


def regle_tva(categorie: str, jour: date, regime_tva: str) -> RegleTva | None:
    """La règle à appliquer, ou `None` quand rien ne se récupère : dossier en
    franchise, catégorie inconnue, part nulle, ou date antérieure à la table
    (on ne réutilise jamais une règle hors de sa période)."""
    if regime_tva == REGIME_FRANCHISE:
        return None
    applicables = [v for v in _versions() if v.debut <= jour]
    if not applicables:
        return None
    regle = applicables[-1].categories.get(categorie)
    if regle is None or regle.recuperable <= 0 or regle.taux <= 0:
        return None
    return regle


def tva_recuperable(montant_ttc_cts: int, regle: RegleTva) -> int:
    """La TVA récupérable contenue dans un montant TTC, en centimes, arrondie
    au centime le plus proche. Toujours entre 0 et le montant : le reste
    (HT et TVA non récupérable) va en charge, au centime près."""
    ttc = Decimal(abs(montant_ttc_cts))
    tva = ttc - (ttc * 100 / (100 + regle.taux)).quantize(Decimal(1), ROUND_HALF_UP)
    recuperable = (tva * regle.recuperable / 100).quantize(Decimal(1), ROUND_HALF_UP)
    return int(min(max(recuperable, Decimal(0)), ttc))
