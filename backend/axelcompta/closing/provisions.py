"""CCA et FNP saisies par l'indiv (doc 06 §5, point 5).

Le moteur n'a pas de règle pour décider quand les constater : cette
politique n'est pas tranchée (doc 06 §5bis). Il enregistre l'estimation
qu'on lui donne, et rien d'autre.
"""

from __future__ import annotations

from datetime import date

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

from .models import ProvisionCloture

COMPTE_CCA = "486"
COMPTE_FNP = "408"


class ProvisionInvalide(DomaineError):
    """Estimation refusée : compte, montant ou nature inutilisable."""


def prefixe_provisions(dossier_id: DossierId, annee: int) -> str:
    return f"{dossier_id}:cloture-provision-{annee}-"


def valider_provision(provision: ProvisionCloture) -> None:
    if provision.nature not in ("cca", "fnp"):
        raise ProvisionInvalide(f"nature inconnue : {provision.nature}")
    if provision.centimes <= 0:
        raise ProvisionInvalide("le montant d'une provision se saisit en centimes positifs")
    compte = provision.compte_charge
    if not compte.isdigit() or not compte.startswith("6") or compte.startswith("69"):
        raise ProvisionInvalide(f"compte de charge attendu (classe 6, hors impôt) : {compte}")
    if not provision.libelle.strip():
        raise ProvisionInvalide("une provision saisie porte un libellé")


def ecritures_provisions(
    dossier_id: DossierId, provisions: tuple[ProvisionCloture, ...], date_cloture: date
) -> tuple[Ecriture, ...]:
    return tuple(
        _ecriture(dossier_id, provision, date_cloture, index)
        for index, provision in enumerate(provisions)
    )


def _ecriture(
    dossier_id: DossierId, provision: ProvisionCloture, date_cloture: date, index: int
) -> Ecriture:
    valider_provision(provision)
    annee = date_cloture.year
    montant = Money(provision.centimes)
    if provision.nature == "cca":
        lignes = (
            LigneEcriture(compte=COMPTE_CCA, sens=Sens.DEBIT, montant=montant),
            LigneEcriture(compte=provision.compte_charge, sens=Sens.CREDIT, montant=montant),
        )
        nature = "CCA"
    else:
        lignes = (
            LigneEcriture(compte=provision.compte_charge, sens=Sens.DEBIT, montant=montant),
            LigneEcriture(compte=COMPTE_FNP, sens=Sens.CREDIT, montant=montant),
        )
        nature = "FNP"
    return Ecriture(
        id=EcritureId(f"{prefixe_provisions(dossier_id, annee)}{index}"),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=date_cloture,
        libelle=f"{nature} — {provision.libelle.strip()}",
        reference_piece=f"CLOTURE-{nature}-{annee}",
        lignes=lignes,
    )
