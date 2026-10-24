"""Contrôles avant stockage : taille, extension, segments de chemin."""

from __future__ import annotations

import hashlib
import re

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId, EcritureId, TenantId

from .models import Justificatif

TAILLE_MAX_OCTETS = 8 * 1024 * 1024
_EXTENSION = re.compile(r"\.[a-z0-9]{1,8}")


class JustificatifRefuse(DomaineError):
    """Photo vide, trop lourde, ou identifiant qui sortirait du dossier."""


def _segment(valeur: str) -> str:
    if not valeur or valeur in {".", ".."} or any(caractere in valeur for caractere in "/\\\x00"):
        raise JustificatifRefuse("Identifiant de stockage refusé.")
    return valeur


def preparer(
    tenant_id: TenantId,
    dossier_id: DossierId,
    ecriture_id: EcritureId,
    contenu: bytes,
    extension: str,
) -> Justificatif:
    if not contenu or len(contenu) > TAILLE_MAX_OCTETS:
        raise JustificatifRefuse("La photo est vide ou dépasse 8 Mo.")
    normalisee = extension.lower()
    if _EXTENSION.fullmatch(normalisee) is None:
        raise JustificatifRefuse("Extension refusée.")
    _segment(tenant_id)
    _segment(dossier_id)
    _segment(ecriture_id)
    return Justificatif(
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        ecriture_id=ecriture_id,
        empreinte=hashlib.sha256(contenu).hexdigest(),
        extension=normalisee,
        taille_octets=len(contenu),
    )
