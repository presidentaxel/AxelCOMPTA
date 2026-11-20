"""Le chiffre d'affaires d'un mois depuis le récapitulatif de la plateforme,
quand Rollee ne couvre pas ce mois (AXE-801). Pur.

Un récapitulatif mensuel lu (Uber, Bolt…, AXE-987 et AXE-943) donne les
courses (frais de la plateforme compris), les autres revenus, les frais et le
net. Il s'écrit comme une semaine Rollee (`ecritures_semaines`) :

* **la recette du mois** : la créance sur la plateforme (467x) pour le net,
  contre 706 HT et 44571 sur les courses, 708 sans TVA pour les autres
  revenus, et la commission (6222, avec la TVA de son régime) ;
* **chaque virement de la plateforme du mois**, encore au 471, solde la
  créance (471 contre 467x) ; le 512 ne bouge pas.

Ce qui reste sur le 467x à la fin est l'écart du mois (un virement du mois
suivant, ou un manque), visible comme pour une semaine Rollee. Un mois que
Rollee couvre n'est jamais écrit ici. Rejouer ne crée rien : les
identifiants dérivent du mois et du virement.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from axelcompta.core.ids import DossierId
from axelcompta.ledger.banque import ligne_banque
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.models import Ecriture, Sens

from .ecritures_semaines import ecriture_recette, ecriture_solde, id_recette, id_solde
from .providers.base import PlatformSettlement

COMPTE_ATTENTE = "471"


@dataclass(frozen=True, slots=True)
class Recap:
    plateforme: str
    mois: str  # « 2025-11 »
    courses_cts: int
    autres_cts: int
    frais_cts: int
    net_cts: int


def recap_depuis(donnees: Mapping[str, object]) -> Recap | None:
    """Les `donnees` d'un document d'import, s'il s'agit d'un récapitulatif
    mensuel lu et juste au centime."""
    if donnees.get("type") != "recap_plateforme":
        return None
    try:
        recap = Recap(
            str(donnees["plateforme"]),
            str(donnees["mois"]),
            int(str(donnees["courses_cts"])),
            int(str(donnees["autres_cts"])),
            int(str(donnees["frais_cts"])),
            int(str(donnees["net_cts"])),
        )
    except (KeyError, ValueError):
        return None
    juste = recap.courses_cts + recap.autres_cts - recap.frais_cts == recap.net_cts
    return recap if juste and len(recap.mois) == 7 else None


def _bornes(mois: str) -> tuple[date, date]:
    annee, numero = int(mois[:4]), int(mois[5:7])
    debut = date(annee, numero, 1)
    suivant = date(annee + numero // 12, numero % 12 + 1, 1)
    return debut, date.fromordinal(suivant.toordinal() - 1)


def _virements_au_471(
    ecritures: Sequence[Ecriture], motif: re.Pattern[str], debut: date, fin: date
) -> list[Ecriture]:
    """Les virements reçus de la plateforme sur le mois, encore au 471 : ni
    annulés, ni tranchés par un humain, ni déjà soldés (Rollee ou récapitulatif)."""
    ids = {e.id for e in ecritures}
    exclues = annulees(ecritures)
    tranches = {i.split(":decision-")[0] for i in ids if ":decision-" in i}
    return [
        e
        for e in ecritures
        if debut <= e.date <= fin
        and e.id not in exclues
        and e.id not in tranches
        and id_solde(str(e.id)) not in ids
        and ligne_banque(e) is not None
        and motif.search(e.libelle)
        and any(lg.compte == COMPTE_ATTENTE and lg.sens is Sens.CREDIT for lg in e.lignes)
    ]


def ecritures_du_mois(
    dossier_id: DossierId,
    recap: Recap,
    ecritures: Sequence[Ecriture],
    regimes_commission: Mapping[str, tuple[re.Pattern[str], str]],
    mois_rollee: Collection[tuple[str, str]],
    tva_recettes_regime: str,
) -> list[Ecriture]:
    """La recette du mois et les soldes de ses virements ; rien si Rollee
    couvre ce mois, ou si la plateforme est inconnue. `regimes_commission` :
    plateforme → (motif du libellé, régime de TVA de la commission)."""
    if (recap.plateforme, recap.mois) in mois_rollee or recap.plateforme not in regimes_commission:
        return []
    motif, regime = regimes_commission[recap.plateforme]
    debut, fin = _bornes(recap.mois)
    cle = f"{dossier_id}:recap:{recap.plateforme}:{recap.mois}"
    ids = {e.id for e in ecritures}
    a_ecrire: list[Ecriture] = []
    if id_recette(cle) not in ids:
        mois = PlatformSettlement(
            dossier_id=dossier_id,
            platform=recap.plateforme,
            period_start=fin,  # la recette du mois, datée de son dernier jour
            period_end=fin,
            payout_date=fin,
            gross_earnings_cts=recap.courses_cts + recap.autres_cts,
            commission_cts=recap.frais_cts,
            commission_tva_regime=regime,
            net_payout_cts=recap.net_cts,
            currency="EUR",
            source_provider="recap_plateforme",
            raw_payload={},
        )
        a_ecrire.append(
            ecriture_recette(cle, mois, 0, debut, tva_recettes_regime, recap.autres_cts)
        )
    for virement in _virements_au_471(ecritures, motif, debut, fin):
        montant = sum(
            lg.montant.centimes
            for lg in virement.lignes
            if lg.compte == COMPTE_ATTENTE and lg.sens is Sens.CREDIT
        )
        a_ecrire.append(ecriture_solde(virement, COMPTE_ATTENTE, montant, recap.plateforme, debut))
    return a_ecrire
