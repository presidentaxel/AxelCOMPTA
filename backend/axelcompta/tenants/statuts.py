"""Configuration fiscale d'un dossier, lue dans la matrice (doc 06 §7).

Le dossier garde ses valeurs en texte (c'est ce que la base et l'API
transportent) ; `configuration_de` les valide et les type une fois pour
toutes. Le moteur lit ensuite la colonne de la matrice (compte d'usage
personnel, impôt, formulaires, dépôt au greffe) au lieu de tester la forme
juridique lui-même.

Chaque dossier est indépendant : aucune valeur n'est héritée du tenant.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import cache
from pathlib import Path

from axelcompta.core.errors import SaisieInvalide

from .models import Dossier

CHEMIN_MATRICE = Path(__file__).with_name("matrice_statuts.toml")
# Comptes propres aux catégories de statut qui ne varient pas avec la forme.
COMPTE_PAIE_DUE = "421"
COMPTE_PAS = "4421"  # prélèvement à la source retenu sur la paie
COMPTE_DIVIDENDES = "457"  # dividendes à payer
COMPTE_RETENUES_DIVIDENDES = "4423"  # retenues et prélèvements sur distributions

# L'option IR temporaire couvre au plus 5 exercices (art. 239 bis AB CGI).
DUREE_OPTION_IR = 5
# Le réel simplifié de TVA disparaît au 01/01/2027 (doc 02 §7bis) : il ne
# reste lisible que pour les exercices ouverts avant.
FIN_REEL_SIMPLIFIE = date(2027, 1, 1)


class FormeJuridique(StrEnum):
    SASU = "SASU"
    SAS = "SAS"
    EURL = "EURL"
    SARL = "SARL"
    EI = "EI"


class RegimeImposition(StrEnum):
    IS = "IS"
    OPTION_IR = "option_IR"
    IR = "IR"
    MICRO = "micro"


class RegimeTva(StrEnum):
    REEL_NORMAL = "reel_normal"
    REEL_SIMPLIFIE = "reel_simplifie"
    FRANCHISE = "franchise"


class TvaRecettes(StrEnum):
    ASSUJETTI_TAUX_REDUIT = "assujetti_taux_reduit"
    FRANCHISE = "franchise"


class PackMetier(StrEnum):
    VTC = "vtc"


@dataclass(frozen=True, slots=True)
class ColonneMatrice:
    cle: str
    libelle: str
    disponible: bool
    entite: str
    comptabilite: str
    impot: str
    formulaires_resultat: tuple[str, ...]
    depot_comptes_inpi: bool
    compte_usage_personnel: str | None
    associes: bool

    @property
    def soumis_is(self) -> bool:
        return self.impot == "IS"


@dataclass(frozen=True, slots=True)
class Matrice:
    version: str
    colonnes: dict[str, ColonneMatrice]
    combinaisons: dict[tuple[FormeJuridique, RegimeImposition], str]
    remuneration_dirigeant: dict[FormeJuridique, str]
    cotisations_dirigeant: dict[FormeJuridique, str]

    def colonne(self, forme: FormeJuridique, regime: RegimeImposition) -> ColonneMatrice | None:
        cle = self.combinaisons.get((forme, regime))
        return None if cle is None else self.colonnes[cle]


@cache
def charger_matrice(chemin: Path = CHEMIN_MATRICE) -> Matrice:
    with chemin.open("rb") as fichier:
        brut = tomllib.load(fichier)
    colonnes = {
        cle: ColonneMatrice(
            cle=cle,
            libelle=c["libelle"],
            disponible=c["disponible"],
            entite=c["entite"],
            comptabilite=c["comptabilite"],
            impot=c["impot"],
            formulaires_resultat=tuple(c["formulaires_resultat"]),
            depot_comptes_inpi=c["depot_comptes_inpi"],
            compte_usage_personnel=c.get("compte_usage_personnel"),
            associes=c["associes"],
        )
        for cle, c in brut["colonnes"].items()
    }
    combinaisons: dict[tuple[FormeJuridique, RegimeImposition], str] = {}
    for c in brut["combinaisons"]:
        cle = (FormeJuridique(c["forme"]), RegimeImposition(c["regime"]))
        if cle in combinaisons or c["colonne"] not in colonnes:
            raise ValueError(f"matrice incohérente sur {cle} ({chemin.name})")
        combinaisons[cle] = c["colonne"]
    remuneration = {
        FormeJuridique(forme): compte
        for forme, compte in brut.get("remuneration_dirigeant", {}).items()
    }
    cotisations = {
        FormeJuridique(forme): compte
        for forme, compte in brut.get("cotisations_dirigeant", {}).items()
    }
    return Matrice(
        version=brut["version"],
        colonnes=colonnes,
        combinaisons=combinaisons,
        remuneration_dirigeant=remuneration,
        cotisations_dirigeant=cotisations,
    )


class ConfigurationInvalide(SaisieInvalide, ValueError):
    """Toutes les erreurs d'un coup, pour qu'un import ou un formulaire puisse
    les afficher ensemble plutôt qu'une à la fois."""

    def __init__(self, dossier_id: str, erreurs: list[str]) -> None:
        super().__init__(f"configuration du dossier {dossier_id} invalide : " + " ; ".join(erreurs))
        self.erreurs = erreurs


@dataclass(frozen=True, slots=True)
class ConfigurationDossier:
    forme: FormeJuridique
    regime_imposition: RegimeImposition
    regime_tva: RegimeTva
    tva_recettes: TvaRecettes
    pack: PackMetier
    option_ir_debut: int | None
    colonne: ColonneMatrice
    compte_remuneration_dirigeant: str | None = None
    compte_cotisations_dirigeant: str | None = None

    @property
    def paie_par_bulletin(self) -> bool:
        """Président assimilé salarié : sa paie se passe depuis son bulletin,
        son virement net solde la paie due (421)."""
        return self.compte_remuneration_dirigeant == COMPTE_PAIE_DUE

    def comptes_categories_statut(self) -> dict[str, str | None]:
        """Catégories dont le compte dépend du statut et non du pack. `None`
        : sans écriture pour ce statut, ou à préciser."""
        societe_is = self.colonne.soumis_is
        return {
            "usage_personnel": self.colonne.compte_usage_personnel,
            # Apport, remboursement ou dépense de l'associé : même compte que
            # l'usage personnel (455 en société, 108 pour l'exploitant d'EI).
            "compte_courant_associe": self.colonne.compte_usage_personnel,
            "remuneration_dirigeant": self.compte_remuneration_dirigeant,
            "cotisations_dirigeant": self.compte_cotisations_dirigeant,
            "prelevement_source_paie": COMPTE_PAS if self.paie_par_bulletin else None,
            "dividendes": COMPTE_DIVIDENDES if societe_is else None,
            "impots_dividendes": COMPTE_RETENUES_DIVIDENDES if societe_is else None,
        }


def _en_enum[E: StrEnum](type_: type[E], valeur: str, champ: str, erreurs: list[str]) -> E | None:
    try:
        return type_(valeur)
    except ValueError:
        admises = ", ".join(v.value for v in type_)
        erreurs.append(f"{champ} « {valeur} » inconnu (admis : {admises})")
        return None


def erreurs_configuration(dossier: Dossier, matrice: Matrice | None = None) -> list[str]:
    return _analyser(dossier, matrice or charger_matrice())[1]


def configuration_de(dossier: Dossier, matrice: Matrice | None = None) -> ConfigurationDossier:
    """Lève `ConfigurationInvalide` si la configuration n'a pas de sens."""
    configuration, erreurs = _analyser(dossier, matrice or charger_matrice())
    if configuration is None:
        raise ConfigurationInvalide(dossier.id, erreurs)
    return configuration


def _analyser(dossier: Dossier, matrice: Matrice) -> tuple[ConfigurationDossier | None, list[str]]:
    erreurs: list[str] = []
    forme = _en_enum(FormeJuridique, dossier.forme_juridique, "forme juridique", erreurs)
    regime = _en_enum(RegimeImposition, dossier.regime_imposition, "régime d'imposition", erreurs)
    tva = _en_enum(RegimeTva, dossier.regime_tva, "régime de TVA", erreurs)
    recettes = _en_enum(TvaRecettes, dossier.tva_recettes_regime, "TVA des recettes", erreurs)
    pack = _en_enum(PackMetier, dossier.pack_metier, "pack métier", erreurs)

    colonne = None
    if forme is not None and regime is not None:
        colonne = matrice.colonne(forme, regime)
        if colonne is None:
            erreurs.append(f"une {forme} ne peut pas être au régime « {regime} »")
        erreurs += _erreurs_option_ir(regime, dossier)

    if tva is not None and recettes is not None:
        if (tva is RegimeTva.FRANCHISE) != (recettes is TvaRecettes.FRANCHISE):
            erreurs.append(
                "régime de TVA et TVA des recettes incohérents : la franchise vaut pour les deux"
            )
        if tva is RegimeTva.REEL_SIMPLIFIE and dossier.exercice_debut >= FIN_REEL_SIMPLIFIE:
            erreurs.append("le réel simplifié de TVA n'existe plus pour un exercice ouvert en 2027")

    if (
        erreurs
        or forme is None
        or regime is None
        or tva is None
        or recettes is None
        or pack is None
        or colonne is None
    ):
        return None, erreurs
    configuration = ConfigurationDossier(
        forme=forme,
        regime_imposition=regime,
        regime_tva=tva,
        tva_recettes=recettes,
        pack=pack,
        option_ir_debut=dossier.option_ir_debut,
        colonne=colonne,
        compte_remuneration_dirigeant=matrice.remuneration_dirigeant.get(forme),
        compte_cotisations_dirigeant=matrice.cotisations_dirigeant.get(forme),
    )
    return configuration, []


def _erreurs_option_ir(regime: RegimeImposition, dossier: Dossier) -> list[str]:
    debut = dossier.option_ir_debut
    if regime is not RegimeImposition.OPTION_IR:
        if debut is not None:
            return ["une année de début d'option IR n'a de sens qu'au régime option_IR"]
        return []
    if debut is None:
        return ["l'option IR exige l'année du premier exercice couvert (option_ir_debut)"]
    annee = dossier.exercice_debut.year
    if debut > annee:
        return [f"option IR à partir de {debut}, après l'exercice {annee}"]
    if annee - debut >= DUREE_OPTION_IR:
        return [
            f"l'option IR prise en {debut} couvre au plus {DUREE_OPTION_IR} exercices : "
            f"l'exercice {annee} est à l'IS"
        ]
    return []
