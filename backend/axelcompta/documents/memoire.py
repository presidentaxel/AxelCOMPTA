"""Stockage en mémoire, cloisonné par tenant et dossier."""

from __future__ import annotations

from axelcompta.core.ids import DossierId, EcritureId, TenantId

from .models import Justificatif


class StockageMemoire:
    def __init__(self) -> None:
        self._photos: dict[tuple[str, str, str], bytes] = {}

    def poser(self, justificatif: Justificatif, contenu: bytes) -> None:
        self._photos[self._cle(justificatif)] = contenu

    def contient(self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId) -> bool:
        return (tenant_id, dossier_id, ecriture_id) in self._photos

    def presents(self, tenant_id: TenantId, dossier_id: DossierId) -> frozenset[EcritureId]:
        return frozenset(
            EcritureId(ecriture)
            for tenant, dossier, ecriture in self._photos
            if tenant == tenant_id and dossier == dossier_id
        )

    def lire(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> bytes | None:
        return self._photos.get((tenant_id, dossier_id, ecriture_id))

    @staticmethod
    def _cle(justificatif: Justificatif) -> tuple[str, str, str]:
        return (justificatif.tenant_id, justificatif.dossier_id, justificatif.ecriture_id)
