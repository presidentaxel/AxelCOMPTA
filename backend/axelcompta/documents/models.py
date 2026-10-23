"""Justificatif déposé pour une écriture. Le contenu n'est pas interprété."""

from __future__ import annotations

from dataclasses import dataclass

from axelcompta.core.ids import DossierId, EcritureId, TenantId


@dataclass(frozen=True, slots=True)
class Justificatif:
    tenant_id: TenantId
    dossier_id: DossierId
    ecriture_id: EcritureId
    empreinte: str
    extension: str
    taille_octets: int
