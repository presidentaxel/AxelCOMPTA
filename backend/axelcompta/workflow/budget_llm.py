"""Garde-fous de coût de l'étage LLM (AXE-887). Pur : aucune base, aucun appel.

Un « lot » est une requête de l'API Batch : au plus `LIBELLES_PAR_LOT`
libellés d'un dossier. Sa dépense compte dès la soumission (estimation
haute), puis au coût réel une fois relevé. On ne soumet que si la dépense
du mois, estimation du lot comprise, reste sous le plafond du chauffeur et
sous le plafond global : on ne paie jamais au-delà.

Pourquoi 0,50 $ par chauffeur et par mois : environ 4 fois le coût attendu
(0,12 $), et une petite part du coût total qu'un abonnement à 8-10 € permet
avec 80 % de marge.
"""

from __future__ import annotations

import hashlib
import os
from calendar import monthrange
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.pseudonymize.fournisseur_anthropic import MODELE_PAR_DEFAUT, PRIX_PAR_MODELE

PLAFOND_CHAUFFEUR_USD = 0.50
PLAFOND_GLOBAL_USD = 100.0
LIBELLES_PAR_LOT = 80
ECHECS_MAX = 2  # un libellé qui échoue deux fois va à l'humain, pour de bon
SEUILS = (50, 80, 100)
# Coupe-circuit : sur 24 h, au moins 3 lots relevés et la moitié en échec ou refus.
FENETRE_COUPE_CIRCUIT = timedelta(hours=24)
LOTS_MIN_COUPE_CIRCUIT = 3
PART_ECHECS_COUPE_CIRCUIT = 0.5
# Une réservation sans identifiant de lot Anthropic après ce délai : la
# soumission a échoué en route. Le lot passe en échec (rien n'a été payé).
RESERVATION_PERIMEE = timedelta(hours=2)
# La projection de fin de mois n'est fiable qu'après quelques jours.
JOURS_AVANT_PROJECTION = 5
# Une anomalie : un chauffeur coûte plus de 3 fois la moyenne.
FACTEUR_ANOMALIE = 3.0
DOSSIERS_MIN_ANOMALIE = 5

# Prix publics : ceux du fournisseur. L'API Batch les divise par deux.
REMISE_BATCH = 0.5

Statut = Literal["soumis", "termine", "echec", "refus"]


@dataclass(frozen=True, slots=True)
class Lot:
    id: str  # clé d'idempotence : un même lot n'est jamais soumis deux fois
    tenant_id: TenantId
    dossier_id: DossierId
    version: str
    modele: str
    cles: tuple[str, ...]
    statut: Statut
    estimation_usd: float
    soumis_le: datetime
    batch_id: str | None = None
    cout_usd: float = 0.0
    jetons_entree: int = 0
    jetons_sortie: int = 0
    jetons_cache: int = 0  # lus depuis le cache de prompt (compris dans l'entrée)
    termine_le: datetime | None = None

    @property
    def depense_usd(self) -> float:
        """Ce que le lot compte dans le budget : l'estimation tant qu'il n'est
        pas relevé, puis le coût réel."""
        return self.estimation_usd if self.statut == "soumis" else self.cout_usd


@dataclass(frozen=True, slots=True)
class Plafonds:
    chauffeur_usd: float = PLAFOND_CHAUFFEUR_USD
    global_usd: float = PLAFOND_GLOBAL_USD


# L'étage est éteint tant que cette variable ne vaut pas « 1 ».
VARIABLE_ACTIF = "AXELCOMPTA_LLM_ACTIF"


def llm_actif() -> bool:
    return os.environ.get(VARIABLE_ACTIF) == "1"


def plafonds_configures() -> Plafonds:
    """Les plafonds par défaut, ou ceux de l'environnement du serveur."""
    return Plafonds(
        chauffeur_usd=float(
            os.environ.get("AXELCOMPTA_LLM_PLAFOND_CHAUFFEUR_USD", PLAFOND_CHAUFFEUR_USD)
        ),
        global_usd=float(os.environ.get("AXELCOMPTA_LLM_PLAFOND_GLOBAL_USD", PLAFOND_GLOBAL_USD)),
    )


def cout(modele: str, entree: int, sortie: int) -> float:
    """Coût d'une requête de l'API Batch. Les jetons lus en cache sont comptés
    au prix plein : on surestime, jamais l'inverse."""
    prix_entree, prix_sortie = PRIX_PAR_MODELE.get(modele, PRIX_PAR_MODELE[MODELE_PAR_DEFAUT])
    return (entree * prix_entree + sortie * prix_sortie) * REMISE_BATCH / 1_000_000


def max_tokens(nb_libelles: int) -> int:
    """Borné selon le lot : réflexion courte (effort bas) et environ
    40 jetons de JSON par libellé."""
    return min(16_000, 1_000 + 120 * nb_libelles)


def estimation(modele: str, caracteres_envoyes: int, nb_libelles: int) -> float:
    """Le pire cas : environ 3 caractères par jeton en entrée, et toute la
    sortie permise consommée."""
    return cout(modele, caracteres_envoyes // 3 + 1, max_tokens(nb_libelles))


def id_lot(dossier_id: DossierId, version: str, cles: Sequence[str], tentative: int) -> str:
    """Même dossier, même version, mêmes libellés, même tentative : même lot.
    Une synchro relancée ne renvoie donc pas un lot déjà soumis."""
    empreinte = "\n".join([str(dossier_id), version, str(tentative), *sorted(cles)])
    return hashlib.sha256(empreinte.encode()).hexdigest()[:32]


def echecs_par_cle(lots: Iterable[Lot]) -> Counter[str]:
    """Un refus du modèle compte comme `ECHECS_MAX` : on ne le relance pas.
    Une soumission qui n'a jamais atteint Anthropic (pas d'identifiant de
    lot) ne compte pas : le libellé n'y est pour rien."""
    echecs: Counter[str] = Counter()
    for lot in lots:
        if lot.batch_id is None:
            continue
        poids = {"echec": 1, "refus": ECHECS_MAX}.get(lot.statut, 0)
        for cle in lot.cles:
            echecs[cle] += poids
    return echecs


def abandonnees(lots: Iterable[Lot]) -> set[str]:
    """Les libellés qui ne repartent plus : ils restent à l'humain."""
    return {cle for cle, n in echecs_par_cle(lots).items() if n >= ECHECS_MAX}


def debut_du_mois(maintenant: datetime) -> datetime:
    return maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def du_mois(lots: Iterable[Lot], maintenant: datetime) -> list[Lot]:
    debut = debut_du_mois(maintenant)
    return [lot for lot in lots if lot.soumis_le >= debut]


def libelles_du_mois(lots: Iterable[Lot], tenant_id: TenantId, maintenant: datetime) -> int:
    """Libellés confiés à l'IA ce mois-ci, une fois par dossier. Les refus
    et les échecs n'ont pas produit de catégorie. Le coût n'entre pas ici :
    le cabinet ne le voit pas."""
    vus: set[tuple[str, str]] = set()
    for lot in du_mois(lots, maintenant):
        if lot.tenant_id != tenant_id or lot.statut not in ("soumis", "termine"):
            continue
        for cle in lot.cles:
            vus.add((str(lot.dossier_id), cle))
    return len(vus)


def coupe_circuit(lots: Iterable[Lot], maintenant: datetime) -> bool:
    """Ouvert si trop de lots récents ont échoué ou été refusés."""
    recents = [
        lot
        for lot in lots
        if lot.termine_le is not None and lot.termine_le >= maintenant - FENETRE_COUPE_CIRCUIT
    ]
    if len(recents) < LOTS_MIN_COUPE_CIRCUIT:
        return False
    mauvais = sum(1 for lot in recents if lot.statut in ("echec", "refus"))
    return mauvais / len(recents) >= PART_ECHECS_COUPE_CIRCUIT


@dataclass
class Depenses:
    """Dépense du mois, par dossier et au global, réservations comprises."""

    par_dossier: dict[str, float] = field(default_factory=dict)
    globale: float = 0.0

    @classmethod
    def du_mois(cls, lots: Iterable[Lot], maintenant: datetime) -> Depenses:
        depenses = cls()
        for lot in du_mois(lots, maintenant):
            depenses.ajouter(lot)
        return depenses

    def ajouter(self, lot: Lot) -> None:
        cle = str(lot.dossier_id)
        self.par_dossier[cle] = self.par_dossier.get(cle, 0.0) + lot.depense_usd
        self.globale += lot.depense_usd


def refus_budget(
    depenses: Depenses, dossier_id: DossierId, estimation_usd: float, plafonds: Plafonds
) -> str | None:
    """La raison de ne pas soumettre, ou None si le lot tient dans les deux plafonds."""
    if depenses.par_dossier.get(str(dossier_id), 0.0) + estimation_usd > plafonds.chauffeur_usd:
        return f"budget du chauffeur atteint ({plafonds.chauffeur_usd:.2f} $ par mois)"
    if depenses.globale + estimation_usd > plafonds.global_usd:
        return f"plafond global atteint ({plafonds.global_usd:.2f} $ par mois)"
    return None


def soumis_le_jour(lots: Iterable[Lot], dossier_id: DossierId, jour: date) -> bool:
    """Au plus un passage par dossier et par jour : on regroupe les libellés."""
    return any(lot.dossier_id == dossier_id and lot.soumis_le.date() == jour for lot in lots)


def seuils_atteints(depense: float, plafond: float) -> list[int]:
    if plafond <= 0:
        return []
    return [seuil for seuil in SEUILS if depense >= plafond * seuil / 100]


def projection_depasse(depense: float, plafond: float, maintenant: datetime) -> bool:
    """Au rythme du mois en cours, le plafond sera-t-il dépassé à la fin du mois ?"""
    if maintenant.day < JOURS_AVANT_PROJECTION or depense <= 0:
        return False
    jours = monthrange(maintenant.year, maintenant.month)[1]
    ecoule = (maintenant - debut_du_mois(maintenant)) / timedelta(days=1)
    return depense / ecoule * jours > plafond


def anomalies(depenses: Depenses) -> list[str]:
    """Les dossiers qui coûtent plus de 3 fois la moyenne : boucle ou dossier anormal."""
    valeurs = [v for v in depenses.par_dossier.values() if v > 0]
    if len(valeurs) < DOSSIERS_MIN_ANOMALIE:
        return []
    moyenne = sum(valeurs) / len(valeurs)
    return sorted(d for d, v in depenses.par_dossier.items() if v > FACTEUR_ANOMALIE * moyenne)
