"""Contrôles communs aux lectures OCR (AXE-943). Purs.

Chaque contrôle rend une phrase d'erreur, ou rien. Une lecture n'est
acceptée que si tous les contrôles de sa catégorie passent : un modèle peut
inventer un montant, un contrôle arithmétique ou un recoupement le voit.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date

_SIREN = re.compile(r"^\d{9}$")


def montants(lu: Mapping[str, object]) -> dict[str, int]:
    """Les montants lus, par nom ; un montant absent n'est pas listé."""
    brut = lu.get("montants")
    if not isinstance(brut, list):
        return {}
    return {
        str(m["nom"]): int(m["valeur_cts"])
        for m in brut
        if isinstance(m, dict) and "nom" in m and isinstance(m.get("valeur_cts"), int)
    }


def texte(lu: Mapping[str, object], champ: str) -> str:
    valeur = lu.get(champ)
    return valeur.strip() if isinstance(valeur, str) else ""


def liste(lu: Mapping[str, object], champ: str) -> list[dict[str, object]]:
    valeur = lu.get(champ)
    return [v for v in valeur if isinstance(v, dict)] if isinstance(valeur, list) else []


def siren_valide(siren: str) -> bool:
    """9 chiffres et la clé de Luhn (La Poste, 356000000, fait exception)."""
    if not _SIREN.match(siren):
        return False
    if siren == "356000000":
        return True
    total = 0
    for rang, chiffre in enumerate(int(c) for c in reversed(siren)):
        double = chiffre * 2 if rang % 2 else chiffre
        total += double - 9 if double > 9 else double
    return total % 10 == 0


def iban_valide(iban: str) -> bool:
    """La clé ISO 13616 (modulo 97)."""
    propre = "".join(iban.split()).upper()
    if not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$", propre):
        return False
    deplace = propre[4:] + propre[:4]
    chiffres = "".join(str(int(c, 36)) for c in deplace)
    return int(chiffres) % 97 == 1


def date_lue(valeur: str) -> date | None:
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        return None


def controle_siren(lu: Mapping[str, object], siren_fiche: str | None) -> list[str]:
    """Le SIREN lu est valide et, si la fiche en a un, c'est le même."""
    siren = texte(lu, "siren")
    if not siren:
        return []
    if not siren_valide(siren):
        return [f"SIREN lu invalide ({siren})."]
    if siren_fiche and siren != siren_fiche:
        return [f"SIREN lu {siren}, la fiche dit {siren_fiche} : document d'une autre société ?"]
    return []


def controle_date(
    lu: Mapping[str, object], champ: str, libelle: str, obligatoire: bool
) -> list[str]:
    valeur = texte(lu, champ)
    if not valeur:
        return [f"{libelle} : non lue."] if obligatoire else []
    jour = date_lue(valeur)
    if jour is None or not 2000 <= jour.year <= 2100:
        return [f"{libelle} : date illisible ({valeur})."]
    return []


def controle_present(
    lu: Mapping[str, object], champs: Sequence[str], libelles: Sequence[str]
) -> list[str]:
    return [
        f"{libelle} : non lu."
        for champ, libelle in zip(champs, libelles, strict=True)
        if not texte(lu, champ)
    ]


def euros(centimes: int) -> str:
    signe = "−" if centimes < 0 else ""
    return f"{signe}{abs(centimes) / 100:,.2f} €".replace(",", " ").replace(".", ",")
