"""Les champs en liste d'une fiche d'import : associés et comptes Rollee (AXE-946). Pur.

Ils sont rangés en JSON dans les champs de la fiche, comme les autres
valeurs (texte). Une valeur illisible (saisie libre d'avant AXE-946) se lit
comme une liste vide, sans erreur : elle reste en base, rien ne s'efface.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

from axelcompta.core.errors import SaisieInvalide

FONCTIONS = {
    "president": "Président",
    "gerant": "Gérant",
    "directeur_general": "Directeur général",
    "associe": "Associé",
    "dirigeant": "Dirigeant",
}
LIGNES_MAX = 20


@dataclass(frozen=True, slots=True)
class Associe:
    prenom: str
    nom: str
    fonction: str  # une clé de FONCTIONS
    pourcentage: str  # « 100 », « 33.33 », ou « » si inconnu


@dataclass(frozen=True, slots=True)
class CompteRolleeRetenu:
    rollee_user_id: str
    nom: str
    plateformes: tuple[str, ...]


def _liste(texte: str, libelle: str) -> list[object]:
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise SaisieInvalide(f"{libelle} : liste illisible.") from exc
    if not isinstance(donnees, list) or len(donnees) > LIGNES_MAX:
        raise SaisieInvalide(f"{libelle} : {LIGNES_MAX} lignes au plus.")
    return donnees


def _texte(ligne: dict[str, object], cle: str) -> str:
    valeur = ligne.get(cle)
    return " ".join(valeur.split()) if isinstance(valeur, str) else ""


def _pourcentage(texte: str) -> str:
    if not texte:
        return ""
    try:
        valeur = Decimal(texte.replace(",", ".").replace("%", "").strip())
    except InvalidOperation as exc:
        raise SaisieInvalide("Part du capital : un pourcentage, par exemple 50.") from exc
    if not 0 <= valeur <= 100:
        raise SaisieInvalide("Part du capital : entre 0 et 100 %.")
    return str(valeur.quantize(Decimal("0.01")).normalize())


def _associe(ligne: object) -> Associe:
    if not isinstance(ligne, dict):
        raise SaisieInvalide("Associés : ligne illisible.")
    associe = Associe(
        prenom=_texte(ligne, "prenom"),
        nom=_texte(ligne, "nom"),
        fonction=_texte(ligne, "fonction") or "associe",
        pourcentage=_pourcentage(_texte(ligne, "pourcentage")),
    )
    if not associe.nom:
        raise SaisieInvalide("Associés : le nom de chaque associé est attendu.")
    if associe.fonction not in FONCTIONS:
        raise SaisieInvalide("Associés : fonction inconnue.")
    return associe


def ranger_associes(texte: str) -> str:
    """La liste validée, en JSON ; refuse un total de parts au-delà de 100 %."""
    associes = [_associe(ligne) for ligne in _liste(texte, "Associés")]
    if total_parts(associes) > 100:
        raise SaisieInvalide("Associés : le total des parts dépasse 100 %.")
    return json.dumps([asdict(a) for a in associes], ensure_ascii=False)


def lire_associes(texte: str | None) -> list[Associe]:
    try:
        return [_associe(ligne) for ligne in json.loads(texte or "[]")]
    except (json.JSONDecodeError, SaisieInvalide, TypeError):
        return []


def total_parts(associes: list[Associe]) -> Decimal:
    return sum((Decimal(a.pourcentage) for a in associes if a.pourcentage), Decimal(0))


def _compte(ligne: object) -> CompteRolleeRetenu:
    if not isinstance(ligne, dict) or not _texte(ligne, "rollee_user_id"):
        raise SaisieInvalide("Comptes Rollee : compte illisible.")
    plateformes = ligne.get("plateformes")
    return CompteRolleeRetenu(
        rollee_user_id=_texte(ligne, "rollee_user_id"),
        nom=_texte(ligne, "nom"),
        plateformes=tuple(p for p in plateformes if isinstance(p, str))
        if isinstance(plateformes, list)
        else (),
    )


def ranger_comptes_rollee(texte: str) -> str:
    """Les comptes retenus, sans doublon, en JSON."""
    comptes = {c.rollee_user_id: c for c in map(_compte, _liste(texte, "Comptes Rollee"))}
    return json.dumps(
        [{**asdict(c), "plateformes": list(c.plateformes)} for c in comptes.values()],
        ensure_ascii=False,
    )


def associes_du_registre(personnes: list[tuple[str, str]], forme: str | None) -> str:
    """Les dirigeants lus au RNE, en associés à compléter (fonction d'après la
    forme, part inconnue)."""
    fonction = {"SASU": "president", "SAS": "president", "EURL": "gerant", "SARL": "gerant"}
    lignes = [
        Associe(prenom.split(" ")[0], nom, fonction.get(forme or "", "dirigeant"), "")
        for nom, prenom in personnes
    ]
    return json.dumps([asdict(a) for a in lignes], ensure_ascii=False) if lignes else ""
