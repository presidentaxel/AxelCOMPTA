"""Relevés de plateformes en Postgres (AXE-821, migration `e8c3a1f6d9b4`)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import DossierId
from axelcompta.core.rls import appliquer_rls

from .orm import settlements_plateforme
from .providers.base import PlatformSettlement
from .settlements_plateforme import SettlementStocke


class PostgresSettlements:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(self, dossier_id: DossierId) -> list[SettlementStocke]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(settlements_plateforme)
                .where(settlements_plateforme.c.dossier_id == dossier_id)
                .order_by(settlements_plateforme.c.periode_debut, settlements_plateforme.c.id)
            ).all()
        return [_stocke(ligne) for ligne in lignes]

    def enregistrer(self, settlements: Sequence[SettlementStocke]) -> None:
        if not settlements:
            return
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            for stocke in settlements:
                valeurs = _valeurs(stocke)
                connexion.execute(
                    insert(settlements_plateforme)
                    .values(id=stocke.id, **valeurs)
                    .on_conflict_do_update(
                        index_elements=[settlements_plateforme.c.id], set_=valeurs
                    )
                )


def _valeurs(stocke: SettlementStocke) -> dict[str, Any]:
    s = stocke.settlement
    return {
        "dossier_id": s.dossier_id,
        "account_id": stocke.account_id,
        "plateforme": s.platform,
        "periode_debut": s.period_start,
        "periode_fin": s.period_end,
        "verse_le": s.payout_date,
        "brut_cts": s.gross_earnings_cts,
        "commission_cts": s.commission_cts,
        "regime_tva_commission": s.commission_tva_regime,
        "verse_cts": s.net_payout_cts,
        "devise": s.currency,
        "source": s.source_provider,
        "payload": s.raw_payload,
        "etat": stocke.etat,
        "ecriture_id": stocke.ecriture_id,
        "motif": stocke.motif,
        "maj_le": stocke.maj_le,
    }


def _stocke(ligne: Row[Any]) -> SettlementStocke:
    return SettlementStocke(
        id=ligne.id,
        account_id=ligne.account_id,
        settlement=PlatformSettlement(
            dossier_id=DossierId(ligne.dossier_id),
            platform=ligne.plateforme,
            period_start=ligne.periode_debut,
            period_end=ligne.periode_fin,
            payout_date=ligne.verse_le,
            gross_earnings_cts=ligne.brut_cts,
            commission_cts=ligne.commission_cts,
            commission_tva_regime=ligne.regime_tva_commission,
            net_payout_cts=ligne.verse_cts,
            currency=ligne.devise,
            source_provider=ligne.source,
            raw_payload=ligne.payload,
        ),
        etat=ligne.etat,
        maj_le=ligne.maj_le,
        ecriture_id=ligne.ecriture_id,
        motif=ligne.motif,
    )
