"""Taux de TVA choisi par l'expert-comptable (AXE-925).

La table du pack propose un taux. L'expert peut en retenir un autre pour
une seule ligne, ou pour toutes les lignes du même libellé : ce second
choix est l'apprentissage, relu aux affichages suivants. Rien ne s'écrit
dans le grand livre ici.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from axelcompta.categorize.appris import normaliser
from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.packs.tva_deductible import RegleTva, regle_tva, tva_recuperable

TAUX_CHOISIS = ("20", "10", "5.5", "2.1", "0")
OrigineTaux = Literal["table", "appris", "specifique"]


class TauxInconnu(DomaineError):
    """Le taux n'est pas l'un de ceux proposés à l'expert."""


def verifier_taux(taux: str) -> str:
    if taux not in TAUX_CHOISIS:
        raise TauxInconnu(f"Taux refusé : {taux}.")
    return taux


def cle_ligne(ecriture_id: str) -> str:
    return f"e:{ecriture_id}"


def cle_globale(libelle: str) -> str:
    return f"l:{normaliser(libelle) or '_'}"


def taux_de_la_table(categorie: str | None, jour: date, regime_tva: str) -> str | None:
    """Le taux proposé par la table, en pour cent, ou rien (franchise, inconnu)."""
    if not categorie:
        return None
    regle = regle_tva(categorie, jour, regime_tva)
    if regle is None:
        return None
    return format(regle.taux.normalize(), "f")


def resoudre_taux(
    specifique: str | None, appris: str | None, table: str | None
) -> tuple[str | None, OrigineTaux | None]:
    """La ligne d'abord, puis le libellé appris, puis la table."""
    if specifique:
        return specifique, "specifique"
    if appris:
        return appris, "appris"
    if table:
        return table, "table"
    return None, None


def montant_tva(montant_cts: int, taux: str) -> int:
    """TVA contenue dans le TTC au taux choisi, récupérée en entier."""
    if taux == "0":
        return 0
    regle = RegleTva(taux=Decimal(taux), recuperable=100)
    return tva_recuperable(abs(montant_cts), regle)


class TauxExpertRepository(Protocol):
    def pour_dossiers(
        self, tenant_id: TenantId, dossier_ids: Sequence[DossierId]
    ) -> dict[DossierId, dict[str, str]]: ...

    def poser(self, tenant_id: TenantId, dossier_id: DossierId, cle: str, taux: str) -> None: ...


class TauxExpertMemoire:
    def __init__(self) -> None:
        self._taux: dict[tuple[str, str, str], str] = {}

    def pour_dossiers(
        self, tenant_id: TenantId, dossier_ids: Sequence[DossierId]
    ) -> dict[DossierId, dict[str, str]]:
        voulus = set(dossier_ids)
        resultat: dict[DossierId, dict[str, str]] = {}
        for (tenant, dossier, cle), taux in self._taux.items():
            if tenant == tenant_id and DossierId(dossier) in voulus:
                resultat.setdefault(DossierId(dossier), {})[cle] = taux
        return resultat

    def poser(self, tenant_id: TenantId, dossier_id: DossierId, cle: str, taux: str) -> None:
        self._taux[(tenant_id, dossier_id, cle)] = verifier_taux(taux)
