"""Confirmation de la configuration par le dirigeant (AXE-730).

Un dossier est **ambigu** tant que :
- Sirene a proposé un élément sans certitude (`Dossier.a_confirmer` : forme
  SAS ou SASU, SARL ou EURL ; premier exercice déduit de la création) ;
- ou, pour une société, le siège, le capital ou les associés manquent.
  Sirene ne les donne pas, et la liasse ne s'en passe pas ;
- ou un registre officiel (INSEE, RNE) dit autre chose que la déclaration,
  tant que personne n'a tranché (AXE-849). Une société cessée au registre
  passe avant tout le reste.

La clôture et la liasse fiscale refusent un dossier ambigu. Pur : le dépôt
écrit, l'API lit.
"""

from __future__ import annotations

from dataclasses import replace

from axelcompta.core.errors import DomaineError

from .models import Dossier
from .registres import CHAMP_ETAT, phrase
from .sirene import A_CONFIRMER_EXERCICE, A_CONFIRMER_FORME
from .statuts import FormeJuridique

# Sirene ne distingue pas ces formes : le dirigeant choisit entre les deux.
FORMES_JUMELLES: dict[str, tuple[str, str]] = {
    FormeJuridique.SAS: (FormeJuridique.SAS, FormeJuridique.SASU),
    FormeJuridique.SASU: (FormeJuridique.SAS, FormeJuridique.SASU),
    FormeJuridique.SARL: (FormeJuridique.SARL, FormeJuridique.EURL),
    FormeJuridique.EURL: (FormeJuridique.SARL, FormeJuridique.EURL),
}

MANQUE_SIEGE = "siege"
MANQUE_CAPITAL = "capital"
MANQUE_ASSOCIES = "associes"

_NOMS = {
    A_CONFIRMER_FORME: "la forme juridique",
    A_CONFIRMER_EXERCICE: "les dates du premier exercice",
    MANQUE_SIEGE: "l'adresse du siège",
    MANQUE_CAPITAL: "le capital",
    MANQUE_ASSOCIES: "les associés",
}


class ConfirmationRefusee(DomaineError):
    """La forme choisie n'est pas une de celles que Sirene laisse ouvertes."""


def est_societe(dossier: Dossier) -> bool:
    return dossier.forme_juridique != FormeJuridique.EI


def identite_manquante(dossier: Dossier) -> tuple[str, ...]:
    """Ce que la liasse d'une société exige et que le dossier n'a pas."""
    if not est_societe(dossier):
        return ()
    identite = dossier.identite
    if identite is None:
        return (MANQUE_SIEGE, MANQUE_CAPITAL, MANQUE_ASSOCIES)
    manque = []
    siege = identite.adresse_siege
    if not (siege.voie.strip() and siege.code_postal.strip() and siege.commune.strip()):
        manque.append(MANQUE_SIEGE)
    if identite.capital_social_cts <= 0:
        manque.append(MANQUE_CAPITAL)
    if not identite.associes:
        manque.append(MANQUE_ASSOCIES)
    return tuple(manque)


def formes_proposees(dossier: Dossier) -> tuple[str, ...]:
    """Les formes entre lesquelles le dirigeant choisit ; une seule sinon."""
    if A_CONFIRMER_FORME in dossier.a_confirmer:
        return FORMES_JUMELLES.get(dossier.forme_juridique, (dossier.forme_juridique,))
    return (dossier.forme_juridique,)


def raison_ambiguite(dossier: Dossier) -> str | None:
    """La phrase qui bloque la clôture et la liasse, ou `None`."""
    a_confirmer = [_NOMS.get(code, code) for code in dossier.a_confirmer]
    manque = [_NOMS[code] for code in identite_manquante(dossier)]
    ecarts = dossier.ecarts_registre
    if any(e.champ == CHAMP_ETAT for e in ecarts):
        return "La société est cessée au registre : vérifiez avant toute clôture."
    if a_confirmer:
        return f"Le dirigeant doit d'abord confirmer {_liste(a_confirmer)}."
    if ecarts:
        return "Le registre ne dit pas la même chose. " + " ".join(phrase(e) for e in ecarts)
    if manque:
        return f"Il manque {_liste(manque)} de la société."
    return None


def confirmer(dossier: Dossier, forme: str | None) -> Dossier:
    """Le dirigeant confirme ce que Sirene a proposé, en choisissant la forme
    s'il le faut. Les éléments d'identité manquants ne se confirment pas :
    ils restent à saisir."""
    choisie = forme or dossier.forme_juridique
    if choisie not in formes_proposees(dossier):
        raise ConfirmationRefusee(f"Forme juridique non proposée pour ce dossier : {choisie}.")
    return replace(dossier, forme_juridique=choisie, a_confirmer=())


def _liste(elements: list[str]) -> str:
    if len(elements) == 1:
        return elements[0]
    return ", ".join(elements[:-1]) + " et " + elements[-1]
