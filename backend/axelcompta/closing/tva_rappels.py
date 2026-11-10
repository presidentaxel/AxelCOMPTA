"""Rappels de la déclaration de TVA dans la cloche du chauffeur (AXE-805).

J-7 puis J-2 avant l'échéance d'une période terminée et pas encore
déclarée. Une seule notification par palier et par période : relancer la
tâche planifiée toutes les heures ne répète rien. Un dossier sans jour
d'échéance réglé n'est pas relancé (le jour ne se devine pas).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date, datetime

from axelcompta.tenants.models import Dossier
from axelcompta.workflow.notifications import (
    TYPE_TVA_J2,
    TYPE_TVA_J7,
    NotificationEnvoyee,
    NotificationRepository,
    ResultatNotification,
)

from .tva_periodique import echeance, periodes_du_dossier, prochaine_a_declarer


def palier_tva(jours_restants: int) -> str | None:
    if 0 <= jours_restants <= 2:
        return TYPE_TVA_J2
    if 2 < jours_restants <= 7:
        return TYPE_TVA_J7
    return None


def notifier_tva(
    dossier: Dossier,
    declarees: Iterable[str],
    notifications: NotificationRepository,
    maintenant: datetime,
) -> ResultatNotification:
    aujourd_hui: date = maintenant.date()
    periode = prochaine_a_declarer(periodes_du_dossier(dossier), declarees, aujourd_hui)
    if periode is None or dossier.tva_jour_echeance is None:
        return ResultatNotification(dossier.id, "rien_a_faire", type=TYPE_TVA_J7)
    palier = palier_tva((echeance(periode, dossier.tva_jour_echeance) - aujourd_hui).days)
    if palier is None:
        return ResultatNotification(dossier.id, "rien_a_faire", type=TYPE_TVA_J7)
    derniere = notifications.derniere(dossier.id, palier)
    if derniere is not None and derniere.envoye_le.date() > periode.fin:
        return ResultatNotification(dossier.id, "deja_notifie", type=palier)
    notifications.enregistrer(
        NotificationEnvoyee(
            id=uuid.uuid4().hex,
            dossier_id=dossier.id,
            type=palier,
            envoye_le=maintenant,
            ecriture_ids=(),
        )
    )
    return ResultatNotification(dossier.id, "creee", type=palier)
