"""Le jour civil des personnes qui utilisent l'application (AXE-920).

Le serveur et la CI tournent en UTC : entre minuit et 1 h (2 h l'été),
`datetime.now(UTC).date()` est encore la veille à Paris. Une date saisie par
un humain (versement de dividendes, fin d'exercice) se compare au jour de
Paris, sinon « aujourd'hui » passe pour une date future.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def aujourd_hui_paris(maintenant: datetime | None = None) -> date:
    """Le jour civil à Paris. `maintenant` (avec fuseau) sert aux tests."""
    return (maintenant or datetime.now(UTC)).astimezone(PARIS).date()
