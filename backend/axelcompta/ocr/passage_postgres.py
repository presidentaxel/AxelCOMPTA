"""Le passage OCR avec les vrais dépôts (worker, rôle propriétaire)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from axelcompta.core.ids import TenantId
from axelcompta.stockage_documents import depot_documents
from axelcompta.tenants.fiches_import_postgres import PostgresFichesImport

from .client import appeler_anthropic
from .passage import ocr_actif, passer, plafond_mois


def passer_ocr(engine: Engine, tenant_id: TenantId) -> str:
    """Le résumé pour le journal des tâches ; « » si l'OCR est éteint ou
    s'il n'y avait rien à lire."""
    if not ocr_actif():
        return ""
    bilan = passer(
        PostgresFichesImport(engine, depot_documents()),
        tenant_id,
        appeler_anthropic(),
        datetime.now(UTC),
        plafond_mois(),
    )
    return bilan.phrase()
