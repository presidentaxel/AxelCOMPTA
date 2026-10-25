"""Rôles V1 du portefeuille : lecture, membre, admin.

`lecture` consulte. `membre` tient les dossiers. `admin` gère l'équipe.
"""

from __future__ import annotations

ROLES_V1 = frozenset({"lecture", "membre", "admin"})

_DROITS: dict[str, frozenset[str]] = {
    "lecture": frozenset({"lire"}),
    "membre": frozenset({"lire", "ecrire"}),
    "admin": frozenset({"lire", "ecrire", "administrer"}),
}


def peut(role: str, action: str) -> bool:
    return action in _DROITS.get(role, frozenset())
