"""Registre des immobilisations et amortissement linéaire (AXE-802, doc 12 §1.3).

Pur : prend le registre, rend les dotations et les écritures d'inventaire.
Plan linéaire au prorata temporis, en jours de 30/360 (un mois = 30 jours),
en centimes. Le cumul est arrondi, la dotation d'un exercice est la
différence de deux cumuls : la somme des dotations vaut toujours la base.

Fiscalité (CGI art. 39-4) : le plafond d'amortissement des véhicules de
tourisme ne s'applique pas aux entreprises de transport de personnes
(BOI-BIC-AMT-20-40-50-20, § 50 : « notamment exploitants de taxis »). Le
pack VTC suppose que les VTC en relèvent : pas de réintégration en 2033-B.
Hypothèse à valider par l'expert-comptable (AXE-815).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

COMPTE_DOTATION = "6811"
COMPTE_VNC_CEDEE = "675"
# Durées proposées au chauffeur, en mois, par compte d'immobilisation. Il peut
# en choisir une autre.
DUREES_PROPOSEES = {"2182": 60, "218": 60, "2183": 36, "2184": 120}
DUREE_PAR_DEFAUT = 60


class ImmobilisationInvalide(SaisieInvalide):
    """Fiche refusée : compte, base, durée ou date inutilisable."""


@dataclass(frozen=True, slots=True)
class Cession:
    """Vente ou mise au rebut. Le prix de vente arrive par la banque (775) ;
    il sert ici à montrer la plus ou moins-value."""

    le: date
    prix_cts: int = 0


@dataclass(frozen=True, slots=True)
class Immobilisation:
    id: str
    designation: str
    compte: str  # 2182 matériel de transport, 2183 informatique…
    mise_en_service: date
    base_cts: int  # HT si la TVA a été récupérée, sinon TTC
    duree_mois: int
    ecriture_acquisition: str | None = None
    cession: Cession | None = None

    @property
    def compte_amortissement(self) -> str:
        """2182 → 28182 (PCG : 28 suivi du compte sans son 2)."""
        return f"28{self.compte[1:]}"


def valider(immobilisation: Immobilisation) -> None:
    compte = immobilisation.compte
    if not compte.isdigit() or not compte.startswith("2") or compte.startswith("28"):
        raise ImmobilisationInvalide("Ce compte n'est pas un compte d'immobilisation.")
    if immobilisation.base_cts <= 0:
        raise ImmobilisationInvalide("La valeur à amortir doit être supérieure à zéro.")
    if not 12 <= immobilisation.duree_mois <= 600:
        raise ImmobilisationInvalide("Indiquez une durée entre 1 et 50 ans.")
    if not immobilisation.designation.strip():
        raise ImmobilisationInvalide("Indiquez de quel bien il s'agit.")
    cession = immobilisation.cession
    if cession is not None and (
        cession.le < immobilisation.mise_en_service or cession.prix_cts < 0
    ):
        raise ImmobilisationInvalide("La cession ne peut pas précéder la mise en service.")


def jours_360(debut: date, fin: date) -> int:
    """Jours de `debut` à `fin` inclus, mois de 30 jours (30E/360)."""
    if fin < debut:
        return 0
    return (
        (fin.year - debut.year) * 360
        + (fin.month - debut.month) * 30
        + (min(fin.day, 30) - min(debut.day, 30))
        + 1
    )


def cumul(immobilisation: Immobilisation, au: date) -> int:
    """Amortissements cumulés au soir du jour `au`, arrêtés à la cession."""
    if immobilisation.cession is not None:
        au = min(au, immobilisation.cession.le)
    total = immobilisation.duree_mois * 30
    jours = min(jours_360(immobilisation.mise_en_service, au), total)
    valeur = Decimal(immobilisation.base_cts) * jours / total
    return int(valeur.quantize(Decimal(1), ROUND_HALF_UP))


def dotation(immobilisation: Immobilisation, debut: date, fin: date) -> int:
    """La dotation de l'exercice [debut, fin]."""
    return cumul(immobilisation, fin) - cumul(immobilisation, debut - timedelta(days=1))


def valeur_nette(immobilisation: Immobilisation, au: date) -> int:
    return immobilisation.base_cts - cumul(immobilisation, au)


def plus_ou_moins_value(immobilisation: Immobilisation) -> int | None:
    """Prix de cession moins valeur nette comptable ; `None` sans cession."""
    cession = immobilisation.cession
    if cession is None:
        return None
    return cession.prix_cts - valeur_nette(immobilisation, cession.le)


def prefixe_immobilisations(dossier_id: DossierId, annee: int) -> str:
    return f"{dossier_id}:cloture-immo-{annee}-"


def ecritures_immobilisations(
    dossier_id: DossierId,
    immobilisations: tuple[Immobilisation, ...],
    debut: date,
    fin: date,
) -> tuple[Ecriture, ...]:
    """Écritures d'inventaire de l'exercice : la dotation de chaque bien
    (6811 / 28xx, au dernier jour), puis la sortie de l'actif d'un bien cédé
    dans l'exercice (28xx et 675 au débit, 2xx au crédit, à la date de cession)."""
    ecritures: list[Ecriture] = []
    prefixe = prefixe_immobilisations(dossier_id, fin.year)
    for immo in immobilisations:
        valider(immo)
        montant = dotation(immo, debut, fin)
        if montant > 0:
            ecritures.append(
                _ecriture(
                    f"{prefixe}dotation-{immo.id}",
                    dossier_id,
                    fin,
                    f"Dotation aux amortissements — {immo.designation}",
                    (
                        (COMPTE_DOTATION, Sens.DEBIT, montant),
                        (immo.compte_amortissement, Sens.CREDIT, montant),
                    ),
                )
            )
        if immo.cession is not None and debut <= immo.cession.le <= fin:
            ecritures.append(_sortie(prefixe, dossier_id, immo))
    return tuple(ecritures)


def _sortie(prefixe: str, dossier_id: DossierId, immo: Immobilisation) -> Ecriture:
    assert immo.cession is not None
    amortie = cumul(immo, immo.cession.le)
    return _ecriture(
        f"{prefixe}cession-{immo.id}",
        dossier_id,
        immo.cession.le,
        f"Sortie de l'actif — {immo.designation}",
        (
            (immo.compte_amortissement, Sens.DEBIT, amortie),
            (COMPTE_VNC_CEDEE, Sens.DEBIT, immo.base_cts - amortie),
            (immo.compte, Sens.CREDIT, immo.base_cts),
        ),
    )


def _ecriture(
    identifiant: str,
    dossier_id: DossierId,
    jour: date,
    libelle: str,
    lignes: tuple[tuple[str, Sens, int], ...],
) -> Ecriture:
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=jour,
        libelle=libelle,
        reference_piece=f"IMMO-{jour.year}",
        lignes=tuple(
            LigneEcriture(compte=compte, sens=sens, montant=Money(centimes))
            for compte, sens, centimes in lignes
            if centimes > 0
        ),
    )
