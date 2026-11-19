"""OCR de la section Documents administratifs, et classement des « Autre »
(AXE-943). Pur.

* Kbis : SIREN, dénomination, forme, capital, siège, immatriculation.
* Statuts : forme, capital, associés et leurs parts.
* Lettre de l'ancien expert-comptable : le cabinet et son contact.
* Un document rangé en « Autre » : sa nature et son exercice, pour le ranger
  dans sa catégorie ; il est ensuite lu comme tel.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from .categories import DESCRIPTION_NATURES, NATURES, Categorie, Contexte
from .controles import controle_date, controle_siren, date_lue, euros, liste, montants, texte

TYPES_RANGES = NATURES


def _champs_identite(lu: Mapping[str, object], textes: tuple[str, ...]) -> dict[str, str]:
    """Capital (et siège, NAF pour un Kbis), pour une fiche qui ne les a pas."""
    champs = {t: texte(lu, t) for t in textes if texte(lu, t)}
    capital = montants(lu).get("capital_cts")
    if capital and capital > 0:
        champs["capital"] = f"{capital / 100:.2f}"
    return champs


def _kbis(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    erreurs = controle_siren(lu, ctx.siren)
    if not texte(lu, "siren"):
        erreurs.append("SIREN : non lu.")
    if not texte(lu, "denomination"):
        erreurs.append("Dénomination : non lue.")
    erreurs += controle_date(lu, "date_immatriculation", "Date d'immatriculation", False)
    capital = montants(lu).get("capital_cts")
    if capital is not None and capital <= 0:
        erreurs.append(f"Capital lu {euros(capital)} : il est positif.")
    return erreurs


def _resume_kbis(lu: Mapping[str, object]) -> str:
    capital = montants(lu).get("capital_cts")
    morceaux = [
        texte(lu, "denomination"),
        texte(lu, "forme_juridique"),
        f"SIREN {texte(lu, 'siren')}",
    ]
    if capital is not None:
        morceaux.append(f"capital {euros(capital)}")
    if texte(lu, "siege"):
        morceaux.append(f"siège {texte(lu, 'siege')}")
    return "Kbis lu : " + ", ".join(m for m in morceaux if m) + "."


KBIS = Categorie(
    "kbis",
    """Document : un extrait Kbis (ou un avis de situation INSEE).
- denomination, forme_juridique (le sigle seul : SAS, SASU, SARL, EURL, EI), siege (adresse
  complète), code_naf,
  date_immatriculation, siren.
- montants : capital_cts.""",
    textes=(
        "siren",
        "denomination",
        "forme_juridique",
        "siege",
        "code_naf",
        "date_immatriculation",
    ),
    montants=("capital_cts",),
    controler=_kbis,
    resumer=_resume_kbis,
    champs_fiche=lambda lu: _champs_identite(lu, ("siege", "code_naf")),
)


def _statuts(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    erreurs = []
    if not texte(lu, "forme_juridique"):
        erreurs.append("Forme juridique : non lue.")
    capital = montants(lu).get("capital_cts")
    if capital is None or capital <= 0:
        erreurs.append("Capital : non lu.")
    associes = liste(lu, "associes")
    parts = [a.get("parts") for a in associes]
    total = montants(lu).get("nombre_parts_total")
    if associes and total and all(isinstance(p, int) for p in parts):
        somme = sum(int(p) for p in parts if isinstance(p, int))
        if somme != total:
            erreurs.append(f"Les associés ont {somme} parts, les statuts en comptent {total}.")
    return erreurs


def _resume_statuts(lu: Mapping[str, object]) -> str:
    associes = liste(lu, "associes")
    capital = montants(lu).get("capital_cts")
    noms = ", ".join(
        f"{a.get('prenom', '')} {a.get('nom', '')} ({a.get('parts')} parts)".strip()
        for a in associes
    )
    capital_txt = f", capital {euros(capital)}" if capital is not None else ""
    return f"Statuts lus : {texte(lu, 'forme_juridique')}{capital_txt}" + (
        f" ; associés : {noms}." if noms else "."
    )


STATUTS = Categorie(
    "statuts",
    """Document : les statuts de la société.
- forme_juridique (le sigle seul : SAS, SASU, SARL, EURL, EI), denomination, siege,
  date_signature.
- montants : capital_cts ; nombre_parts_total (nombre total d'actions ou de parts, sans centimes :
  100 parts -> 100).
- associes : chaque associé, avec nom, prenom, parts (son nombre d'actions ou de parts, entier).""",
    textes=("forme_juridique", "denomination", "siege", "date_signature"),
    montants=("capital_cts", "nombre_parts_total"),
    listes={"associes": {"nom": "string", "prenom": "string", "parts": "integer"}},
    controler=_statuts,
    resumer=_resume_statuts,
    champs_fiche=lambda lu: _champs_identite(lu, ()),
)


def _lettre(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    return [] if texte(lu, "cabinet") else ["Cabinet : non lu."]


LETTRE_COMPTABLE = Categorie(
    "lettre_comptable",
    """\
Document : un courrier de l'ancien expert-comptable (lettre de fin de mission, de confraternité…).
- cabinet (nom du cabinet), contact (nom de l'expert-comptable), email, telephone, date_lettre.""",
    textes=("cabinet", "contact", "email", "telephone", "date_lettre"),
    controler=_lettre,
    resumer=lambda lu: (
        f"Lettre de {texte(lu, 'cabinet')}"
        + (f" ({texte(lu, 'contact')})" if texte(lu, "contact") else "")
        + "."
    ),
)


_IMMATRICULATION = re.compile(
    r"^[A-Z]{2}-?\d{3}-?[A-Z]{2}$"  # depuis 2009 : AB-123-CD
    r"|^\d{1,4} ?[A-Z]{1,3} ?(\d{2}|2A|2B|97\d)$"  # avant 2009 : 1234 AB 75
)


_FORMES = re.compile(r"\b(SASU|SAS|SARL|EURL|EI|SCI|STE|SOCIETE|M|MME|MR)\b")


def _normal(texte_: str) -> str:
    """Majuscules, sans ponctuation ni forme juridique, espaces simples."""
    propre = re.sub(r"[^A-Z0-9 ]", " ", texte_.upper())
    return " ".join(_FORMES.sub(" ", propre).split())


def _titulaire_connu(titulaire: str, champs: Mapping[str, str]) -> bool | None:
    """La société (dénomination entière) ou le dirigeant (son nom) ; `None`
    si la fiche ne connaît ni l'une ni l'autre."""
    denomination = _normal(champs.get("denomination", ""))
    nom = _normal(champs.get("nom", ""))
    if not denomination and not nom:
        return None
    lu = f" {_normal(titulaire)} "
    return bool(denomination and f" {denomination} " in lu) or bool(nom and f" {nom} " in lu)


def _carte_grise(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    erreurs = []
    immat = texte(lu, "immatriculation").upper().replace(" ", "")
    if not immat:
        erreurs.append("Immatriculation : non lue.")
    elif not _IMMATRICULATION.match(immat):
        erreurs.append(f"Immatriculation lue {immat} : ni AB-123-CD, ni l'ancien format.")
    erreurs += controle_date(
        lu, "date_premiere_immatriculation", "Date de première immatriculation", True
    )
    titulaire = texte(lu, "titulaire")
    if not titulaire:
        erreurs.append("Titulaire : non lu.")
    elif _titulaire_connu(titulaire, ctx.champs) is False:
        erreurs.append(
            f"Titulaire lu « {texte(lu, 'titulaire')} » : ni la société, ni le dirigeant de la "
            "fiche. Véhicule d'un tiers, ou en LOA au nom du loueur ?"
        )
    return erreurs


def _detail_vehicule(lu: Mapping[str, object]) -> str:
    morceaux = [
        " ".join(m for m in (texte(lu, "marque"), texte(lu, "modele")) if m),
        texte(lu, "immatriculation").upper(),
    ]
    jour = date_lue(texte(lu, "date_premiere_immatriculation"))
    if jour is not None:
        morceaux.append(f"1re immatriculation le {jour:%d/%m/%Y}")
    if texte(lu, "energie"):
        morceaux.append(texte(lu, "energie").lower())
    if texte(lu, "puissance_fiscale"):
        morceaux.append(f"{texte(lu, 'puissance_fiscale')} CV")
    return ", ".join(m for m in morceaux if m) + " (carte grise)."


CARTE_GRISE = Categorie(
    "carte_grise",
    """Document : un certificat d'immatriculation (carte grise) d'un véhicule.
- immatriculation (champ A, AB-123-CD), marque (D.1), modele (D.3, ou D.2 à défaut),
  date_premiere_immatriculation (B), titulaire (C.1, la société ou la personne au nom de qui le
  véhicule est immatriculé), energie (P.3 : essence, diesel, hybride, électrique…),
  puissance_fiscale (P.6, en chevaux fiscaux, le nombre seul).""",
    textes=(
        "immatriculation",
        "marque",
        "modele",
        "date_premiere_immatriculation",
        "titulaire",
        "energie",
        "puissance_fiscale",
    ),
    controler=_carte_grise,
    resumer=lambda lu: f"Carte grise lue : {_detail_vehicule(lu)}",
    # Le choix Acheté, LOA ou LLD ne se lit pas sur une carte grise : seul
    # le détail se remplit (AXE-993).
    champs_fiche=lambda lu: {"vehicule_detail": _detail_vehicule(lu)},
)


def _classement(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    erreurs = []
    if texte(lu, "type_document") not in TYPES_RANGES or texte(lu, "type_document") == "autre":
        erreurs.append("Nature du document non reconnue : à ranger à la main.")
    annee = texte(lu, "annee_exercice")
    if annee and not (annee.isdigit() and 2000 <= int(annee) <= 2100):
        erreurs.append(f"Exercice illisible ({annee}).")
    return erreurs


CLASSEMENT = Categorie(
    "classement",
    "Range ce document : dis ce que c'est.\n"
    f"- type_document, parmi : {DESCRIPTION_NATURES}.\n"
    """- annee_exercice : l'année de clôture de l'exercice que le document concerne (pour une pièce,
  l'année de sa date), "" si aucune.
- siren, denomination : la société concernée.""",
    textes=("type_document", "annee_exercice", "siren", "denomination"),
    controler=_classement,
    resumer=lambda lu: f"Rangé par l'OCR : {texte(lu, 'type_document')}.",
    max_tokens=2_000,
    constater_nature=False,
)

DOCUMENTS: dict[str, Categorie] = {c.cle: c for c in (KBIS, STATUTS, LETTRE_COMPTABLE, CARTE_GRISE)}
