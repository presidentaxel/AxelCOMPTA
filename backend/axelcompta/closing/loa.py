"""Véhicule en LOA : premier loyer majoré étalé, engagement hors bilan (AXE-803).

Pur, comme les immobilisations. Le premier loyer majoré est payé d'un coup
et passe en charge (612) par la banque ; à chaque clôture, la part qui
concerne les mois suivants est mise en charge constatée d'avance (486). On
écrit l'écart entre la CCA voulue en fin d'exercice et celle d'ouverture :
la charge de l'exercice est exactement la part de ses jours.

Échéancier supposé : le loyer majoré à la date de début, puis un loyer par
mois à partir du mois suivant, jusqu'au terme ; l'option se lève au terme.

Part non déductible (CGI art. 39-4) : comme pour l'amortissement, le plafond
ne s'applique pas aux entreprises de transport de personnes
(BOI-BIC-AMT-20-40-50-20, § 50 et § 260). Pas de réintégration pour le pack
VTC. Le taux de CO2 est gardé pour le jour où il faudrait l'appliquer.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

from .immobilisations import jours_360

COMPTE_CCA = "486"
COMPTE_LOYER_LOA = "612"


class ContratInvalide(SaisieInvalide):
    """Fiche de LOA refusée."""


@dataclass(frozen=True, slots=True)
class ContratLoa:
    id: str
    loueur: str
    vehicule: str
    debut: date
    duree_mois: int
    loyer_mensuel_cts: int
    premier_loyer_cts: int
    prix_levee_cts: int
    co2_g_km: int | None = None


def valider(contrat: ContratLoa) -> None:
    if not contrat.loueur.strip() or not contrat.vehicule.strip():
        raise ContratInvalide("Indiquez le loueur et le véhicule.")
    if not 6 <= contrat.duree_mois <= 120:
        raise ContratInvalide("Indiquez une durée entre 6 et 120 mois.")
    montants = (contrat.loyer_mensuel_cts, contrat.premier_loyer_cts, contrat.prix_levee_cts)
    if min(montants) < 0 or contrat.loyer_mensuel_cts == 0:
        raise ContratInvalide("Les montants doivent être positifs, et le loyer non nul.")


def _plus_mois(jour: date, mois: int) -> date:
    """Même jour, `mois` mois plus tard (borné à la fin du mois : 31/01 → 28/02)."""
    annee, rang = divmod(jour.month - 1 + mois, 12)
    annee += jour.year
    return date(annee, rang + 1, min(jour.day, monthrange(annee, rang + 1)[1]))


def echeances(contrat: ContratLoa) -> list[tuple[date, int]]:
    """Le loyer majoré au début, puis un loyer par mois jusqu'au terme."""
    return [(contrat.debut, contrat.premier_loyer_cts)] + [
        (_plus_mois(contrat.debut, k), contrat.loyer_mensuel_cts)
        for k in range(1, contrat.duree_mois)
    ]


def terme(contrat: ContratLoa) -> date:
    return _plus_mois(contrat.debut, contrat.duree_mois) - timedelta(days=1)


def part_consommee(contrat: ContratLoa, au: date) -> int:
    """La part du premier loyer qui concerne les jours écoulés jusqu'à `au`."""
    total = contrat.duree_mois * 30
    jours = min(jours_360(contrat.debut, au), total)
    valeur = Decimal(contrat.premier_loyer_cts) * jours / total
    return int(valeur.quantize(Decimal(1), ROUND_HALF_UP))


def cca(contrat: ContratLoa, au: date) -> int:
    """Charge constatée d'avance au soir de `au` : 0 avant le paiement."""
    if au < contrat.debut:
        return 0
    return contrat.premier_loyer_cts - part_consommee(contrat, au)


def charge_premier_loyer(contrat: ContratLoa, debut: date, fin: date) -> int:
    """La part du premier loyer qui revient à l'exercice [debut, fin]."""
    return part_consommee(contrat, fin) - part_consommee(contrat, debut - timedelta(days=1))


def engagement_restant(contrat: ContratLoa, au: date) -> int:
    """Hors bilan : loyers encore à payer après `au`, plus le prix de levée."""
    if au >= terme(contrat):
        return 0
    restants = sum(montant for jour, montant in echeances(contrat) if jour > au)
    return restants + contrat.prix_levee_cts


def prefixe_loa(dossier_id: DossierId, annee: int) -> str:
    return f"{dossier_id}:cloture-loa-{annee}-"


def ecritures_loa(
    dossier_id: DossierId,
    contrats: tuple[ContratLoa, ...],
    debut: date,
    fin: date,
    compte_loyer: str = COMPTE_LOYER_LOA,
) -> tuple[Ecriture, ...]:
    """L'écart de CCA de l'exercice, au dernier jour : 486 au débit si elle
    augmente (année du paiement), 612 au débit si elle se consomme."""
    ecritures = []
    for contrat in contrats:
        valider(contrat)
        ecart = cca(contrat, fin) - cca(contrat, debut - timedelta(days=1))
        if ecart == 0:
            continue
        debit, credit = (COMPTE_CCA, compte_loyer) if ecart > 0 else (compte_loyer, COMPTE_CCA)
        montant = Money(abs(ecart))
        ecritures.append(
            Ecriture(
                id=EcritureId(f"{prefixe_loa(dossier_id, fin.year)}{contrat.id}"),
                dossier_id=dossier_id,
                journal=Journal.OD,
                date=fin,
                libelle=f"LOA {contrat.loueur} — premier loyer étalé",
                reference_piece=f"LOA-{fin.year}",
                lignes=(
                    LigneEcriture(compte=debit, sens=Sens.DEBIT, montant=montant),
                    LigneEcriture(compte=credit, sens=Sens.CREDIT, montant=montant),
                ),
            )
        )
    return tuple(ecritures)
