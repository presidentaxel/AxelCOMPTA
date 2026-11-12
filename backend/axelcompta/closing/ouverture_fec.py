"""Bilan d'ouverture d'une société existante, depuis le FEC de son outil
précédent (AXE-804, doc 14 §1.6).

Le FEC de l'exercice clos la veille de l'ouverture dans AxeLCompta donne la
balance de clôture ; `ecriture_a_nouveaux` (le même calcul que pour un
exercice clos dans AxeLCompta) en tire l'écriture d'à-nouveaux (journal AN)
au premier jour de l'exercice ouvert.

Le lecteur est **tolérant** aux variantes réelles du format (tabulation ou
barre verticale, CR+LF ou LF, UTF-8 ou Windows-1252, Debit/Credit ou
Montant/Sens, numéros d'écriture alphanumériques par journal) : le
validateur de `filings/fec.py` contrôle **nos** exports, plus stricts.

Garde-fous contre un faux FEC, dans `analyser` :
- refus : nom de fichier hors `SIRENFECAAAAMMJJ`, SIREN qui n'est pas celui
  du dossier, clôture qui n'est pas la veille de l'ouverture, écriture ou
  balance déséquilibrée, ligne au débit et au crédit, date d'écriture hors
  de l'exercice, validation dans le futur, compte inconnu sans
  correspondance, rien à reprendre ;
- alertes (affichées, la personne qui importe décide) : pas de capital,
  pas de banque, validation antérieure à l'écriture, et le solde de banque
  à comparer au relevé.
L'empreinte du fichier et l'attestation de la personne qui importe sont
gardées (`ouvertures_importees`). Pur : ni base ni réseau.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

from .cloture_fiscale import soldes
from .ouverture import CLASSES_DE_BILAN, ecriture_a_nouveaux

COLONNES_OBLIGATOIRES = (
    "journalcode",
    "ecriturenum",
    "ecrituredate",
    "comptenum",
    "pieceref",
    "ecriturelib",
    "validdate",
)
_NOM = re.compile(r"^(\d{9})FEC(\d{8})(?:\.\w+)?$", re.IGNORECASE)
_DATE = re.compile(r"^\d{8}$")
_MONTANT = re.compile(r"^\d+(?:[.,]\d{1,2})?$")
_COMPTE_PCG = re.compile(r"^[1-7]\d{2,}$")
# Un exercice dure au plus 24 mois (premier exercice compris).
DUREE_MAX = timedelta(days=731)
ATTESTATION = (
    "J'atteste que ce fichier est le FEC de l'exercice clos le {cloture}, "
    "produit par l'outil comptable précédent de la société, sans modification."
)


class FecRefuse(SaisieInvalide):
    """Le fichier ne peut pas servir de bilan d'ouverture, avec la raison."""


@dataclass(frozen=True, slots=True)
class LigneFec:
    journal: str
    numero: str
    date_ecriture: date
    compte: str
    libelle: str
    debit: int  # centimes
    credit: int
    valide_le: date


@dataclass(frozen=True, slots=True)
class Analyse:
    """Ce que la personne qui importe voit avant de valider. Rien n'est
    écrit ; `a_nouveaux` est `None` tant qu'un refus reste."""

    empreinte: str
    siren: str
    cloture: date
    ouverture: date
    nb_lignes: int
    nb_ecritures: int
    total_debit: int
    resultat: int  # bénéfice positif, perte négative
    solde_banque: int  # 512, débit positif
    capital: int  # 101 à 108, crédit positif
    comptes_inconnus: tuple[str, ...]
    refus: tuple[str, ...]
    alertes: tuple[str, ...]
    a_nouveaux: Ecriture | None

    @property
    def attestation(self) -> str:
        return ATTESTATION.format(cloture=self.cloture.strftime("%d/%m/%Y"))


def empreinte(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _texte(contenu: bytes) -> str:
    for encodage in ("utf-8-sig", "cp1252"):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    raise FecRefuse("Le fichier n'est pas un texte lisible (UTF-8 ou Windows).")


def _date(valeur: str, zone: str, numero_ligne: int) -> date:
    if not _DATE.match(valeur):
        raise FecRefuse(f"Ligne {numero_ligne} : {zone} n'est pas une date AAAAMMJJ.")
    try:
        return date(int(valeur[:4]), int(valeur[4:6]), int(valeur[6:]))
    except ValueError as erreur:
        raise FecRefuse(f"Ligne {numero_ligne} : {zone} n'est pas une date valide.") from erreur


def _centimes(valeur: str, numero_ligne: int) -> int:
    propre = valeur.strip().replace(" ", "") or "0"
    if not _MONTANT.match(propre):
        raise FecRefuse(f"Ligne {numero_ligne} : montant illisible ({valeur}).")
    entier, _, fraction = propre.replace(",", ".").partition(".")
    return int(entier) * 100 + int(fraction.ljust(2, "0"))


def _montants(zones: Mapping[str, str], numero_ligne: int) -> tuple[int, int]:
    if "debit" in zones and "credit" in zones:
        return _centimes(zones["debit"], numero_ligne), _centimes(zones["credit"], numero_ligne)
    montant = _centimes(zones.get("montant", ""), numero_ligne)
    sens = zones.get("sens", "").strip().upper()
    if sens in ("D", "+1", "1"):
        return montant, 0
    if sens in ("C", "-1"):
        return 0, montant
    raise FecRefuse(f"Ligne {numero_ligne} : ni Debit/Credit ni Montant/Sens lisibles.")


def lire_fec_externe(contenu: bytes) -> tuple[LigneFec, ...]:
    """Les lignes du FEC, ou `FecRefuse` avec la raison."""
    texte = _texte(contenu).replace("\r\n", "\n").strip("\n")
    lignes = texte.split("\n")
    if not lignes or not lignes[0]:
        raise FecRefuse("Le fichier est vide.")
    separateur = "\t" if "\t" in lignes[0] else "|"
    entete = [c.strip().lower() for c in lignes[0].split(separateur)]
    manquantes = [c for c in COLONNES_OBLIGATOIRES if c not in entete]
    if manquantes:
        raise FecRefuse("En-tête FEC incomplet : il manque " + ", ".join(manquantes) + ".")
    lues = []
    for rang, ligne in enumerate(lignes[1:], start=2):
        valeurs = ligne.split(separateur)
        if len(valeurs) != len(entete):
            raise FecRefuse(f"Ligne {rang} : {len(valeurs)} zones au lieu de {len(entete)}.")
        zones = dict(zip(entete, (v.strip() for v in valeurs), strict=True))
        if any(not zones[c] for c in COLONNES_OBLIGATOIRES):
            raise FecRefuse(f"Ligne {rang} : une zone obligatoire est vide.")
        debit, credit = _montants(zones, rang)
        if debit and credit:
            raise FecRefuse(f"Ligne {rang} : montant au débit et au crédit à la fois.")
        lues.append(
            LigneFec(
                journal=zones["journalcode"],
                numero=zones["ecriturenum"],
                date_ecriture=_date(zones["ecrituredate"], "EcritureDate", rang),
                compte=zones["comptenum"],
                libelle=zones.get("comptelib", ""),
                debit=debit,
                credit=credit,
                valide_le=_date(zones["validdate"], "ValidDate", rang),
            )
        )
    if not lues:
        raise FecRefuse("Le fichier n'a aucune écriture.")
    return tuple(lues)


def lire_nom(nom_fichier: str) -> tuple[str, date]:
    """`123456789FEC20251231.txt` → (SIREN, date de clôture)."""
    trouve = _NOM.match(nom_fichier.strip().rsplit("/", 1)[-1])
    if trouve is None:
        raise FecRefuse(
            "Le nom du fichier doit être SIRENFECAAAAMMJJ (par exemple 123456789FEC20251231.txt), "
            "comme l'exige l'article A.47 A-1 : renommé, il n'est plus un FEC."
        )
    return trouve.group(1), _date(trouve.group(2), "La date du nom", 0)


def verifier_correspondance(correspondance: Mapping[str, str]) -> None:
    for source, cible in correspondance.items():
        if not _COMPTE_PCG.match(cible):
            raise FecRefuse(f"Compte {source} : {cible} n'est pas un compte du plan comptable.")


def _comptes_pcg(
    lignes: tuple[LigneFec, ...], correspondance: Mapping[str, str]
) -> tuple[tuple[LigneFec, ...], tuple[str, ...]]:
    inconnus = sorted(
        {
            lg.compte
            for lg in lignes
            if not _COMPTE_PCG.match(lg.compte) and lg.compte not in correspondance
        }
    )
    traduites = tuple(
        LigneFec(
            lg.journal,
            lg.numero,
            lg.date_ecriture,
            correspondance.get(lg.compte, lg.compte),
            lg.libelle,
            lg.debit,
            lg.credit,
            lg.valide_le,
        )
        for lg in lignes
    )
    return traduites, tuple(inconnus)


def _ecritures(dossier_id: DossierId, lignes: tuple[LigneFec, ...]) -> tuple[Ecriture, ...]:
    groupes: dict[tuple[str, str], list[LigneFec]] = {}
    for lg in lignes:
        groupes.setdefault((lg.journal, lg.numero), []).append(lg)
    ecritures = []
    for (journal, numero), membres in groupes.items():
        lignes_ecriture = tuple(
            LigneEcriture(
                compte=lg.compte,
                sens=Sens.DEBIT if lg.debit else Sens.CREDIT,
                montant=Money(lg.debit or lg.credit),
            )
            for lg in membres
            if lg.debit or lg.credit
        )
        if lignes_ecriture:
            ecritures.append(
                Ecriture(
                    id=EcritureId(f"{dossier_id}:fec:{journal}:{numero}"),
                    dossier_id=dossier_id,
                    journal=Journal.OD,
                    date=membres[0].date_ecriture,
                    libelle=f"FEC {journal} {numero}",
                    reference_piece=None,
                    lignes=lignes_ecriture,
                )
            )
    return tuple(ecritures)


def _desequilibres(lignes: tuple[LigneFec, ...]) -> list[str]:
    totaux: dict[tuple[str, str], int] = {}
    for lg in lignes:
        cle = (lg.journal, lg.numero)
        totaux[cle] = totaux.get(cle, 0) + lg.debit - lg.credit
    fausses = [f"{j} {n}" for (j, n), ecart in totaux.items() if ecart]
    if not fausses:
        return []
    exemple = ", ".join(fausses[:3]) + ("…" if len(fausses) > 3 else "")
    return [f"{len(fausses)} écriture(s) déséquilibrée(s) : {exemple}."]


def _controles_dates(
    lignes: tuple[LigneFec, ...], cloture: date, aujourd_hui: date
) -> tuple[list[str], list[str]]:
    refus, alertes = [], []
    if any(lg.date_ecriture > cloture for lg in lignes):
        refus.append(f"Des écritures sont datées après la clôture du {cloture:%d/%m/%Y}.")
    if any(lg.date_ecriture < cloture - DUREE_MAX for lg in lignes):
        refus.append(
            "Des écritures sont antérieures à l'exercice (plus de 24 mois avant la clôture)."
        )
    if any(lg.valide_le > aujourd_hui for lg in lignes):
        refus.append("Des écritures sont validées à une date future : le fichier n'est pas fiable.")
    if any(lg.valide_le < lg.date_ecriture for lg in lignes):
        alertes.append(
            "Des écritures ont été validées avant leur date : vérifiez l'origine du fichier."
        )
    return refus, alertes


def _controles_dossier(
    siren: str, cloture: date, siren_dossier: str | None, ouverture: date
) -> list[str]:
    refus = []
    if siren_dossier is not None and siren != siren_dossier:
        refus.append(f"Ce FEC est celui du SIREN {siren}, pas de cette société ({siren_dossier}).")
    if cloture != ouverture - timedelta(days=1):
        refus.append(
            f"Ce FEC est clos le {cloture:%d/%m/%Y} ; il faut celui de l'exercice clos la veille "
            f"de l'ouverture dans AxeLCompta, le {ouverture - timedelta(days=1):%d/%m/%Y}."
        )
    return refus


def analyser(
    contenu: bytes,
    nom_fichier: str,
    dossier_id: DossierId,
    siren_dossier: str | None,
    ouverture: date,
    correspondance: Mapping[str, str],
    aujourd_hui: date,
) -> Analyse:
    """Lit et contrôle le FEC, et prépare l'écriture d'à-nouveaux. Lève
    `FecRefuse` si le fichier n'est pas lisible ; sinon rend les refus et
    les alertes pour qu'ils s'affichent tous d'un coup."""
    siren, cloture = lire_nom(nom_fichier)
    verifier_correspondance(correspondance)
    lignes, inconnus = _comptes_pcg(lire_fec_externe(contenu), correspondance)
    refus = _controles_dossier(siren, cloture, siren_dossier, ouverture) + _desequilibres(lignes)
    refus_dates, alertes = _controles_dates(lignes, cloture, aujourd_hui)
    refus += refus_dates
    if inconnus:
        refus.append(
            "Comptes à faire correspondre au plan comptable : " + ", ".join(inconnus) + "."
        )
    ecritures = _ecritures(dossier_id, lignes)
    balance = soldes(ecritures)
    if not any(c.startswith(CLASSES_DE_BILAN) and s for c, s in balance.items()):
        refus.append(
            "Aucun solde de bilan à reprendre : ce n'est pas le FEC d'une société en activité."
        )
    capital = -sum(s for c, s in balance.items() if c.startswith("10"))
    banque = sum(s for c, s in balance.items() if c.startswith("512"))
    if capital <= 0:
        alertes.append("Aucun capital (comptes 101 à 108) : vérifiez que le FEC est complet.")
    if not any(c.startswith("512") for c in balance):
        alertes.append("Aucun compte de banque (512) : vérifiez que le FEC est complet.")
    else:
        alertes.append(
            f"Solde de banque au {cloture:%d/%m/%Y} : {_euros(banque)}. "
            "Comparez-le à votre relevé bancaire de cette date."
        )
    a_nouveaux = None if refus else ecriture_a_nouveaux(dossier_id, ecritures, ouverture)
    return Analyse(
        empreinte=empreinte(contenu),
        siren=siren,
        cloture=cloture,
        ouverture=ouverture,
        nb_lignes=len(lignes),
        nb_ecritures=len(ecritures),
        total_debit=sum(lg.debit for lg in lignes),
        resultat=-sum(s for c, s in balance.items() if c.startswith(("6", "7"))),
        solde_banque=banque,
        capital=capital,
        comptes_inconnus=inconnus,
        refus=tuple(refus),
        alertes=tuple(alertes),
        a_nouveaux=a_nouveaux,
    )


def _euros(centimes: int) -> str:
    signe = "-" if centimes < 0 else ""
    reste = abs(centimes)
    return f"{signe}{reste // 100:,}".replace(",", " ") + f",{reste % 100:02d} €"
