"""Une ligne de log, un objet JSON (doc 15 §4)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import TextIO


def ecrire(
    niveau: str,
    module: str,
    evenement: str,
    *,
    sortie: TextIO | None = None,
    **champs: object,
) -> None:
    """N'écrit que les champs déjà passés. L'appelant ne met pas de libellé,
    de nom ou d'IBAN brut : ce journal n'est pas une porte vers un LLM,
    mais il part quand même hors du dossier."""
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": niveau,
        "module": module,
        "event": evenement,
        **champs,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), file=sortie or sys.stdout)
