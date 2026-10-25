"""TOTP (RFC 6238, SHA-1, pas de 30 s). Pas de dépendance externe."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct

PAS_SECONDES = 30


def secret_aleatoire() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def code_totp(secret: str, moment: int, pas: int = PAS_SECONDES) -> str:
    cle = _cle(secret)
    compteur = moment // pas
    digest = hmac.new(cle, struct.pack(">Q", compteur), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    morceau = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return f"{morceau % 1_000_000:06d}"


def verifier_totp(secret: str, code: str, moment: int, fenetre: int = 1) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    for decalage in range(-fenetre, fenetre + 1):
        if hmac.compare_digest(code_totp(secret, moment + decalage * PAS_SECONDES), code):
            return True
    return False


def _cle(secret: str) -> bytes:
    rembourrage = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret.upper() + rembourrage, casefold=True)
