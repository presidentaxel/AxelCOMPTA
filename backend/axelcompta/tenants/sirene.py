"""Configuration d'un dossier tirée du répertoire Sirene (AXE-834).

Pur : la réponse de l'API « Recherche d'entreprises » (data.gouv, sans clé)
est lue ailleurs ; ici, on la transforme en configuration de dossier.

Ce que Sirene dit, et ce qu'il ne dit pas :
- **date de création** : le premier exercice d'une société créée dans
  l'année commence ce jour-là, pas au 1er janvier ;
- **état administratif** : une société cessée (`C`) n'a pas de dossier ;
- **activité (NAF)** : 49.32Z (taxis, VTC) ou 49.39B (autres transports
  routiers de voyageurs) désigne un chauffeur ;
- **nature juridique** : depuis 2020, SAS et SASU partagent 5710, SARL et
  EURL 5499. On pose SAS ou SARL et on marque la forme « à confirmer » : le
  dirigeant tranche (associé unique ou non), on ne devine pas.

Une valeur proposée ici n'est jamais définitive : elle part dans
`Dossier.a_confirmer` jusqu'à ce que le dirigeant la valide (AXE-730).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date

from .models import Dossier

CODES_NAF_CHAUFFEUR = frozenset({"49.32Z", "49.39B"})
ETAT_ACTIF = "A"

# Nomenclature des catégories juridiques, niveau III. 5710 et 5499 couvrent
# aussi l'associé unique depuis 2020 : forme posée, mais à confirmer.
_FORME_PAR_NATURE = {"1000": "EI", "5498": "EURL", "5499": "SARL", "5710": "SAS", "5720": "SASU"}
NATURES_AMBIGUES = frozenset({"5499", "5710"})

A_CONFIRMER_FORME = "forme_juridique"
A_CONFIRMER_EXERCICE = "exercice"


@dataclass(frozen=True, slots=True)
class FicheSirene:
    siren: str
    nature_juridique: str | None
    code_naf: str | None
    etat_administratif: str | None
    date_creation: date | None

    @property
    def active(self) -> bool:
        return self.etat_administratif in (None, ETAT_ACTIF)

    @property
    def chauffeur(self) -> bool:
        return self.code_naf in CODES_NAF_CHAUFFEUR


def fiche_depuis_reponse(reponse: Mapping[str, object], siren: str) -> FicheSirene | None:
    """Premier résultat de `GET /search?q=<siren>`, seulement si son SIREN
    est exactement celui demandé. Une valeur absente ou illisible devient
    `None`, jamais une valeur par défaut."""
    resultats = reponse.get("results")
    if not isinstance(resultats, list) or not resultats:
        return None
    premier = resultats[0]
    if not isinstance(premier, Mapping) or str(premier.get("siren") or "") != siren:
        return None
    return FicheSirene(
        siren=siren,
        nature_juridique=_texte(premier.get("nature_juridique")),
        code_naf=_texte(premier.get("activite_principale")),
        etat_administratif=_texte(premier.get("etat_administratif")),
        date_creation=_date(premier.get("date_creation")),
    )


def forme_depuis_nature(nature: str | None) -> str | None:
    return None if nature is None else _FORME_PAR_NATURE.get(nature.strip())


def configurer_depuis_sirene(dossier: Dossier, fiche: FicheSirene, aujourd_hui: date) -> Dossier:
    """Forme, premier exercice, activité et ce qui reste à confirmer.

    Le premier exercice n'est déplacé que s'il commence **avant** la
    création de la société (impossible) : un exercice déjà correct, ou
    choisi par le dirigeant, n'est jamais touché."""
    a_confirmer = set(dossier.a_confirmer)
    forme = forme_depuis_nature(fiche.nature_juridique) or dossier.forme_juridique
    if fiche.nature_juridique is None or fiche.nature_juridique.strip() in NATURES_AMBIGUES:
        a_confirmer.add(A_CONFIRMER_FORME)
    debut, fin = dossier.exercice_debut, dossier.exercice_fin
    creation = fiche.date_creation
    if creation is not None and creation > debut and creation <= aujourd_hui:
        debut = creation
        fin = date(creation.year, 12, 31)
        a_confirmer.add(A_CONFIRMER_EXERCICE)
    return replace(
        dossier,
        forme_juridique=forme,
        exercice_debut=debut,
        exercice_fin=fin,
        code_naf=fiche.code_naf,
        a_confirmer=tuple(sorted(a_confirmer)),
    )


def _texte(valeur: object) -> str | None:
    if not isinstance(valeur, str):
        return None
    texte = valeur.strip()
    return texte or None


def _date(valeur: object) -> date | None:
    texte = _texte(valeur)
    if texte is None:
        return None
    try:
        return date.fromisoformat(texte[:10])
    except ValueError:
        return None
