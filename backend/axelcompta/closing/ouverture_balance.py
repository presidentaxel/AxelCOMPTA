"""Bilan d'ouverture depuis une balance de clôture lue par l'OCR, quand la
fiche d'import n'a pas de FEC (AXE-992). Pur.

Mêmes garde-fous que le FEC (`ouverture_fec.analyser`), à ce qui se vérifie
sur une balance : arrêtée la veille de l'ouverture, équilibrée au centime,
chaque compte dans le plan comptable (ou mis en correspondance). Une balance
arrêtée **avant les écritures de clôture** a encore ses comptes 6 et 7 :
leur solde net est le résultat, porté en 120 ou 129 par l'écriture
d'à-nouveaux, comme pour un exercice clos ici, et l'écran le dit.
L'attestation n'est pas celle du FEC : la balance n'est pas le fichier
d'origine, la personne qui reprend atteste avoir vérifié les soldes lus.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

from .ouverture import CLASSES_DE_BILAN, ecriture_a_nouveaux
from .ouverture_fec import Analyse, verifier_correspondance

_COMPTE_PCG = re.compile(r"^[1-7]\d{2,}$")


def _euros(centimes: int) -> str:
    texte = f"{abs(centimes) / 100:,.2f}".replace(",", " ").replace(".", ",")
    return f"{'-' if centimes < 0 else ''}{texte} €"


def _traduits(
    soldes: Mapping[str, int], correspondance: Mapping[str, str]
) -> tuple[dict[str, int], tuple[str, ...]]:
    inconnus = sorted(c for c in soldes if not _COMPTE_PCG.match(c) and c not in correspondance)
    traduits: dict[str, int] = {}
    for compte, solde in soldes.items():
        cible = correspondance.get(compte, compte)
        traduits[cible] = traduits.get(cible, 0) + solde
    return traduits, tuple(inconnus)


def _ecriture(dossier_id: DossierId, traduits: Mapping[str, int], cloture: date) -> Ecriture:
    lignes = tuple(
        LigneEcriture(
            compte=compte,
            sens=Sens.DEBIT if solde > 0 else Sens.CREDIT,
            montant=Money(abs(solde)),
        )
        for compte, solde in sorted(traduits.items())
        if solde and _COMPTE_PCG.match(compte)
    )
    return Ecriture(
        id=EcritureId(f"{dossier_id}:balance:{cloture.isoformat()}"),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=cloture,
        libelle=f"Balance au {cloture:%d/%m/%Y}",
        reference_piece=None,
        lignes=lignes,
    )


def _refus(
    soldes: Mapping[str, int], cloture: date, ouverture: date, inconnus: tuple[str, ...]
) -> list[str]:
    refus = []
    veille = ouverture - timedelta(days=1)
    if cloture != veille:
        refus.append(
            f"Cette balance est arrêtée au {cloture:%d/%m/%Y} ; il faut celle de l'exercice clos "
            f"la veille de l'ouverture dans AxeLCompta, le {veille:%d/%m/%Y}."
        )
    ecart = sum(soldes.values())
    if ecart:
        refus.append(f"La balance ne s'équilibre pas : écart de {_euros(ecart)}.")
    if inconnus:
        refus.append(
            "Comptes à faire correspondre au plan comptable : " + ", ".join(inconnus) + "."
        )
    if not any(c.startswith(CLASSES_DE_BILAN) and s for c, s in soldes.items()):
        refus.append("Aucun solde de bilan à reprendre.")
    return refus


def _alertes(traduits: Mapping[str, int], cloture: date, resultat: int) -> list[str]:
    alertes = []
    if resultat:
        compte = "120" if resultat > 0 else "129"
        alertes.append(
            "Balance arrêtée avant l'affectation du résultat : "
            f"{_euros(resultat)} porté en {compte}, à affecter ensuite."
        )
    if -sum(s for c, s in traduits.items() if c.startswith("10")) <= 0:
        alertes.append("Aucun capital (comptes 101 à 108) : vérifiez que la balance est complète.")
    if any(c.startswith("512") for c in traduits):
        banque = sum(s for c, s in traduits.items() if c.startswith("512"))
        alertes.append(
            f"Solde de banque au {cloture:%d/%m/%Y} : {_euros(banque)}. "
            "Comparez-le à votre relevé bancaire de cette date."
        )
    else:
        alertes.append("Aucun compte de banque (512) : vérifiez que la balance est complète.")
    return alertes


def analyser_balance(
    soldes: Mapping[str, int],
    cloture: date,
    empreinte_source: str,
    dossier_id: DossierId,
    ouverture: date,
    correspondance: Mapping[str, str],
) -> Analyse:
    """Contrôle la balance et prépare l'écriture d'à-nouveaux ; les refus et
    les alertes s'affichent tous d'un coup, comme pour un FEC."""
    verifier_correspondance(correspondance)
    traduits, inconnus = _traduits(soldes, correspondance)
    refus = _refus(soldes, cloture, ouverture, inconnus)
    ecriture = _ecriture(dossier_id, traduits, cloture)
    resultat = -sum(s for c, s in traduits.items() if c.startswith(("6", "7")))
    a_nouveaux = None if refus else ecriture_a_nouveaux(dossier_id, (ecriture,), ouverture)
    return Analyse(
        empreinte=empreinte_source,
        siren="",
        cloture=cloture,
        ouverture=ouverture,
        nb_lignes=len(soldes),
        nb_ecritures=1,
        total_debit=sum(s for s in soldes.values() if s > 0),
        resultat=resultat,
        solde_banque=sum(s for c, s in traduits.items() if c.startswith("512")),
        capital=-sum(s for c, s in traduits.items() if c.startswith("10")),
        comptes_inconnus=inconnus,
        refus=tuple(refus),
        alertes=tuple(_alertes(traduits, cloture, resultat)),
        a_nouveaux=a_nouveaux,
        source="balance",
    )
