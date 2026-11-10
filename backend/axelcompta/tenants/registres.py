"""Données officielles d'une entreprise et écarts avec ce qu'en déclare le
dirigeant (AXE-849).

Deux registres :
- l'**INSEE** (API Sirene) : dénomination, catégorie juridique, siège, date
  de création, état (actif ou cessé), activité ;
- le **RNE** (INPI) : forme exacte grâce à l'indicateur d'associé unique
  (Sirene ne distingue pas SAS et SASU, ni SARL et EURL), capital,
  dirigeants.

Pur : les réponses brutes sont lues ici, les appels HTTP vivent dans
`axelcompta.registres_officiels`. **Les formats sont lus d'après la
documentation publique des deux API, pas encore sur une vraie réponse**
(pas de clé à l'écriture) : chaque champ absent ou illisible devient
`None`, jamais une valeur par défaut, et une valeur `None` n'est jamais
comparée. Un écart ne naît donc que de deux valeurs connues et différentes.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation

from axelcompta.core.errors import Introuvable, SaisieInvalide
from axelcompta.core.identite import Adresse

from .models import Dossier, EcartRegistre
from .sirene import forme_depuis_nature

SOURCE_INSEE = "insee"
SOURCE_RNE = "rne"

CHAMP_ETAT = "etat"
CHAMP_FORME = "forme_juridique"
CHAMP_DENOMINATION = "denomination"
CHAMP_SIEGE = "siege"
CHAMP_CAPITAL = "capital"
CHAMP_DIRIGEANT = "dirigeant"

# Une forme « à plusieurs » devient « à associé unique » quand le RNE le dit.
_UNIPERSONNELLE = {"SAS": "SASU", "SARL": "EURL"}


@dataclass(frozen=True, slots=True)
class FicheOfficielle:
    """Ce que disent les registres, à une date de lecture. `None` : le
    registre ne le dit pas (ou n'a pas été lu)."""

    siren: str
    lu_le: date
    sources: tuple[str, ...]
    denomination: str | None = None
    categorie_juridique: str | None = None
    forme_juridique: str | None = None
    siege: Adresse | None = None
    capital_cts: int | None = None
    dirigeants: tuple[str, ...] = ()
    cessee: bool | None = None
    date_creation: date | None = None
    code_naf: str | None = None


def _objet(valeur: object) -> Mapping[str, object]:
    return valeur if isinstance(valeur, Mapping) else {}


def _chemin(racine: object, *cles: str) -> object:
    courant: object = racine
    for cle in cles:
        courant = _objet(courant).get(cle)
    return courant


def _texte(valeur: object) -> str | None:
    if isinstance(valeur, str) and valeur.strip():
        return valeur.strip()
    return None


def _date(valeur: object) -> date | None:
    texte = _texte(valeur)
    try:
        return date.fromisoformat(texte) if texte else None
    except ValueError:
        return None


def _adresse(
    numero: object, type_voie: object, voie: object, cp: object, commune: object
) -> Adresse | None:
    if _texte(cp) is None or _texte(commune) is None:
        return None
    libelle = " ".join(p for p in (_texte(type_voie), _texte(voie)) if p)
    return Adresse(_texte(numero) or "", libelle, _texte(cp) or "", _texte(commune) or "")


def fiche_insee(
    unite_legale: Mapping[str, object], etablissement: Mapping[str, object], siren: str, lu_le: date
) -> FicheOfficielle | None:
    """`GET /siren/{siren}` et `GET /siret/{siret du siège}` de l'API Sirene
    3.11. `None` si la réponse ne porte pas ce SIREN."""
    unite = _objet(unite_legale.get("uniteLegale"))
    if str(unite.get("siren") or "") != siren:
        return None
    periodes = unite.get("periodesUniteLegale")
    courante = _objet(periodes[0]) if isinstance(periodes, Sequence) and periodes else {}
    etat = _texte(courante.get("etatAdministratifUniteLegale"))
    categorie = _texte(courante.get("categorieJuridiqueUniteLegale"))
    adresse = _objet(_chemin(etablissement, "etablissement", "adresseEtablissement"))
    return FicheOfficielle(
        siren=siren,
        lu_le=lu_le,
        sources=(SOURCE_INSEE,),
        denomination=_texte(courante.get("denominationUniteLegale")),
        categorie_juridique=categorie,
        forme_juridique=forme_depuis_nature(categorie),
        siege=_adresse(
            adresse.get("numeroVoieEtablissement"),
            adresse.get("typeVoieEtablissement"),
            adresse.get("libelleVoieEtablissement"),
            adresse.get("codePostalEtablissement"),
            adresse.get("libelleCommuneEtablissement"),
        ),
        cessee=None if etat is None else etat == "C",
        date_creation=_date(unite.get("dateCreationUniteLegale")),
        code_naf=_texte(courante.get("activitePrincipaleUniteLegale")),
    )


def _capital_cts(valeur: object) -> int | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, str)):
        return None
    try:
        euros = Decimal(str(valeur).replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None
    centimes = euros * 100
    return int(centimes) if centimes == centimes.to_integral_value() and centimes >= 0 else None


def _dirigeants(pouvoirs: object) -> tuple[str, ...]:
    noms = []
    for pouvoir in (
        pouvoirs if isinstance(pouvoirs, Sequence) and not isinstance(pouvoirs, str) else ()
    ):
        personne = _objet(_chemin(pouvoir, "individu", "descriptionPersonne"))
        nom = _texte(personne.get("nom"))
        prenoms = personne.get("prenoms")
        premier = (
            _texte(prenoms[0])
            if isinstance(prenoms, Sequence) and not isinstance(prenoms, str) and prenoms
            else _texte(prenoms)
        )
        if nom:
            noms.append(" ".join(p for p in (premier, nom) if p))
    return tuple(noms)


def fiche_rne(reponse: Mapping[str, object], siren: str, lu_le: date) -> FicheOfficielle | None:
    """`GET /api/companies/{siren}` du RNE. `None` si la réponse ne porte pas
    ce SIREN ou pas de personne morale."""
    if str(reponse.get("siren") or "") != siren:
        return None
    morale = _objet(_chemin(reponse, "formality", "content", "personneMorale"))
    if not morale:
        return None
    entreprise = _objet(_chemin(morale, "identite", "entreprise"))
    description = _objet(_chemin(morale, "identite", "description"))
    categorie = _texte(entreprise.get("formeJuridique"))
    forme = forme_depuis_nature(categorie)
    unique = description.get("indicateurAssocieUnique")
    if isinstance(unique, bool) and forme in _UNIPERSONNELLE:
        forme = _UNIPERSONNELLE[forme] if unique else forme
    elif forme in _UNIPERSONNELLE:
        forme = None  # le RNE ne lève pas l'ambiguïté : on ne compare pas
    adresse = _objet(_chemin(morale, "adresseEntreprise", "adresse"))
    return FicheOfficielle(
        siren=siren,
        lu_le=lu_le,
        sources=(SOURCE_RNE,),
        denomination=_texte(entreprise.get("denomination")),
        categorie_juridique=categorie,
        forme_juridique=forme,
        siege=_adresse(
            adresse.get("numVoie"),
            adresse.get("typeVoie"),
            adresse.get("voie"),
            adresse.get("codePostal"),
            adresse.get("commune"),
        ),
        capital_cts=_capital_cts(description.get("montantCapital")),
        dirigeants=_dirigeants(_chemin(morale, "composition", "pouvoirs")),
    )


def combiner(insee: FicheOfficielle | None, rne: FicheOfficielle | None) -> FicheOfficielle | None:
    """Le RNE fait foi pour la forme, le capital et les dirigeants ; l'INSEE
    pour l'état, l'activité et la date de création. Chacun complète l'autre."""
    if insee is None or rne is None:
        return insee or rne
    return replace(
        insee,
        sources=(SOURCE_INSEE, SOURCE_RNE),
        lu_le=max(insee.lu_le, rne.lu_le),
        denomination=rne.denomination or insee.denomination,
        forme_juridique=rne.forme_juridique
        or (None if insee.forme_juridique in _UNIPERSONNELLE else insee.forme_juridique),
        siege=insee.siege or rne.siege,
        capital_cts=rne.capital_cts,
        dirigeants=rne.dirigeants,
    )


def _normal(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join("".join(c if c.isalnum() else " " for c in sans_accents.upper()).split())


def _euros(centimes: int) -> str:
    return (
        f"{centimes // 100:,}".replace(",", " ")
        + (f",{centimes % 100:02d}" if centimes % 100 else "")
        + " €"
    )


def ecarts(dossier: Dossier, fiche: FicheOfficielle) -> tuple[EcartRegistre, ...]:
    """Champ par champ, ce qui diffère entre la déclaration et le registre.
    Une société cessée passe en premier."""
    trouves: list[EcartRegistre] = []
    if fiche.cessee:
        trouves.append(EcartRegistre(CHAMP_ETAT, "active", "cessée"))
    if fiche.forme_juridique and fiche.forme_juridique != dossier.forme_juridique:
        trouves.append(EcartRegistre(CHAMP_FORME, dossier.forme_juridique, fiche.forme_juridique))
    identite = dossier.identite
    if identite is None:
        return tuple(trouves)
    if fiche.denomination and _normal(fiche.denomination) != _normal(identite.denomination):
        trouves.append(EcartRegistre(CHAMP_DENOMINATION, identite.denomination, fiche.denomination))
    siege = identite.adresse_siege
    if fiche.siege and (siege.code_postal, _normal(siege.commune)) != (
        fiche.siege.code_postal,
        _normal(fiche.siege.commune),
    ):
        trouves.append(
            EcartRegistre(CHAMP_SIEGE, siege.sur_une_ligne(), fiche.siege.sur_une_ligne())
        )
    if fiche.capital_cts is not None and fiche.capital_cts != identite.capital_social_cts:
        trouves.append(
            EcartRegistre(
                CHAMP_CAPITAL, _euros(identite.capital_social_cts), _euros(fiche.capital_cts)
            )
        )
    if fiche.dirigeants and identite.associes:
        dirigeant = identite.dirigeant
        noms = {_normal(nom).split()[-1] for nom in fiche.dirigeants}
        if _normal(dirigeant.nom).split()[-1:] and _normal(dirigeant.nom).split()[-1] not in noms:
            trouves.append(
                EcartRegistre(
                    CHAMP_DIRIGEANT,
                    f"{dirigeant.prenoms} {dirigeant.nom}",
                    ", ".join(fiche.dirigeants),
                )
            )
    return tuple(trouves)


def restants(
    trouves: Sequence[EcartRegistre], resolus: Mapping[str, str]
) -> tuple[EcartRegistre, ...]:
    """Les écarts que personne n'a tranchés. Une résolution vaut pour la
    valeur du registre qu'elle a vue : si le registre change, l'écart revient."""
    return tuple(e for e in trouves if resolus.get(e.champ) != e.officiel)


# (déclaré, au registre) : accordés avec le nom du champ.
_PHRASES = {
    CHAMP_FORME: ("Forme déclarée", "forme au registre"),
    CHAMP_DENOMINATION: ("Nom déclaré", "nom au registre"),
    CHAMP_SIEGE: ("Siège déclaré", "siège au registre"),
    CHAMP_CAPITAL: ("Capital déclaré", "capital au registre"),
    CHAMP_DIRIGEANT: ("Dirigeant déclaré", "dirigeants au registre"),
}


def phrase(ecart: EcartRegistre) -> str:
    """« Forme déclarée SASU, forme au registre SAS. »"""
    if ecart.champ == CHAMP_ETAT:
        return "Société cessée au registre."
    declare, officiel = _PHRASES.get(ecart.champ, (ecart.champ, "au registre"))
    return f"{declare} {ecart.declare}, {officiel} {ecart.officiel}."


class TranchageRefuse(SaisieInvalide):
    """Une valeur à retenir qui n'a pas de sens pour cet écart."""


def trancher(
    dossier: Dossier, champ: str, retenue: str
) -> tuple[EcartRegistre, tuple[EcartRegistre, ...], str | None]:
    """L'écart tranché, les écarts qui restent, et la forme à poser si le
    dirigeant retient celle du registre. Pour les autres champs, retenir le
    registre veut dire que la saisie de l'identité est à corriger : l'écart
    ne revient pas tant que le registre ne change pas."""
    trouve = next((e for e in dossier.ecarts_registre if e.champ == champ), None)
    if trouve is None:
        raise Introuvable(f"Aucun écart en cours sur : {champ}.")
    if retenue not in ("declaree", "officielle"):
        raise TranchageRefuse("Choisissez la valeur déclarée ou celle du registre.")
    if champ == CHAMP_ETAT and retenue == "officielle":
        raise TranchageRefuse(
            "Une société cessée se retire du portefeuille : prévenez votre gestionnaire."
        )
    restants_apres = tuple(e for e in dossier.ecarts_registre if e.champ != champ)
    forme = trouve.officiel if champ == CHAMP_FORME and retenue == "officielle" else None
    return trouve, restants_apres, forme


def phrase_gestionnaire(ecart: EcartRegistre) -> str:
    """Pour le gestionnaire : le détail, sauf les noms de personnes."""
    if ecart.champ == CHAMP_DIRIGEANT:
        return "Dirigeant différent de celui du registre."
    return phrase(ecart)
