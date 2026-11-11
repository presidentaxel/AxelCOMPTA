"""Saisie de l'identité d'une société par son dirigeant (AXE-846).

La liasse d'une société exige son siège, son capital et ses associés
(`confirmation.identite_manquante`). Sirene ne les donne pas tous : le
dirigeant les saisit, pré-remplis depuis le registre public (Recherche
d'entreprises) quand il donne son SIREN.

Pur : l'API lit le registre et le dépôt écrit. Toute valeur qui ne tient
pas lève `IdentiteInvalide` avec une phrase pour le dirigeant, jamais une
valeur par défaut inventée.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.identite import Adresse, Associe, IdentiteEntreprise

from .import_dossiers import siren_valide
from .statuts import FormeJuridique

CIVILITES = ("M", "MME")
# Une société à associé unique : un seul associé, pas plus.
FORMES_UNIPERSONNELLES = (FormeJuridique.SASU, FormeJuridique.EURL)
QUALITE_PAR_FORME: dict[str, str] = {
    FormeJuridique.SASU: "Président",
    FormeJuridique.SAS: "Président",
    FormeJuridique.EURL: "Gérant",
    FormeJuridique.SARL: "Gérant",
}


class IdentiteInvalide(SaisieInvalide):
    """Une valeur saisie ne tient pas (SIREN, code postal, capital…)."""


@dataclass(frozen=True, slots=True)
class PersonneConnue:
    """Ce qu'un registre dit d'une personne, sans rien inventer. La civilité
    et la date de naissance complète n'y sont pas : le dirigeant les saisit."""

    nom: str
    prenoms: str
    code_postal: str = ""
    commune: str = ""
    pays: str = "France"


@dataclass(frozen=True, slots=True)
class PreRemplissage:
    """Ce que les registres donnent pour un SIREN. Une valeur absente
    reste vide : le dirigeant la saisit."""

    siren: str
    denomination: str
    nic: str
    adresse_siege: Adresse
    code_ape: str
    capital_social_cts: int | None = None
    personnes: tuple[PersonneConnue, ...] = ()


def verifier_identite(identite: IdentiteEntreprise, forme: str, aujourd_hui: date) -> None:
    """Lève `IdentiteInvalide` à la première valeur qui ne tient pas."""
    if not identite.denomination.strip():
        raise IdentiteInvalide("Indiquez le nom de la société.")
    if not siren_valide(identite.siren):
        raise IdentiteInvalide("Le SIREN doit compter 9 chiffres valides.")
    if len(identite.nic) != 5 or not identite.nic.isdigit():
        raise IdentiteInvalide("Le NIC du siège compte 5 chiffres (fin du SIRET).")
    _verifier_adresse(identite.adresse_siege, "du siège")
    if identite.capital_social_cts <= 0:
        raise IdentiteInvalide("Le capital doit être supérieur à zéro.")
    _verifier_associes(identite.associes, forme, aujourd_hui)


def _verifier_adresse(adresse: Adresse, de_quoi: str) -> None:
    if not adresse.voie.strip() or not adresse.commune.strip():
        raise IdentiteInvalide(f"Indiquez la rue et la commune {de_quoi}.")
    if adresse.pays == "France" and (
        len(adresse.code_postal) != 5 or not adresse.code_postal.isdigit()
    ):
        raise IdentiteInvalide(f"Le code postal {de_quoi} compte 5 chiffres.")


def _verifier_associes(associes: tuple[Associe, ...], forme: str, aujourd_hui: date) -> None:
    if not associes:
        raise IdentiteInvalide("Indiquez au moins un associé.")
    if forme in FORMES_UNIPERSONNELLES and len(associes) != 1:
        raise IdentiteInvalide("Une société à associé unique n'a qu'un seul associé.")
    for associe in associes:
        _verifier_associe(associe, aujourd_hui)


def _verifier_associe(associe: Associe, aujourd_hui: date) -> None:
    nom = f"{associe.prenoms} {associe.nom}".strip() or "un associé"
    if associe.civilite not in CIVILITES:
        raise IdentiteInvalide(f"Civilité de {nom} : M ou MME.")
    if not associe.nom.strip() or not associe.prenoms.strip():
        raise IdentiteInvalide("Indiquez le nom et les prénoms de chaque associé.")
    if associe.date_naissance >= aujourd_hui:
        raise IdentiteInvalide(f"La date de naissance de {nom} doit être passée.")
    if not associe.commune_naissance.strip():
        raise IdentiteInvalide(f"Indiquez la commune de naissance de {nom}.")
    if associe.nb_titres <= 0:
        raise IdentiteInvalide(f"Le nombre de titres de {nom} doit être supérieur à zéro.")
    if not associe.qualite.strip():
        raise IdentiteInvalide(f"Indiquez la qualité de {nom} (Président, Gérant, associé).")
    _verifier_adresse(associe.adresse, f"de {nom}")


def qualite_par_defaut(forme: str) -> str:
    """Ce que le dirigeant est le plus souvent, selon la forme."""
    return QUALITE_PAR_FORME.get(forme, "")


def completer_pre_remplissage(
    pre: PreRemplissage | None,
    siren: str,
    denomination: str | None = None,
    siege: Adresse | None = None,
    code_ape: str | None = None,
    capital_social_cts: int | None = None,
    personnes: tuple[PersonneConnue, ...] = (),
) -> PreRemplissage | None:
    """Ajoute le capital et les personnes d'un registre officiel. `None` si
    aucun registre n'a rien donné."""
    if (
        pre is None
        and not denomination
        and siege is None
        and not code_ape
        and not capital_social_cts
        and not personnes
    ):
        return None
    base = pre or PreRemplissage(
        siren=siren,
        denomination="",
        nic="",
        adresse_siege=Adresse("", "", "", ""),
        code_ape="",
    )
    return replace(
        base,
        denomination=base.denomination or denomination or "",
        code_ape=base.code_ape or code_ape or "",
        adresse_siege=(
            base.adresse_siege if base.adresse_siege.voie else (siege or base.adresse_siege)
        ),
        capital_social_cts=capital_social_cts or base.capital_social_cts,
        personnes=personnes or base.personnes,
    )


def pre_remplissage(reponse: Mapping[str, object], siren: str) -> PreRemplissage | None:
    """Premier résultat de Recherche d'entreprises, seulement s'il porte
    exactement ce SIREN. `None` sinon : on ne pré-remplit jamais avec une
    autre société."""
    resultats = reponse.get("results")
    if not isinstance(resultats, list) or not resultats:
        return None
    premier = resultats[0]
    if not isinstance(premier, Mapping) or str(premier.get("siren") or "") != siren:
        return None
    siege = premier.get("siege")
    siege = siege if isinstance(siege, Mapping) else {}
    siret = _texte(siege.get("siret"))
    return PreRemplissage(
        siren=siren,
        denomination=_texte(premier.get("nom_raison_sociale"))
        or _texte(premier.get("nom_complet")),
        nic=siret[9:] if len(siret) == 14 and siret.startswith(siren) else "",
        adresse_siege=_adresse_du_siege(siege),
        code_ape=_texte(siege.get("activite_principale"))
        or _texte(premier.get("activite_principale")),
    )


def _adresse_du_siege(siege: Mapping[str, object]) -> Adresse:
    numero = " ".join(
        partie
        for partie in (_texte(siege.get("numero_voie")), _texte(siege.get("indice_repetition")))
        if partie
    )
    voie = " ".join(
        partie
        for partie in (_texte(siege.get("type_voie")), _texte(siege.get("libelle_voie")))
        if partie
    )
    return Adresse(
        numero=numero,
        voie=voie,
        code_postal=_texte(siege.get("code_postal")),
        commune=_texte(siege.get("libelle_commune")),
    )


def _texte(valeur: object) -> str:
    return valeur.strip() if isinstance(valeur, str) else ""
