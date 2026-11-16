"""Lire automatiquement les documents déposés sur une fiche d'import (AXE-947).

Le statut de traitement d'un document dit si ses informations ont été
compilées :
- **FEC** : lu avec le lecteur du bilan d'ouverture (AXE-804) : nombre de
  lignes, période, équilibre ;
- **QIF** (relevés exportés par la banque) : opérations, période, total ;
- les autres (PDF, images, Excel) restent « à lire » : l'OCR viendra avec
  AXE-943.

Un fichier qui ne se lit pas est « illisible », avec la raison.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from axelcompta.closing.ouverture_fec import FecRefuse, lire_fec_externe
from axelcompta.tenants.fiches_import import StatutDocument

A_LIRE = "À lire : sera lu par l'OCR (AXE-943), ou compilé à la main."


@dataclass(frozen=True, slots=True)
class OperationQif:
    jour: date
    montant_cts: int
    libelle: str


class QifIllisible(ValueError):
    pass


def _euros(centimes: int) -> str:
    signe = "−" if centimes < 0 else ""
    return f"{signe}{abs(centimes) / 100:,.2f} €".replace(",", " ").replace(".", ",")


def _date_qif(texte: str) -> date:
    """« 31/12/2025 », « 31/12/25 », « 12/31'25 » (format US de Quicken)."""
    propre = texte.strip().replace("'", "/").replace("-", "/").replace(".", "/")
    morceaux = [m.strip() for m in propre.split("/")]
    if len(morceaux) != 3 or not all(m.isdigit() for m in morceaux):
        raise QifIllisible(f"date illisible : {texte}")
    a, b, annee = (int(m) for m in morceaux)
    annee += 2000 if annee < 100 else 0
    jour, mois = (a, b) if b <= 12 else (b, a)  # jour/mois en France ; mois/jour si impossible
    try:
        return date(annee, mois, jour)
    except ValueError as exc:
        raise QifIllisible(f"date illisible : {texte}") from exc


def _montant_qif(texte: str) -> int:
    propre = texte.strip().replace(" ", "").replace(" ", "")
    if "," in propre and "." in propre:
        propre = (
            propre.replace(",", "")
            if propre.rfind(".") > propre.rfind(",")
            else propre.replace(".", "").replace(",", ".")
        )
    else:
        propre = propre.replace(",", ".")
    try:
        return int((Decimal(propre) * 100).quantize(Decimal("1")))
    except InvalidOperation as exc:
        raise QifIllisible(f"montant illisible : {texte}") from exc


def lire_qif(contenu: bytes) -> list[OperationQif]:
    """Les opérations d'un relevé QIF : D (date), T ou U (montant), P (tiers),
    M (mémo), ^ (fin d'opération)."""
    texte = (
        contenu.decode("utf-8", errors="replace")
        if contenu[:3] != b"\xef\xbb\xbf"
        else contenu[3:].decode()
    )
    if not texte.lstrip().startswith("!"):
        raise QifIllisible("ce n'est pas un fichier QIF (il commence par « !Type: »)")
    operations, courante = [], dict[str, str]()
    for ligne in texte.splitlines():
        if not ligne or ligne.startswith("!"):
            continue
        if ligne.startswith("^"):
            if "D" in courante and ("T" in courante or "U" in courante):
                libelle = " ".join(filter(None, (courante.get("P"), courante.get("M"))))
                montant = _montant_qif(courante.get("T") or courante["U"])
                operations.append(OperationQif(_date_qif(courante["D"]), montant, libelle))
            courante = {}
            continue
        courante.setdefault(ligne[0], ligne[1:].strip())
    if not operations:
        raise QifIllisible("aucune opération")
    return operations


def _fec(contenu: bytes) -> tuple[StatutDocument, str]:
    try:
        lignes = lire_fec_externe(contenu)
    except FecRefuse as exc:
        return "illisible", f"FEC illisible : {exc}"
    debit, credit = sum(x.debit for x in lignes), sum(x.credit for x in lignes)
    debut, fin = min(x.date_ecriture for x in lignes), max(x.date_ecriture for x in lignes)
    equilibre = "équilibré" if debit == credit else f"déséquilibré de {_euros(debit - credit)}"
    return "traite", (
        f"FEC lu : {len(lignes)} lignes du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}, {equilibre}."
    )


def _qif(contenu: bytes) -> tuple[StatutDocument, str]:
    try:
        operations = lire_qif(contenu)
    except (QifIllisible, UnicodeDecodeError) as exc:
        return "illisible", f"QIF illisible : {exc}."
    debut, fin = min(o.jour for o in operations), max(o.jour for o in operations)
    total = sum(o.montant_cts for o in operations)
    return "traite", (
        f"QIF lu : {len(operations)} opérations du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}, "
        f"solde des mouvements {_euros(total)}."
    )


def traiter(categorie: str, nom_fichier: str, contenu: bytes) -> tuple[StatutDocument, str]:
    """Le statut de traitement d'un document déposé, et son résumé."""
    extension = Path(nom_fichier).suffix.lower()
    if extension == ".qif":
        return _qif(contenu)
    if categorie == "fec" or (extension == ".txt" and b"JournalCode" in contenu[:500]):
        return _fec(contenu)
    return "a_traiter", A_LIRE
