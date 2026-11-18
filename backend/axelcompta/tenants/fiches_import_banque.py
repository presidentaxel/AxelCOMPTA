"""Ce que le gestionnaire dit des comptes de banque d'une fiche (AXE-973). Pur.

Deux réglages, gardés dans les champs de la fiche (JSON) :

- **rattachements** (`banque_rattachements`) : le compte d'un FEC
  (`fec:5120020`) ou d'un relevé (`doc:<id>`) est en fait un compte déjà
  connu (`digi:67499359`, la Bred ; ou le compte d'un autre FEC). Ses
  opérations et ses soldes rejoignent ceux de ce compte ;
- **soldes saisis** (`banque_soldes`) : un solde lu sur un relevé PDF
  (« Solde au 30/09/2025 : 1 367,16 € »), en attendant que l'OCR les lise
  (AXE-943). Un solde est celui de fin de journée.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from axelcompta.core.errors import SaisieInvalide

CHAMP_RATTACHEMENTS = "banque_rattachements"
CHAMP_SOLDES = "banque_soldes"
SOLDES_MAX = 200
_CLE = re.compile(r"^(digi|fec|doc):[\w.-]{1,64}$")


@dataclass(frozen=True, slots=True)
class SoldeSaisi:
    compte: str
    le: date
    cts: int
    source: str


def rattachements(champs: Mapping[str, str]) -> dict[str, str]:
    try:
        lus = json.loads(champs.get(CHAMP_RATTACHEMENTS) or "{}")
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in lus.items()} if isinstance(lus, dict) else {}


def racine(cle: str, liens: Mapping[str, str]) -> str:
    """Le compte auquel `cle` est rattachée, de proche en proche (sans
    boucle)."""
    vues = {cle}
    while cle in liens and liens[cle] not in vues:
        cle = liens[cle]
        vues.add(cle)
    return cle


def rattacher(champs: Mapping[str, str], source: str, cible: str | None) -> dict[str, str]:
    """Les champs avec `source` rattachée à `cible` (`None` : détachée).
    Refuse une clé inconnue, un compte rattaché à lui-même ou une boucle."""
    if not _CLE.match(source) or (cible is not None and not _CLE.match(cible)):
        raise SaisieInvalide("Compte de banque inconnu.")
    if source.startswith("digi:"):
        raise SaisieInvalide("Un compte Digifactory ne se rattache pas : c'est la référence.")
    liens = rattachements(champs)
    if cible is None:
        liens.pop(source, None)
    else:
        if racine(cible, liens) == source or cible == source:
            raise SaisieInvalide("Ce rattachement ferait une boucle.")
        liens[source] = cible
    return {**champs, CHAMP_RATTACHEMENTS: json.dumps(liens, sort_keys=True)}


def soldes_saisis(champs: Mapping[str, str]) -> list[SoldeSaisi]:
    try:
        lus = json.loads(champs.get(CHAMP_SOLDES) or "[]")
    except ValueError:
        return []
    soldes = []
    for s in lus if isinstance(lus, list) else []:
        try:
            soldes.append(
                SoldeSaisi(
                    str(s["compte"]), date.fromisoformat(s["le"]), int(s["cts"]), str(s["source"])
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return soldes


def _centimes(texte: str) -> int:
    propre = texte.strip().replace(" ", "").replace("\xa0", "").replace(" ", "")
    propre = propre.replace("€", "").replace("−", "-")
    if "," in propre and "." in propre:
        propre = (
            propre.replace(".", "")
            if propre.rfind(",") > propre.rfind(".")
            else propre.replace(",", "")
        )
    propre = propre.replace(",", ".")
    try:
        return int((Decimal(propre) * 100).quantize(Decimal("1")))
    except InvalidOperation as exc:
        raise SaisieInvalide("Montant : par exemple 1 367,16 ou -250,00.") from exc


def ajouter_solde(
    champs: Mapping[str, str], compte: str, le: date, montant: str, source: str, aujourd_hui: date
) -> dict[str, str]:
    """Les champs avec un solde de plus, lu sur un relevé."""
    if not _CLE.match(compte):
        raise SaisieInvalide("Compte de banque inconnu.")
    if le > aujourd_hui:
        raise SaisieInvalide("Un solde se lit sur un relevé passé, pas à une date future.")
    soldes = soldes_saisis(champs)
    if len(soldes) >= SOLDES_MAX:
        raise SaisieInvalide(f"Au plus {SOLDES_MAX} soldes saisis par fiche.")
    origine = source.strip()[:80] or "Relevé"
    soldes.append(SoldeSaisi(compte, le, _centimes(montant), f"{origine} (saisi)"))
    return {**champs, CHAMP_SOLDES: _json(soldes)}


def retirer_solde(champs: Mapping[str, str], rang: int) -> dict[str, str]:
    soldes = soldes_saisis(champs)
    if not 0 <= rang < len(soldes):
        raise SaisieInvalide("Solde introuvable.")
    del soldes[rang]
    return {**champs, CHAMP_SOLDES: _json(soldes)}


def _json(soldes: list[SoldeSaisi]) -> str:
    return json.dumps(
        [
            {"compte": s.compte, "le": s.le.isoformat(), "cts": s.cts, "source": s.source}
            for s in soldes
        ]
    )
