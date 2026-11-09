"""Créer les dossiers d'un portefeuille depuis un fichier (AXE-809).

Pour un portefeuille sans Digifactory : une ligne par société, et un rapport
ligne par ligne **avant** toute création. Les lignes en erreur ne sont pas
créées ; les autres le sont ensemble. Un second dépôt du même fichier ne crée
rien de plus : chaque dossier a un identifiant stable (`DIGI_{contact}` si le
numéro de contact Digifactory est donné, sinon `SIREN_{siren}`).

Le fichier n'est qu'un pré-remplissage (doc 03 §3bis) : le dirigeant
confirme sa configuration à sa première connexion (AXE-730). Pur : la
lecture Sirene est passée par l'appelant.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, TenantId

from .models import Dossier
from .sirene import FicheSirene, forme_depuis_nature
from .statuts import ConfigurationInvalide, configuration_de

COLONNES = (
    "siren",
    "nom",
    "forme_juridique",
    "regime_imposition",
    "regime_tva",
    "tva_recettes_regime",
    "exercice_debut",
    "exercice_fin",
    "option_ir_debut",
    "contact_digifactory",
)
OBLIGATOIRES = (
    "siren",
    "nom",
    "forme_juridique",
    "regime_imposition",
    "regime_tva",
    "exercice_debut",
)
LIGNES_MAX = 2_000
TAILLE_MAX = 2 * 1024 * 1024  # 2 Mo
DUREE_MAX_JOURS = 24 * 31  # un premier exercice dure au plus 24 mois

MODELE_CSV = (
    ";".join(COLONNES)
    + "\n"
    + "552100554;MK DRIVING;SASU;IS;reel_normal;assujetti_taux_reduit;2026-01-01;2026-12-31;;\n"
)

LireFiche = Callable[[str], FicheSirene | None]


class FichierIllisible(SaisieInvalide):
    """Pas un CSV lisible, trop gros, ou sans les colonnes attendues."""


@dataclass(frozen=True, slots=True)
class LigneImport:
    numero: int  # numéro de ligne dans le fichier (l'en-tête est la 1)
    dossier: Dossier | None  # None si la ligne est en erreur
    erreurs: tuple[str, ...] = ()
    avertissements: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Rapport:
    lignes: tuple[LigneImport, ...] = field(default_factory=tuple)

    @property
    def valides(self) -> tuple[Dossier, ...]:
        return tuple(ligne.dossier for ligne in self.lignes if ligne.dossier is not None)

    @property
    def en_erreur(self) -> int:
        return sum(1 for ligne in self.lignes if ligne.dossier is None)


def siren_valide(siren: str) -> bool:
    """Neuf chiffres et clé de Luhn (INSEE)."""
    if len(siren) != 9 or not siren.isdigit():
        return False
    total = 0
    for rang, chiffre in enumerate(int(c) for c in siren):
        double = chiffre * 2 if rang % 2 == 1 else chiffre
        total += double - 9 if double > 9 else double
    return total % 10 == 0


def lire_csv(contenu: bytes) -> list[dict[str, str]]:
    """Point-virgule ou virgule (Excel français ou non), UTF-8 avec ou sans BOM."""
    if len(contenu) > TAILLE_MAX:
        raise FichierIllisible("Le fichier dépasse 2 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FichierIllisible(
            "Le fichier n'est pas en UTF-8 : enregistrez-le en CSV UTF-8."
        ) from exc
    premiere = texte.splitlines()[0] if texte.strip() else ""
    separateur = ";" if premiere.count(";") >= premiere.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=separateur)
    manquantes = [c for c in OBLIGATOIRES if c not in (lecteur.fieldnames or [])]
    if manquantes:
        raise FichierIllisible(f"Colonnes manquantes : {', '.join(manquantes)}.")
    lignes = [{k: (v or "").strip() for k, v in ligne.items() if k} for ligne in lecteur]
    if len(lignes) > LIGNES_MAX:
        raise FichierIllisible(f"Au plus {LIGNES_MAX} lignes par fichier.")
    return lignes


def _date(texte: str, nom: str, erreurs: list[str]) -> date | None:
    if not texte:
        return None
    try:
        return date.fromisoformat(texte)
    except ValueError:
        erreurs.append(f"{nom} illisible ({texte}) : attendu AAAA-MM-JJ.")
        return None


def identifiant(siren: str, contact: str) -> DossierId:
    return DossierId(f"DIGI_{contact}" if contact else f"SIREN_{siren}")


def _construire(tenant_id: TenantId, ligne: dict[str, str], erreurs: list[str]) -> Dossier | None:
    siren = ligne.get("siren", "").replace(" ", "")
    if not siren_valide(siren):
        erreurs.append(f"SIREN invalide : {siren or '(vide)'}.")
    for colonne in OBLIGATOIRES:
        if not ligne.get(colonne):
            erreurs.append(f"Colonne {colonne} vide.")
    debut = _date(ligne.get("exercice_debut", ""), "exercice_debut", erreurs)
    fin = _date(ligne.get("exercice_fin", ""), "exercice_fin", erreurs)
    if debut and fin and not 0 < (fin - debut).days <= DUREE_MAX_JOURS:
        erreurs.append(
            "La fin d'exercice doit suivre le début, et l'exercice durer 24 mois au plus."
        )
    option = ligne.get("option_ir_debut", "")
    if option and not option.isdigit():
        erreurs.append(f"option_ir_debut illisible ({option}) : une année.")
    if erreurs or debut is None:
        return None
    return Dossier(
        id=identifiant(siren, ligne.get("contact_digifactory", "")),
        tenant_id=tenant_id,
        forme_juridique=ligne["forme_juridique"].upper(),
        regime_imposition=ligne["regime_imposition"],
        regime_tva=ligne["regime_tva"],
        nom=ligne["nom"],
        tva_recettes_regime=ligne.get("tva_recettes_regime") or "assujetti_taux_reduit",
        exercice_debut=debut,
        exercice_fin=fin,
        option_ir_debut=int(option) if option else None,
        contact_nr=ligne.get("contact_digifactory") or None,
    )


def _ecarts_sirene(dossier: Dossier, siren: str, fiche: FicheSirene | None) -> list[str]:
    if fiche is None:
        return [f"Aucune fiche Sirene pour {siren} : vérifiez le numéro."]
    ecarts: list[str] = []
    forme = forme_depuis_nature(fiche.nature_juridique)
    if (
        forme
        and forme != dossier.forme_juridique
        and {forme, dossier.forme_juridique}
        not in (
            {"SAS", "SASU"},
            {"SARL", "EURL"},
        )
    ):
        ecarts.append(f"Forme {dossier.forme_juridique} dans le fichier, {forme} chez Sirene.")
    if not fiche.active:
        ecarts.append("Société cessée selon Sirene.")
    return ecarts


def rapport(
    tenant_id: TenantId,
    lignes: Sequence[dict[str, str]],
    existants: Iterable[DossierId],
    lire_fiche: LireFiche | None = None,
) -> Rapport:
    """Chaque ligne : le dossier à créer, ou ses erreurs. Rien n'est écrit."""
    deja, vus = set(existants), set[DossierId]()
    resultat: list[LigneImport] = []
    for numero, ligne in enumerate(lignes, start=2):
        erreurs: list[str] = []
        dossier = _construire(tenant_id, ligne, erreurs)
        avertissements: list[str] = []
        if dossier is not None:
            try:
                configuration_de(dossier)
            except ConfigurationInvalide as exc:
                erreurs.append(f"Configuration refusée : {exc}")
            if dossier.id in deja:
                erreurs.append("Déjà dans le portefeuille.")
            elif dossier.id in vus:
                erreurs.append("Deux fois dans le fichier.")
            if lire_fiche is not None and not erreurs:
                avertissements = _ecarts_sirene(dossier, ligne["siren"], lire_fiche(ligne["siren"]))
            vus.add(dossier.id)
        resultat.append(
            LigneImport(numero, None if erreurs else dossier, tuple(erreurs), tuple(avertissements))
        )
    return Rapport(tuple(resultat))
