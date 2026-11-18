"""L'appel à Claude pour l'OCR (AXE-943).

Un message : le document (PDF en bloc `document`, image en bloc `image`),
la consigne de sa catégorie, et le schéma JSON imposé (`output_config`).
Effort `low` : lire n'a pas besoin de longue réflexion. Sonnet a le repli
côté serveur en cas de refus ; Haiku n'en a pas, son refus fait relire par
Sonnet. La clé et le workspace viennent de l'environnement, comme pour
l'étage LLM de la catégorisation (AXE-887).
"""

from __future__ import annotations

import base64
import json
from typing import Any

from axelcompta.pseudonymize.fournisseur_anthropic import BETA_REPLI, cout, entetes_anthropic

from .categories import Categorie
from .lecture import SONNET, Appel, Appeler

MEDIA_IMAGES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
MEDIA_LISIBLES = MEDIA_IMAGES | {"application/pdf"}


def bloc(contenu: bytes, media_type: str) -> dict[str, Any]:
    source = {
        "type": "base64",
        "media_type": media_type,
        "data": base64.standard_b64encode(contenu).decode(),
    }
    return {"type": "image" if media_type in MEDIA_IMAGES else "document", "source": source}


def parametres(
    modele: str, categorie: Categorie, contenu: bytes, media_type: str
) -> dict[str, Any]:
    parametres: dict[str, Any] = {
        "model": modele,
        "max_tokens": categorie.max_tokens,
        "system": categorie.consigne_complete(),
        "output_config": {
            "effort": "low",
            "format": {"type": "json_schema", "schema": categorie.schema()},
        },
        "messages": [
            {
                "role": "user",
                "content": [
                    bloc(contenu, media_type),
                    {"type": "text", "text": "Lis ce document et rends le JSON demandé."},
                ],
            }
        ],
    }
    if modele == SONNET:
        parametres["betas"] = [BETA_REPLI]
        parametres["fallbacks"] = "default"
    return parametres


def appeler_anthropic(messages: Any = None) -> Appeler:
    """L'appel réel ; `messages` remplace `client.beta.messages` dans les tests."""
    if messages is None:
        import anthropic

        options: dict[str, Any] = {"max_retries": 2}
        if entetes := entetes_anthropic():
            options["default_headers"] = entetes
        messages = anthropic.Anthropic(**options).beta.messages

    def appeler(modele: str, categorie: Categorie, contenu: bytes, media_type: str) -> Appel:
        try:
            reponse = messages.create(**parametres(modele, categorie, contenu, media_type))
        except Exception as exc:  # noqa: BLE001 — une erreur d'API fait relire, jamais planter
            statut = getattr(exc, "status_code", None)
            return Appel(None, 0.0, f"Lecture impossible ({statut or type(exc).__name__}).")
        usage = reponse.usage
        entree = sum(
            int(getattr(usage, c, 0) or 0)
            for c in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        depense = cout(modele, entree, int(usage.output_tokens))
        if reponse.stop_reason != "end_turn":
            return Appel(None, depense, f"Réponse inutilisable ({reponse.stop_reason}).")
        texte = next((b.text for b in reponse.content if b.type == "text"), "")
        try:
            lu = json.loads(texte)
        except ValueError:
            return Appel(None, depense, "Réponse illisible.")
        return Appel(lu if isinstance(lu, dict) else None, depense, "")

    return appeler
