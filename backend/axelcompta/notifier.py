"""Pose dans l'application la notification « des opérations sont à traiter »
(doc 19 §5.2) pour tout un portefeuille.

Composition root comme `synchro_digifactory.py` (doc 18). Lancé par les
tâches planifiées (`axelcompta.taches`), après la synchro, ou à la main. Les
règles anti-harcèlement (regroupement, intervalle, rappel) sont dans
`workflow/notifications.py` ; ce module ne fait que câbler. Aucun e-mail :
les notifications sont internes (Louis, 2026-09-26), l'e-mail et le SMS
sont des intégrations du gestionnaire.

Usage, depuis backend/ (DATABASE_URL défini) :

    python -m axelcompta.notifier --tenant <tenant_id>
    python -m axelcompta.notifier --tenant <tenant_id> --simulation
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.consentement import ReleveConsentement
from axelcompta.ingestion.consentement_postgres import PostgresConsentementRepository
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.decisions import DecisionRepository
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.notifications import (
    TYPE_A_TRANCHER,
    InMemoryNotificationRepository,
    NotificationRepository,
    ResultatNotification,
    notifier_a_trancher,
    notifier_cloture_a_valider,
)
from axelcompta.workflow.notifications_postgres import PostgresNotificationRepository
from axelcompta.workflow.relances_consentement import notifier_consentement


def notifier_portefeuille(
    dossiers: tuple[Dossier, ...],
    ledger: LedgerService,
    decisions: DecisionRepository,
    notifications: NotificationRepository,
    maintenant: datetime,
    tenant: Tenant | None = None,
    consentements: Mapping[DossierId, ReleveConsentement] | None = None,
) -> list[ResultatNotification]:
    """`consentements` à None saute les relances de connexion bancaire."""
    resultats: list[ResultatNotification] = []
    for dossier in dossiers:
        try:
            resultats.append(
                notifier_a_trancher(dossier.id, ledger, decisions, notifications, maintenant)
            )
            resultats.append(
                notifier_cloture_a_valider(
                    dossier.id, dossier.fin_exercice(), notifications, maintenant
                )
            )
            if consentements is not None:
                resultats.append(
                    notifier_consentement(
                        dossier, tenant, consentements.get(dossier.id), notifications, maintenant
                    )
                )
        except Exception as exc:  # noqa: BLE001 — un dossier en échec ne bloque pas les autres
            resultats.append(ResultatNotification(dossier.id, "echec", detail=type(exc).__name__))
    return resultats


def notifier_depuis_base(
    engine: Engine, dossiers: tuple[Dossier, ...], simulation: bool = False
) -> list[ResultatNotification]:
    """`simulation` calcule sans rien enregistrer."""
    notifications: NotificationRepository = (
        InMemoryNotificationRepository() if simulation else PostgresNotificationRepository(engine)
    )
    tenant = (
        PostgresDossierRepository(engine).obtenir_tenant(dossiers[0].tenant_id)
        if dossiers
        else None
    )
    return notifier_portefeuille(
        dossiers,
        PostgresLedgerService(engine),
        PostgresDecisionRepository(engine),
        notifications,
        datetime.now(UTC).replace(tzinfo=None),
        tenant,
        PostgresConsentementRepository(engine).lister([d.id for d in dossiers]),
    )


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--tenant", required=True)
    parseur.add_argument(
        "--simulation",
        action="store_true",
        help="calcule et affiche sans rien enregistrer",
    )
    args = parseur.parse_args()

    engine = engine_depuis_env()
    dossiers = PostgresDossierRepository(engine).lister_par_tenant(TenantId(args.tenant))
    resultats = notifier_depuis_base(engine, dossiers, args.simulation)
    for r in resultats:
        detail = f" ({r.detail})" if r.detail else ""
        compte = f", {r.nb_a_trancher} à trancher" if r.type == TYPE_A_TRANCHER else ""
        print(f"{r.dossier_id} : {r.type} {r.statut}{compte}{detail}")
    return 1 if any(r.statut == "echec" for r in resultats) else 0


if __name__ == "__main__":
    sys.exit(main())
