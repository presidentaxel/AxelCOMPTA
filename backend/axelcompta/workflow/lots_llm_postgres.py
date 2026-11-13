"""`LotsLlm` et `AlertesLlm` sur Postgres (tables `lots_llm`, `alertes_llm`, AXE-887)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .budget_llm import Lot

_COLONNES = (
    "id, tenant_id, dossier_id, version, modele, cles, statut, estimation_usd, soumis_le, "
    "batch_id, cout_usd, jetons_entree, jetons_sortie, jetons_cache, termine_le"
)


def _utc(valeur: datetime | None) -> datetime | None:
    if valeur is None or valeur.tzinfo is not None:
        return valeur
    return valeur.replace(tzinfo=UTC)


def _lot(ligne: Row[Any]) -> Lot:
    soumis_le = _utc(ligne.soumis_le)
    assert soumis_le is not None
    return Lot(
        id=ligne.id,
        tenant_id=TenantId(ligne.tenant_id),
        dossier_id=DossierId(ligne.dossier_id),
        version=ligne.version,
        modele=ligne.modele,
        cles=tuple(ligne.cles),
        statut=ligne.statut,
        estimation_usd=float(ligne.estimation_usd),
        soumis_le=soumis_le,
        batch_id=ligne.batch_id,
        cout_usd=float(ligne.cout_usd),
        jetons_entree=ligne.jetons_entree,
        jetons_sortie=ligne.jetons_sortie,
        jetons_cache=ligne.jetons_cache,
        termine_le=_utc(ligne.termine_le),
    )


class PostgresLotsLlm:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(self, depuis: datetime) -> list[Lot]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)  # côté web : les lots de son portefeuille
            lignes = connexion.execute(
                text(
                    f"SELECT {_COLONNES} FROM lots_llm WHERE soumis_le >= :depuis "
                    "ORDER BY soumis_le, id"
                ),
                {"depuis": depuis},
            ).all()
        return [_lot(ligne) for ligne in lignes]

    def enregistrer(self, lots: Sequence[Lot]) -> None:
        if not lots:
            return
        valeurs = ", ".join(f":{c.strip()}" for c in _COLONNES.split(","))
        mises_a_jour = ", ".join(
            f"{c.strip()} = EXCLUDED.{c.strip()}" for c in _COLONNES.split(",")[1:]
        )
        with self._engine.begin() as connexion:
            connexion.execute(
                text(
                    f"INSERT INTO lots_llm ({_COLONNES}) VALUES ({valeurs}) "
                    f"ON CONFLICT (id) DO UPDATE SET {mises_a_jour}"
                ),
                [{**_valeurs(lot)} for lot in lots],
            )


def _valeurs(lot: Lot) -> dict[str, Any]:
    return {
        "id": lot.id,
        "tenant_id": str(lot.tenant_id),
        "dossier_id": str(lot.dossier_id),
        "version": lot.version,
        "modele": lot.modele,
        "cles": list(lot.cles),
        "statut": lot.statut,
        "estimation_usd": lot.estimation_usd,
        "soumis_le": lot.soumis_le,
        "batch_id": lot.batch_id,
        "cout_usd": lot.cout_usd,
        "jetons_entree": lot.jetons_entree,
        "jetons_sortie": lot.jetons_sortie,
        "jetons_cache": lot.jetons_cache,
        "termine_le": lot.termine_le,
    }


class PostgresAlertesLlm:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def marquer(self, portee: str, cle: str, mois: str, seuil: str, le: datetime) -> bool:
        with self._engine.begin() as connexion:
            inseree = connexion.execute(
                text(
                    "INSERT INTO alertes_llm (portee, cle, mois, seuil, envoyee_le) "
                    "VALUES (:portee, :cle, :mois, :seuil, :le) ON CONFLICT DO NOTHING"
                ),
                {"portee": portee, "cle": cle, "mois": mois, "seuil": seuil, "le": le},
            )
        return inseree.rowcount == 1
