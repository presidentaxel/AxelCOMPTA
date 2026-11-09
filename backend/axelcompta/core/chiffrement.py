"""Chiffrement des identifiants d'intégration, et jetons signés (AXE-808).

Les identifiants que le gestionnaire branche (mot de passe SMTP, clé d'API
d'un fournisseur de SMS) sont chiffrés en base (Fernet : AES-128-CBC +
HMAC-SHA256) et jamais renvoyés à l'écran. La clé vit dans l'environnement
(`AXELCOMPTA_CLE_INTEGRATIONS`), jamais en base : sans elle, rien ne se
branche et rien ne part, l'erreur le dit (doc 08 §2.7, pas de défaut
silencieux).

Générer une clé : `python -c "from cryptography.fernet import Fernet;
print(Fernet.generate_key().decode())"`.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken

VARIABLE_CLE = "AXELCOMPTA_CLE_INTEGRATIONS"


class CleAbsente(RuntimeError):
    """`AXELCOMPTA_CLE_INTEGRATIONS` n'est pas définie."""


class ChiffreIllisible(ValueError):
    """Le texte chiffré a été altéré, ou la clé a changé."""


def _cle(cle: str | None) -> bytes:
    valeur = cle if cle is not None else os.environ.get(VARIABLE_CLE)
    if not valeur:
        raise CleAbsente(f"{VARIABLE_CLE} manquante (voir .env.example)")
    return valeur.encode()


def chiffrer(texte: str, cle: str | None = None) -> str:
    return Fernet(_cle(cle)).encrypt(texte.encode()).decode()


def dechiffrer(jeton: str, cle: str | None = None) -> str:
    try:
        return Fernet(_cle(cle)).decrypt(jeton.encode()).decode()
    except InvalidToken as exc:
        raise ChiffreIllisible("identifiants illisibles : clé changée ou donnée altérée") from exc


def signer(message: str, cle: str | None = None) -> str:
    """Signature courte d'un message (lien de désinscription, par exemple)."""
    return hmac.new(_cle(cle), message.encode(), hashlib.sha256).hexdigest()[:32]


def signature_valide(message: str, signature: str, cle: str | None = None) -> bool:
    return hmac.compare_digest(signer(message, cle), signature)
