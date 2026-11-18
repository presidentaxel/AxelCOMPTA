"""Lire automatiquement les documents déposés sur une fiche d'import (AXE-947,
AXE-970).

Le statut de traitement d'un document dit si ses informations ont été
compilées :
- **FEC** (reconnu à son contenu, quel que soit son nom ou son extension) :
  lu avec le lecteur du bilan d'ouverture (AXE-804). Le résumé dit période,
  nombre de lignes et équilibre ; les **données** gardent SIREN, clôture,
  journaux, résultat et le solde de chaque compte, pour la reprise ;
- **QIF** (relevés exportés par la banque) : opérations, période, total ;
- les autres (PDF, images, Excel) restent « à lire » : l'OCR viendra avec
  AXE-943.

Un fichier qui ne se lit pas est « illisible », avec la raison.

AXE-970 : `classer` devine la catégorie d'un fichier déposé en vrac sur un
exercice (nom, puis contenu) ; `deplier` sort chaque fichier d'une archive
zip, zips imbriqués compris (archive fiscale OneUp : un zip signé qui en
contient un autre), avec des plafonds contre une archive piégée.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pypdf import PdfReader

from axelcompta.closing.ouverture_fec import FecRefuse, LigneFec, lire_fec_externe, lire_nom
from axelcompta.ingestion.recaps_plateforme import lire_recap
from axelcompta.tenants.fiches_import import StatutDocument

A_LIRE = "À lire : sera lu par l'OCR (AXE-943), ou compilé à la main."
IMPRESSION_FEC = "Impression PDF du FEC : c'est le fichier texte du FEC qui se lit."


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


@dataclass(frozen=True, slots=True)
class Traitement:
    """Ce qui a été tiré d'un document : statut, phrase pour l'écran, données
    structurées (FEC) et l'exercice qu'il dit (année de clôture du FEC)."""

    statut: StatutDocument
    resume: str
    donnees: dict[str, object] | None = None
    exercice: int | None = None


def est_fec(contenu: bytes) -> bool:
    """Un FEC se reconnaît à son en-tête, pas à son nom (OneUp le nomme
    avec le SIRET et l'extension .csv)."""
    tete = contenu[:600].lstrip(b"\xef\xbb\xbf").lower()
    return tete.startswith(b"journalcode") and (b"\t" in tete or b"|" in tete)


def _donnees_fec(lignes: tuple[LigneFec, ...], nom: str) -> dict[str, object]:
    soldes: dict[str, int] = {}
    for lg in lignes:
        soldes[lg.compte] = soldes.get(lg.compte, 0) + lg.debit - lg.credit
    try:
        siren, cloture = lire_nom(nom)
    except FecRefuse:
        siren, cloture = None, None
    return {
        "type": "fec",
        "siren": siren,
        "cloture": cloture.isoformat() if cloture else None,
        "debut": min(x.date_ecriture for x in lignes).isoformat(),
        "fin": max(x.date_ecriture for x in lignes).isoformat(),
        "lignes": len(lignes),
        "ecritures": len({(x.journal, x.numero) for x in lignes}),
        "journaux": sorted({x.journal for x in lignes}),
        "total_debit_cts": sum(x.debit for x in lignes),
        "equilibre": sum(x.debit - x.credit for x in lignes) == 0,
        "resultat_cts": -sum(s for c, s in soldes.items() if c.startswith(("6", "7"))),
        "soldes_cts": {c: s for c, s in sorted(soldes.items()) if s},
        "banque": _banque_fec(lignes),
        "immobilisations": _immobilisations_fec(lignes),
    }


def _immobilisations_fec(lignes: tuple[LigneFec, ...]) -> dict[str, dict[str, object]]:
    """AXE-976 : par compte d'immobilisation (20…, 21…), son libellé et la
    date de sa première entrée hors à-nouveaux (l'achat, s'il a eu lieu dans
    l'exercice) ; le solde est déjà dans `soldes_cts`."""
    immobilisations: dict[str, dict[str, object]] = {}
    for lg in lignes:
        if not lg.compte.startswith(("20", "21")) or lg.debit <= 0:
            continue
        if lg.journal.upper() in JOURNAUX_A_NOUVEAUX:
            continue
        deja = immobilisations.get(lg.compte)
        if deja is None or str(deja["achat_le"]) > lg.date_ecriture.isoformat():
            immobilisations[lg.compte] = {
                "libelle": lg.libelle,
                "achat_le": lg.date_ecriture.isoformat(),
            }
    return immobilisations


JOURNAUX_A_NOUVEAUX = frozenset({"AN", "RAN", "ANO", "ANX"})


def _banque_fec(lignes: tuple[LigneFec, ...]) -> dict[str, object]:
    """AXE-973 : par compte de banque (512…), son libellé, le solde
    d'ouverture lu dans les à-nouveaux (en fin de veille de leur date) et
    chaque mouvement de l'exercice (jour, montant signé), pour vérifier la
    couverture bancaire par le solde."""
    banque: dict[str, dict[str, object]] = {}
    for lg in lignes:
        if not lg.compte.startswith("512"):
            continue
        compte = banque.setdefault(
            lg.compte,
            {"libelle": lg.libelle, "ouverture_le": None, "ouverture_cts": None, "operations": []},
        )
        montant = lg.debit - lg.credit
        if lg.journal.upper() in JOURNAUX_A_NOUVEAUX:
            veille = (lg.date_ecriture - timedelta(days=1)).isoformat()
            compte["ouverture_le"] = veille
            compte["ouverture_cts"] = int(str(compte["ouverture_cts"] or 0)) + montant
        else:
            operations = compte["operations"]
            assert isinstance(operations, list)
            operations.append([lg.date_ecriture.isoformat(), montant])
    return dict(banque)


def _fec(contenu: bytes, nom: str, siren: str | None) -> Traitement:
    try:
        lignes = lire_fec_externe(contenu)
    except FecRefuse as exc:
        return Traitement("illisible", f"FEC illisible : {exc}")
    except UnicodeDecodeError:
        return Traitement("illisible", "FEC illisible : ce n'est pas un fichier texte.")
    donnees = _donnees_fec(lignes, nom)
    debit, credit = sum(x.debit for x in lignes), sum(x.credit for x in lignes)
    debut, fin = min(x.date_ecriture for x in lignes), max(x.date_ecriture for x in lignes)
    equilibre = "équilibré" if debit == credit else f"déséquilibré de {_euros(debit - credit)}"
    phrase = (
        f"FEC lu : {len(lignes)} lignes du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}, {equilibre}, "
        f"résultat {_euros(int(str(donnees['resultat_cts'])))}."
    )
    cloture = donnees["cloture"]
    if cloture:
        phrase += f" Clos le {date.fromisoformat(str(cloture)):%d/%m/%Y}."
    if siren and donnees["siren"] and donnees["siren"] != siren:
        phrase += f" ⚠ SIREN {donnees['siren']} dans le nom, pas celui de la fiche ({siren})."
    exercice = date.fromisoformat(str(cloture)).year if cloture else fin.year
    return Traitement("traite", phrase, donnees, exercice)


def _qif(contenu: bytes) -> Traitement:
    try:
        operations = lire_qif(contenu)
    except (QifIllisible, UnicodeDecodeError) as exc:
        return Traitement("illisible", f"QIF illisible : {exc}.")
    debut, fin = min(o.jour for o in operations), max(o.jour for o in operations)
    total = sum(o.montant_cts for o in operations)
    return Traitement(
        "traite",
        f"QIF lu : {len(operations)} opérations du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}, "
        f"solde des mouvements {_euros(total)}.",
        {
            "type": "qif",
            "debut": debut.isoformat(),
            "fin": fin.isoformat(),
            "operations": len(operations),
            "solde_mouvements_cts": total,
            # AXE-973 : chaque mouvement, pour la couverture bancaire.
            "mouvements": [[o.jour.isoformat(), o.montant_cts] for o in operations],
        },
        fin.year,
    )


def traiter(
    categorie: str, nom_fichier: str, contenu: bytes, siren: str | None = None
) -> Traitement:
    """Le statut de traitement d'un document déposé, son résumé et ce qui en
    a été lu. `siren` : celui de la fiche, pour signaler un FEC d'une autre
    société."""
    extension = Path(nom_fichier).suffix.lower()
    if extension == ".qif":
        return _qif(contenu)
    if est_fec(contenu) or (categorie == "fec" and extension in (".txt", ".csv")):
        return _fec(contenu, Path(nom_fichier).name, siren)
    if categorie == "fec" and contenu.startswith(b"%PDF"):
        return Traitement("a_traiter", IMPRESSION_FEC, {"type": "impression_fec"})
    if categorie == "releve_plateforme" and contenu.startswith(b"%PDF"):
        return _recap_plateforme(contenu)
    if categorie == "archive" or extension == ".zip":
        return Traitement("traite", "Archive gardée intacte ; ses fichiers sont rangés à part.")
    return Traitement("a_traiter", A_LIRE)


MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _recap_plateforme(contenu: bytes) -> Traitement:
    """AXE-987 : un récapitulatif mensuel Uber se lit sans OCR (PDF texte)."""
    try:
        lecteur = PdfReader(io.BytesIO(contenu))
        texte = "\n".join(page.extract_text() or "" for page in lecteur.pages)
    except Exception:  # noqa: BLE001 — un PDF abîmé reste à lire, sans erreur
        return Traitement("a_traiter", A_LIRE)
    recap = lire_recap(texte)
    if recap is None:
        return Traitement("a_traiter", A_LIRE)
    annee, mois = (int(x) for x in recap.mois.split("-"))
    nom_mois = f"{MOIS_FR[mois - 1]} {annee}"
    if not recap.juste:
        return Traitement(
            "a_traiter",
            f"Récapitulatif {recap.plateforme.capitalize()} de {nom_mois} : les montants ne "
            "tombent pas juste (courses + autres − frais ≠ net), à relire.",
            recap.donnees(),
            annee,
        )
    return Traitement(
        "traite",
        f"Récapitulatif {recap.plateforme.capitalize()} de {nom_mois} : courses "
        f"{_euros(recap.courses_cts)}, autres revenus {_euros(recap.autres_cts)}, frais "
        f"{_euros(recap.frais_cts)}, net {_euros(recap.net_cts)}.",
        recap.donnees(),
        annee,
    )


# --- AXE-970 : classer un fichier déposé en vrac ------------------------------

_FEC_NOM = re.compile(r"(^|/)\d{9}(\d{5})?fec\d{8}", re.IGNORECASE)
# Dans l'ordre : le premier motif qui parle l'emporte (« paiement_IS » est
# un paiement avant d'être de l'IS).
_MOTIFS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(motif), categorie)
    for motif, categorie in (
        (r"paiement|ordre de prelevement|avis de prelevement", "paiement_impot"),
        (r"accuse", "accuse_reception"),
        # « Synthèse de la déclaration RESULTAT » : la 2065 télédéclarée.
        (
            r"liasse|declaration (de )?resultat|\b(2065|2033|2031|2035|2050|2051|2052|2053)\b",
            "liasse",
        ),
        (r"\btva\b|\b3517\b|\bca3\b|\bca12\b|\b3310\b", "declaration_tva"),
        (r"\bis\b|\b257[12]\b|impot sur les societes|\bacompte", "declaration_is"),
        (r"grand[ ._-]?livre|\bgl\b", "grand_livre"),
        (r"balance", "balance"),
        (r"bilan|compte de resultat|comptes annuels|\bannexe", "comptes_annuels"),
        # AXE-987 : avant « relevé » : un relevé Uber n'est pas un relevé bancaire.
        (r"\b(uber|bolt|heetch|freenow|free now|allocab)\b", "releve_plateforme"),
        # « SG 10-2025.pdf » : un relevé Société Générale du mois (AXE-988).
        (
            r"releve|\.qif$|\.ofx$|societe generale|\bsg \d{1,2}[ -]\d{4}\b",
            "releve_bancaire",
        ),
        (r"k-?bis|extrait", "kbis"),
        (r"statuts", "statuts"),
        (r"\brib\b|\biban\b", "rib"),
        (
            r"encaissement|\b(enc|fac|fa|av)-?\d+|facture|\brecu\b|ticket|note de frais",
            "piece",
        ),
    )
)


def _sans_accent(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


# AXE-988 : un classeur ou un document Office est un zip, mais un seul
# fichier : il n'est pas déplié (13 XML internes sinon).
EXTENSIONS_OFFICE = frozenset(
    {
        ".xlsx",
        ".xlsm",
        ".xltx",
        ".docx",
        ".docm",
        ".dotx",
        ".pptx",
        ".ppsx",
        ".ods",
        ".odt",
        ".odp",
        ".odg",
        ".numbers",
        ".pages",
        ".key",
        ".epub",
    }
)


def est_zip(nom: str, contenu: bytes) -> bool:
    """Une archive à déplier : un contenu zip qui n'est pas un fichier Office."""
    return contenu[:4] == b"PK\x03\x04" and Path(nom.lower()).suffix not in EXTENSIONS_OFFICE


def classer(nom_fichier: str, contenu: bytes) -> str:
    """La catégorie d'un fichier d'après son contenu (FEC, archive) puis son
    nom, chemin compris (« Encaissements de Vente/ENC-117.pdf » : une pièce) ;
    « autre » si rien ne parle. Une impression PDF du FEC n'est pas un FEC."""
    nom = _sans_accent(nom_fichier).replace("_", " ")
    if nom.endswith(".zip") or est_zip(nom, contenu):
        return "archive"
    if est_impression_fec(nom_fichier, contenu):
        return "fec"
    if est_fec(contenu) or (
        _FEC_NOM.search(nom.replace(" ", "")) and not contenu.startswith(b"%PDF")
    ):
        return "fec"
    for motif, categorie in _MOTIFS:
        if motif.search(nom):
            return categorie
    return "autre"


def est_impression_fec(nom_fichier: str, contenu: bytes) -> bool:
    """Un PDF dont le nom dit FEC (« FEC - Fichier à plat CSV.pdf », OneUp) :
    l'impression du FEC, rangée avec lui. Le nom seul, pas le chemin."""
    base = _sans_accent(nom_fichier.rsplit("/", 1)[-1]).replace("_", " ")
    return contenu.startswith(b"%PDF") and re.search(r"\bfec\b", base) is not None


def annee_du_nom(nom_fichier: str, permises: set[int] | None = None) -> int | None:
    """L'année de clôture lue dans un nom (« 908771033FEC20220930 », « liasse
    2019 ») ; la dernière qui parle, et seulement parmi `permises` si donné."""
    lues = [int(a) for a in re.findall(r"(?<!\d)(20\d\d)(?:\d{4})?(?!\d)", nom_fichier)]
    if permises is not None:
        lues = [a for a in lues if a in permises]
    return lues[-1] if lues else None


# --- AXE-970 : déplier une archive -------------------------------------------

MEMBRES_MAX = 5_000
TAILLE_DEPLIEE_MAX = 1024 * 1024 * 1024  # 1 Go une fois dépliée, toutes profondeurs
PROFONDEUR_MAX = 3
_IGNORES = re.compile(r"(^|/)(__macosx|meta-inf)(/|$)|(^|/)\.|(^|/)(mimetype(\.txt)?|thumbs\.db)$")


def est_technique(nom: str, contenu: bytes) -> bool:
    """Les fichiers techniques d'une archive fiscale (OneUp) : `info.txt`
    (logiciel, liste des fichiers) et `logs.txt` (journal des événements).
    Reconnus à leur contenu ; ils restent dans le zip d'origine, signé."""
    base = nom.rsplit("/", 1)[-1].lower()
    tete = contenu[:40].lstrip(b"\xef\xbb\xbf")
    return (base == "info.txt" and tete.startswith(b"Software\t")) or (
        base == "logs.txt" and tete.startswith(b'"JETNID"')
    )


class ArchiveIllisible(ValueError):
    """Zip abîmé, chiffré, ou au-delà des plafonds."""


@dataclass(frozen=True, slots=True)
class Membre:
    chemin: str  # « archive.zip/Encaissements de Vente/ENC-117/ENC-117.pdf »
    contenu: bytes


def _nom_membre(info: zipfile.ZipInfo) -> str:
    """Un nom en UTF-8 sans le drapeau UTF-8 (OneUp) est relu comme UTF-8."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def deplier(contenu: bytes) -> list[Membre]:
    """Chaque fichier de l'archive, zips imbriqués dépliés à leur tour (le zip
    intermédiaire n'est pas gardé : il est dans l'archive d'origine). Les
    dossiers, fichiers cachés, `__MACOSX`, la signature `META-INF` et les
    fichiers techniques OneUp (`est_technique`) sont laissés : l'archive
    d'origine les garde intacts."""
    membres: list[Membre] = []
    budget = [TAILLE_DEPLIEE_MAX]

    def ouvrir(donnees: bytes, prefixe: str, profondeur: int) -> None:
        try:
            archive = zipfile.ZipFile(io.BytesIO(donnees))
        except zipfile.BadZipFile as exc:
            raise ArchiveIllisible("archive zip illisible") from exc
        with archive:
            for info in archive.infolist():
                nom = _nom_membre(info)
                if info.is_dir() or _IGNORES.search(nom.lower()):
                    continue
                if info.flag_bits & 0x1:
                    raise ArchiveIllisible(f"{nom} est protégé par un mot de passe")
                budget[0] -= info.file_size
                if budget[0] < 0 or len(membres) >= MEMBRES_MAX:
                    raise ArchiveIllisible(
                        f"archive trop grosse une fois dépliée (plus de {MEMBRES_MAX} fichiers "
                        "ou plus de 1 Go) : la déposer en plusieurs fois"
                    )
                donnee = archive.read(info)
                chemin = f"{prefixe}{nom}"
                if est_zip(nom, donnee) and profondeur < PROFONDEUR_MAX:
                    ouvrir(donnee, f"{chemin}/", profondeur + 1)
                    continue
                if not est_technique(nom, donnee):
                    membres.append(Membre(chemin, donnee))

    ouvrir(contenu, "", 1)
    return membres
