"""OCR de la section Documents administratifs, et classement des « Autre »
(AXE-943). Pur.

* Kbis : SIREN, dénomination, forme, capital, siège, immatriculation.
* Statuts : forme, capital, associés et leurs parts.
* Lettre de l'ancien expert-comptable : le cabinet et son contact.
* Un document rangé en « Autre » : sa nature et son exercice, pour le ranger
  dans sa catégorie ; il est ensuite lu comme tel.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from axelcompta.core.errors import SaisieInvalide
from axelcompta.tenants.fiches_import_listes import ranger_associes

from .categories import Categorie, Contexte
from .controles import controle_date, controle_siren, entier, euros, liste, montants, texte

TYPES_RANGES = (
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


def _associes(lu: Mapping[str, object]) -> dict[str, str]:
    """AXE-990 : les associés des statuts et leur part du capital, au format
    de la fiche ; rien si la liste ne se valide pas (total au-delà de 100 %)."""
    associes = [a for a in liste(lu, "associes") if str(a.get("nom") or "").strip()]
    parts = [entier(a.get("parts")) for a in associes]
    total = montants(lu).get("nombre_parts_total") or sum(parts)
    if not associes:
        return {}
    lignes = [
        {
            "prenom": str(a.get("prenom") or "").strip(),
            "nom": str(a.get("nom") or "").strip(),
            "fonction": "associe",
            "pourcentage": f"{p * 100 / total:.2f}" if total else "",
        }
        for a, p in zip(associes, parts, strict=True)
    ]
    try:
        return {"associes": ranger_associes(json.dumps(lignes, ensure_ascii=False))}
    except SaisieInvalide:
        return {}


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
    champs_fiche=lambda lu: {**_champs_identite(lu, ()), **_associes(lu)},
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
    """Range ce document : dis ce que c'est.
- type_document, parmi : liasse (liasse fiscale 2033, 2050, 2065, 2031, ou leur synthèse),
  comptes_annuels (bilan et compte de résultat), balance, grand_livre, declaration_tva (CA3, CA12,
  3517), declaration_is (2571, 2572, relevé d'acompte ou de solde), accuse_reception (accusé de
  dépôt d'une déclaration), paiement_impot (ordre ou avis de paiement d'un impôt), piece (facture,
  reçu, ticket, note de frais), emprunt (tableau d'amortissement, échéancier de prêt),
  releve_bancaire (relevé de compte), rib, releve_plateforme (récapitulatif ou relevé Uber, Bolt,
  Heetch, Free Now…), kbis, statuts, lettre_comptable (courrier de l'ancien expert-comptable),
  autre.
- annee_exercice : l'année de clôture de l'exercice que le document concerne (pour une pièce,
  l'année de sa date), "" si aucune.
- siren, denomination : la société concernée.""",
    textes=("type_document", "annee_exercice", "siren", "denomination"),
    controler=_classement,
    resumer=lambda lu: f"Rangé par l'OCR : {texte(lu, 'type_document')}.",
    max_tokens=2_000,
)

DOCUMENTS: dict[str, Categorie] = {c.cle: c for c in (KBIS, STATUTS, LETTRE_COMPTABLE)}
