"""Fichiers sous `<racine>/<tenant>/<dossier>/<écriture><extension>`."""

from __future__ import annotations

from pathlib import Path

from axelcompta.core.ids import DossierId, EcritureId, TenantId

from .models import Justificatif
from .preparer import JustificatifRefuse


class StockageFichier:
    def __init__(self, racine: Path) -> None:
        self._racine = racine

    def poser(self, justificatif: Justificatif, contenu: bytes) -> None:
        chemin = self._chemin(justificatif)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)

    def contient(self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId) -> bool:
        return ecriture_id in self.presents(tenant_id, dossier_id)

    def presents(self, tenant_id: TenantId, dossier_id: DossierId) -> frozenset[EcritureId]:
        dossier = self._racine / tenant_id / dossier_id
        if not dossier.is_dir():
            return frozenset()
        return frozenset(
            EcritureId(chemin.stem) for chemin in dossier.iterdir() if chemin.is_file()
        )

    def lire(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> bytes | None:
        dossier = self._racine / tenant_id / dossier_id
        if not dossier.is_dir():
            return None
        for chemin in dossier.iterdir():
            if chemin.stem == ecriture_id and chemin.is_file():
                return chemin.read_bytes()
        return None

    def _chemin(self, justificatif: Justificatif) -> Path:
        racine = self._racine.resolve()
        chemin = (
            racine / justificatif.tenant_id / justificatif.dossier_id
        ) / f"{justificatif.ecriture_id}{justificatif.extension}"
        if not chemin.resolve().is_relative_to(racine):
            raise JustificatifRefuse("Chemin de stockage refusé.")
        return chemin
