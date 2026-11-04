"""Implémentation Postgres de AgregatsRepository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from . import agregats
from .agregats import AgregatsRepository, AgregatStocke, LigneAgregat
from .orm import agregats_dossier as table


def _iso(valeur: date | None) -> str | None:
    return valeur.isoformat() if valeur is not None else None


def _valeur_de(ligne: Row[tuple[object, ...]]) -> AgregatStocke:
    return AgregatStocke(
        ca_ht_cts=ligne.ca_ht_cts,
        charges_cts=ligne.charges_cts,
        resultat_cts=ligne.resultat_cts,
        exercice_debut=_iso(ligne.exercice_debut),
        exercice_fin=_iso(ligne.exercice_fin),
        alerte_tva=ligne.alerte_tva,
    )


def _colonnes(valeur: AgregatStocke) -> dict[str, object]:
    return {
        "a_jour": True,
        "version_calcul": agregats.VERSION_CALCUL,
        "ca_ht_cts": valeur.ca_ht_cts,
        "charges_cts": valeur.charges_cts,
        "resultat_cts": valeur.resultat_cts,
        "exercice_debut": date.fromisoformat(valeur.exercice_debut)
        if valeur.exercice_debut
        else None,
        "exercice_fin": date.fromisoformat(valeur.exercice_fin) if valeur.exercice_fin else None,
        "alerte_tva": valeur.alerte_tva,
        "calcule_le": datetime.now(UTC),
    }


class PostgresAgregatsRepository(AgregatsRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, LigneAgregat]:
        if not dossier_ids:
            return {}
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table).where(table.c.dossier_id.in_(list(dossier_ids)))
            ).all()
        return {
            DossierId(ligne.dossier_id): LigneAgregat(
                version=ligne.version,
                valeur=_valeur_de(ligne)
                if ligne.a_jour and ligne.version_calcul == agregats.VERSION_CALCUL
                else None,
            )
            for ligne in lignes
        }

    def enregistrer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        valeur: AgregatStocke,
        version_lue: int | None,
    ) -> bool:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            if version_lue is None:
                # Une ligne apparue entre-temps, même périmée, a raison : le
                # calcul n'est pas gardé.
                resultat = connexion.execute(
                    pg_insert(table)
                    .values(
                        dossier_id=dossier_id, tenant_id=tenant_id, version=0, **_colonnes(valeur)
                    )
                    .on_conflict_do_nothing(index_elements=["dossier_id"])
                )
            else:
                resultat = connexion.execute(
                    update(table)
                    .where(table.c.dossier_id == dossier_id, table.c.version == version_lue)
                    .values(**_colonnes(valeur))
                )
        return resultat.rowcount == 1
