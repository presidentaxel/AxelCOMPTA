"""Webhooks Rollee (AXE-820) : vérifier, garder, puis traiter plus tard.

Rollee prévient quand un compte est relié ou perdu (`connect_account`,
`disconnect_account`…), et quand des données sont prêtes
(`update_multi_endpoint`, `update_endpoint`). Les événements ne portent pas
les données : l'API reste la source. Rollee réessaie 3 fois si on répond
lentement (> 10 s) ou en erreur, puis abandonne : on répond tout de suite,
on garde l'événement, la file de jobs le traite, et un rattrapage quotidien
couvre ce qui se serait perdu.

Signature : `X-Signature`, HMAC SHA-512 avec le secret qu'on a donné à
Rollee en configurant le webhook. La doc ne dit pas ce qui est signé ni
l'encodage : on vérifie le corps brut, en hexadécimal ou en base64. À
confirmer au premier webhook sandbox (AXE-817).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol

from axelcompta.core.ids import TenantId

TYPES_COMPTES = frozenset(
    {"create_account", "update_account", "connect_account", "disconnect_account", "delete_account"}
)
TYPES_DONNEES = frozenset({"update_endpoint", "update_multi_endpoint"})


def signature_valide(secret: str, corps: bytes, signature: str | None) -> bool:
    if not secret or not signature:
        return False
    empreinte = hmac.new(secret.encode(), corps, hashlib.sha512).digest()
    attendues = (empreinte.hex(), base64.b64encode(empreinte).decode())
    recue = signature.strip()
    if recue.lower().startswith("sha512="):
        recue = recue[len("sha512=") :]
    return any(hmac.compare_digest(recue, attendue) for attendue in attendues)


@dataclass(frozen=True, slots=True)
class EvenementRollee:
    id: str  # empreinte du corps : un webhook rejoué n'est gardé qu'une fois
    tenant_id: TenantId
    branchement_id: str
    type: str
    payload: dict[str, Any]
    recu_le: datetime
    traite_le: datetime | None = None
    resultat: str | None = None

    @property
    def users(self) -> tuple[str, ...]:
        """Les users Rollee concernés (un seul, ou plusieurs avec `accounts`)."""
        data = self.payload.get("data") or {}
        if not isinstance(data, dict):
            return ()
        trouves = [data.get("user_id")]
        trouves += [a.get("user_id") for a in data.get("accounts") or [] if isinstance(a, dict)]
        return tuple(dict.fromkeys(str(u) for u in trouves if u))


class EvenementIllisible(ValueError):
    """Le corps n'est pas du JSON, ou n'a pas de type."""


def lire(
    corps: bytes, tenant_id: TenantId, branchement_id: str, recu_le: datetime
) -> EvenementRollee:
    """Le type est sous `action` (événements de comptes) ou `type` (les
    autres) : la doc Rollee montre les deux."""
    try:
        payload = json.loads(corps)
    except ValueError as exc:
        raise EvenementIllisible("corps illisible") from exc
    if not isinstance(payload, dict):
        raise EvenementIllisible("corps inattendu")
    type_ = payload.get("type") or payload.get("action")
    if not isinstance(type_, str) or not type_:
        raise EvenementIllisible("événement sans type")
    return EvenementRollee(
        id=hashlib.sha256(corps).hexdigest(),
        tenant_id=tenant_id,
        branchement_id=branchement_id,
        type=type_,
        payload=payload,
        recu_le=recu_le,
    )


class EvenementsRolleeRepository(Protocol):
    def garder(self, evenement: EvenementRollee) -> bool:
        """`False` si déjà reçu (même corps) : rien n'est refait."""
        ...

    def a_traiter(self, tenant_id: TenantId, limite: int) -> list[EvenementRollee]: ...

    def marquer_traite(self, evenement_id: str, resultat: str, le: datetime) -> None: ...


@dataclass
class EvenementsRolleeMemoire:
    evenements: dict[str, EvenementRollee] = field(default_factory=dict)

    def garder(self, evenement: EvenementRollee) -> bool:
        if evenement.id in self.evenements:
            return False
        self.evenements[evenement.id] = evenement
        return True

    def a_traiter(self, tenant_id: TenantId, limite: int) -> list[EvenementRollee]:
        attente = [
            e for e in self.evenements.values() if e.tenant_id == tenant_id and e.traite_le is None
        ]
        return sorted(attente, key=lambda e: e.recu_le)[:limite]

    def marquer_traite(self, evenement_id: str, resultat: str, le: datetime) -> None:
        self.evenements[evenement_id] = replace(
            self.evenements[evenement_id], traite_le=le, resultat=resultat
        )


def resume(traites: Sequence[str]) -> str:
    if len(traites) <= 1:
        return f"{len(traites)} événement Rollee traité"
    return f"{len(traites)} événements Rollee traités"
