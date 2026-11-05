"""Paie du président assimilé salarié (SASU, SAS), depuis son bulletin.

AxeLCompta n'établit ni le bulletin ni la DSN : c'est le rôle d'un logiciel
de paie. Il passe en comptabilité le bulletin tel quel, chiffres fournis
par le chauffeur :
- 641 au débit : salaire brut ; 645 au débit : cotisations patronales ;
- 431 au crédit : cotisations salariales et patronales dues à l'URSSAF ;
- 4421 au crédit : prélèvement à la source retenu ;
- 421 au crédit : net à payer.

Le reste suit la banque, catégorisé par le chauffeur : son virement net
solde le 421 (« Ma rémunération »), le paiement à l'URSSAF le 431 (« Mes
cotisations sociales »), le reversement du prélèvement à la source le 4421.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens


class BulletinIncoherent(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Bulletin:
    """Montants en centimes, recopiés du bulletin ; `mois` au format AAAA-MM."""

    mois: str
    brut: int
    cotisations_salariales: int
    cotisations_patronales: int
    prelevement_a_la_source: int

    @property
    def net_a_payer(self) -> int:
        return self.brut - self.cotisations_salariales - self.prelevement_a_la_source

    def fin_du_mois(self) -> date:
        annee, mois = (int(x) for x in self.mois.split("-"))
        suivant = date(annee + 1, 1, 1) if mois == 12 else date(annee, mois + 1, 1)
        return suivant - timedelta(days=1)


def verifier(bulletin: Bulletin) -> None:
    montants = (
        bulletin.brut,
        bulletin.cotisations_salariales,
        bulletin.cotisations_patronales,
        bulletin.prelevement_a_la_source,
    )
    if any(m < 0 for m in montants) or bulletin.brut == 0:
        raise BulletinIncoherent(
            "Les montants sont négatifs, ou le salaire avant retenues est nul."
        )
    if bulletin.net_a_payer <= 0:
        raise BulletinIncoherent("Les retenues dépassent le salaire avant retenues.")
    try:
        bulletin.fin_du_mois()
    except ValueError as exc:
        raise BulletinIncoherent(
            f"Le mois « {bulletin.mois} » est illisible. Indiquez-le sous la forme AAAA-MM."
        ) from exc


def id_bulletin(dossier_id: DossierId, mois: str) -> EcritureId:
    return EcritureId(f"{dossier_id}:bulletin-{mois}")


def ecriture_bulletin(dossier_id: DossierId, bulletin: Bulletin) -> Ecriture:
    verifier(bulletin)
    cotisations = bulletin.cotisations_salariales + bulletin.cotisations_patronales
    lignes = [
        LigneEcriture("641", Sens.DEBIT, Money(bulletin.brut)),
        LigneEcriture("431", Sens.CREDIT, Money(cotisations)),
        LigneEcriture("421", Sens.CREDIT, Money(bulletin.net_a_payer)),
    ]
    if bulletin.cotisations_patronales:
        lignes.insert(1, LigneEcriture("645", Sens.DEBIT, Money(bulletin.cotisations_patronales)))
    if bulletin.prelevement_a_la_source:
        lignes.append(LigneEcriture("4421", Sens.CREDIT, Money(bulletin.prelevement_a_la_source)))
    return Ecriture(
        id=id_bulletin(dossier_id, bulletin.mois),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=bulletin.fin_du_mois(),
        libelle=f"Bulletin de paie du président, {bulletin.mois}",
        reference_piece=f"BULLETIN-{bulletin.mois}",
        lignes=tuple(lignes),
    )
