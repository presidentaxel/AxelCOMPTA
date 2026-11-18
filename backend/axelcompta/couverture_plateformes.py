"""La couverture des plateformes d'une fiche d'import, mois par mois (AXE-987).

Pour chaque plateforme (Uber, Bolt…), on rapproche trois sources :

* la **banque** : les virements de la plateforme au grand livre du dossier,
  rangés dans la semaine qu'ils paient (`revenus_semaines`) ;
* **Rollee** : les jours gagnés gardés pour le dossier ;
* les **documents** déposés sur la fiche : un récapitulatif lu donne un mois.

Un mois est :

* `rollee` : chaque virement du mois tombe dans une semaine qui a des jours
  Rollee ;
* `document` : un récapitulatif de la plateforme pour ce mois est déposé ;
* `a_completer` : des virements en banque dans des semaines sans jour Rollee,
  et aucun document : il manque des informations ;
* `banque` : des jours Rollee mais aucun virement en banque. C'est un manque
  côté banque, que la couverture bancaire (AXE-973) traite ;
* `sans_activite` : ni l'un ni l'autre.

Seuls des agrégats sortent d'ici : nombre de virements et total du mois.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from axelcompta.ingestion.semaines_plateforme import lundi
from axelcompta.ingestion.settlements_plateforme import SettlementStocke
from axelcompta.ledger.models import Ecriture
from axelcompta.revenus_semaines import virements_de_plateforme
from axelcompta.tenants.fiches_import import DocumentImport

EtatMois = Literal["rollee", "document", "a_completer", "banque", "sans_activite"]
NOMS = {
    "uber": "Uber",
    "bolt": "Bolt",
    "heetch": "Heetch",
    "allocab": "Allocab",
    "freenow": "Free Now",
}
MOIS = (
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


@dataclass(frozen=True, slots=True)
class VirementVu:
    plateforme: str
    semaine: date  # le lundi de la semaine payée
    montant_cts: int


@dataclass(frozen=True, slots=True)
class MoisPlateforme:
    mois: str  # « 2025-10 »
    etat: EtatMois
    virements: int = 0  # virements du mois sans jour Rollee
    verse_cts: int = 0


@dataclass(frozen=True, slots=True)
class PlateformeCouverte:
    plateforme: str
    mois: tuple[MoisPlateforme, ...]

    @property
    def a_completer(self) -> tuple[str, ...]:
        nom = NOMS.get(self.plateforme, self.plateforme.capitalize())
        return tuple(
            f"{nom}, {libelle_mois(m.mois)} : {m.virements} virement(s) en banque "
            f"({_euros(m.verse_cts)}) sans jour Rollee. Déposez le récapitulatif du mois."
            for m in self.mois
            if m.etat == "a_completer"
        )


def _euros(centimes: int) -> str:
    return f"{centimes / 100:,.2f} €".replace(",", " ").replace(".", ",")


def libelle_mois(mois: str) -> str:
    annee, numero = mois.split("-")
    return f"{MOIS[int(numero) - 1]} {annee}"


def _mois(jour: date) -> str:
    return f"{jour.year}-{jour.month:02d}"


def _mois_entre(debut: date, fin: date) -> list[str]:
    tous, courant = [], date(debut.year, debut.month, 1)
    while courant <= fin:
        tous.append(_mois(courant))
        courant = (courant + timedelta(days=32)).replace(day=1)
    return tous


def couverture(
    jours: Iterable[tuple[str, date]],
    virements: Iterable[VirementVu],
    documents: Iterable[tuple[str, str]],
    depuis: date | None,
    aujourd_hui: date,
) -> list[PlateformeCouverte]:
    """`jours` : (plateforme, jour Rollee) ; `documents` : (plateforme,
    mois) des récapitulatifs lus. Mois par mois, de `depuis` (ou de la
    première donnée) au mois en cours."""
    jours, virements, documents = list(jours), list(virements), set(documents)
    plateformes = sorted({p for p, _ in jours} | {v.plateforme for v in virements})
    semaines_rollee = {(p, lundi(j)) for p, j in jours}
    mois_rollee = {(p, _mois(j)) for p, j in jours}
    debuts = [j for _p, j in jours] + [v.semaine for v in virements]
    if not plateformes or (depuis is None and not debuts):
        return []
    debut = depuis or min(debuts)
    resultat = []
    for plateforme in plateformes:
        siens = [v for v in virements if v.plateforme == plateforme]
        mois = []
        for m in _mois_entre(debut, aujourd_hui):
            du_mois = [v for v in siens if _mois(v.semaine) == m]
            sans = [v for v in du_mois if (plateforme, v.semaine) not in semaines_rollee]
            if sans and (plateforme, m) in documents:
                etat: EtatMois = "document"
            elif sans:
                etat = "a_completer"
            elif du_mois:
                etat = "rollee"
            elif (plateforme, m) in mois_rollee:
                etat = "banque"
            elif (plateforme, m) in documents:
                etat = "document"
            else:
                etat = "sans_activite"
            mois.append(MoisPlateforme(m, etat, len(sans), sum(v.montant_cts for v in sans)))
        resultat.append(PlateformeCouverte(plateforme, tuple(mois)))
    return resultat


def jours_rollee(stockes: Sequence[SettlementStocke]) -> list[tuple[str, date]]:
    """Les jours Rollee gardés pour le dossier (semaines et mois ignorés)."""
    return [
        (s.settlement.platform, s.settlement.period_start)
        for s in stockes
        if s.settlement.period_start == s.settlement.period_end and s.etat != "delie"
    ]


def virements_vus(grand_livre: Sequence[Ecriture]) -> list[VirementVu]:
    return [
        VirementVu(v.plateforme, v.semaine, v.montant_cts)
        for v, _e in virements_de_plateforme(grand_livre).values()
    ]


def recaps_deposes(documents: Sequence[DocumentImport]) -> list[tuple[str, str]]:
    """(plateforme, mois) de chaque récapitulatif lu sur la fiche."""
    lus = []
    for d in documents:
        donnees = d.donnees or {}
        if donnees.get("type") == "recap_plateforme" and d.statut_traitement == "traite":
            lus.append((str(donnees.get("plateforme")), str(donnees.get("mois"))))
    return lus
