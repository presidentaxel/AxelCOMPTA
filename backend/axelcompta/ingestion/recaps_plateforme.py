"""Lire un récapitulatif de plateforme déposé sur une fiche d'import (AXE-987).

Uber envoie chaque mois un « Récapitulatif fiscal » en PDF texte : pas
besoin d'OCR, le texte se lit. Deux formats vus :

* **jusqu'à octobre 2025** : « Récapitulatif fiscal de la période 2025/9 »,
  montants « €9,587.94 » ; le premier « Total » est celui des courses
  (péages compris), le second celui des autres revenus (divers, primes) ;
* **depuis novembre 2025** : « 01-30 Novembre 2025 », montants
  « 5 085,68 € » ; « Revenus issus de courses », « … d'autres services »,
  « Frais de service Uber », « Montant total ».

Dans les deux, courses (frais Uber compris) + autres revenus − frais de
service Uber = montant net, au centime : c'est le contrôle. Un document
qui ne tombe pas juste, ou qu'on ne reconnaît pas, reste « à lire » (OCR,
AXE-943). Pur : prend le texte, pas le PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MOIS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}
_EURO_US = r"€\s?([\d,]+\.\d{2})"
_EURO_FR = r"(\d[\d  ]*,\d{2})\s?€"


@dataclass(frozen=True, slots=True)
class RecapPlateforme:
    plateforme: str
    mois: str  # « 2025-11 »
    siren: str | None
    courses_cts: int  # frais de service de la plateforme compris
    autres_cts: int  # primes, parrainages, divers
    frais_cts: int  # frais de service de la plateforme
    net_cts: int

    @property
    def juste(self) -> bool:
        return self.courses_cts + self.autres_cts - self.frais_cts == self.net_cts

    def donnees(self) -> dict[str, object]:
        return {
            "type": "recap_plateforme",
            "plateforme": self.plateforme,
            "mois": self.mois,
            "siren": self.siren,
            "courses_cts": self.courses_cts,
            "autres_cts": self.autres_cts,
            "frais_cts": self.frais_cts,
            "net_cts": self.net_cts,
        }


def _cts(texte: str) -> int:
    propre = texte.replace(" ", "").replace(" ", "").replace("\xa0", "")
    propre = propre.replace(",", "") if "." in propre else propre.replace(",", ".")
    try:
        return int((Decimal(propre) * 100).quantize(Decimal("1")))
    except InvalidOperation as exc:
        raise ValueError(f"montant illisible : {texte}") from exc


def _siren(texte: str) -> str | None:
    lu = re.search(r"SIREN(?:/SIRET)?\s*:?\s*(\d{9})", texte)
    return lu.group(1) if lu else None


def _ancien_format(texte: str) -> RecapPlateforme | None:
    periode = re.search(r"période (\d{4})/(\d{1,2})", texte)
    net = re.search(r"Total des revenus nets \(hors frais de service et TVA\) " + _EURO_US, texte)
    frais = re.search(r"Frais de service pour les courses Uber " + _EURO_US, texte)
    totaux = re.findall(r"Total " + _EURO_US, texte)
    if not (periode and net and frais and totaux):
        return None
    return RecapPlateforme(
        "uber",
        f"{periode.group(1)}-{int(periode.group(2)):02d}",
        _siren(texte),
        _cts(totaux[0]),
        _cts(totaux[1]) if len(totaux) > 1 else 0,
        _cts(frais.group(1)),
        _cts(net.group(1)),
    )


def _nouveau_format(texte: str) -> RecapPlateforme | None:
    periode = re.search(r"\d{2}-\d{2} ([A-Za-zéûÉ]+) (\d{4})", texte)
    courses = re.search(r"Revenus issus de courses " + _EURO_FR, texte)
    autres = re.search(r"Revenus issus d'autres services " + _EURO_FR, texte)
    frais = re.search(r"Frais de service Uber " + _EURO_FR, texte)
    net = re.search(r"Montant total " + _EURO_FR, texte)
    if not (periode and courses and frais and net):
        return None
    mois = MOIS.get(periode.group(1).lower())
    if mois is None:
        return None
    return RecapPlateforme(
        "uber",
        f"{periode.group(2)}-{mois:02d}",
        _siren(texte),
        _cts(courses.group(1)),
        _cts(autres.group(1)) if autres else 0,
        _cts(frais.group(1)),
        _cts(net.group(1)),
    )


def lire_recap(texte_brut: str) -> RecapPlateforme | None:
    """Le récapitulatif mensuel Uber lu dans le texte du PDF ; `None` si ce
    n'en est pas un (ou une autre plateforme, pas encore lue)."""
    texte = re.sub(r"\s+", " ", texte_brut)
    if "Uber B.V." not in texte or "capitulatif fiscal" not in texte:
        return None
    try:
        return _nouveau_format(texte) or _ancien_format(texte)
    except ValueError:
        return None


def plateforme_du_nom(nom_fichier: str) -> str | None:
    """La plateforme que dit le nom d'un fichier (« uber_monthly_2025_9.pdf »)."""
    nom = nom_fichier.lower()
    for plateforme in ("uber", "bolt", "heetch", "freenow", "free now", "allocab"):
        if plateforme in nom:
            return plateforme.replace(" ", "")
    return None
