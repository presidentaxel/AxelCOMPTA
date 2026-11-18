"""AXE-943 : l'appel à Claude, avec un client factice."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from axelcompta.ocr.client import appeler_anthropic, bloc, parametres
from axelcompta.ocr.documents import KBIS
from axelcompta.ocr.lecture import HAIKU, SONNET


class _Messages:
    def __init__(self, reponse: Any = None, erreur: Exception | None = None) -> None:
        self.reponse, self.erreur = reponse, erreur
        self.recus: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.recus.append(kwargs)
        if self.erreur:
            raise self.erreur
        return self.reponse


def _reponse(texte: str, stop: str = "end_turn") -> Any:
    usage = SimpleNamespace(input_tokens=10_000, output_tokens=500)
    return SimpleNamespace(
        stop_reason=stop, usage=usage, content=[SimpleNamespace(type="text", text=texte)]
    )


def test_un_pdf_part_en_document_et_une_image_en_image() -> None:
    assert bloc(b"%PDF", "application/pdf")["type"] == "document"
    assert bloc(b"\xff\xd8\xff", "image/jpeg")["type"] == "image"


def test_sonnet_a_le_repli_serveur_haiku_non() -> None:
    assert "fallbacks" not in parametres(HAIKU, KBIS, b"%PDF", "application/pdf")
    p = parametres(SONNET, KBIS, b"%PDF", "application/pdf")
    assert p["fallbacks"] == "default"
    assert p["output_config"]["format"]["schema"] == KBIS.schema()


def test_une_lecture_et_son_cout() -> None:
    messages = _Messages(_reponse(json.dumps({"siren": "908771033"})))
    appel = appeler_anthropic(messages)(HAIKU, KBIS, b"%PDF", "application/pdf")
    assert appel.lu == {"siren": "908771033"}
    assert round(appel.cout_usd, 5) == round((10_000 * 0.1 + 500 * 0.5) / 1e6, 5)


def test_un_refus_ou_une_erreur_ne_plante_pas() -> None:
    refus = appeler_anthropic(_Messages(_reponse("", "refusal")))(
        HAIKU, KBIS, b"%PDF", "application/pdf"
    )
    assert (refus.lu, refus.erreur) == (None, "Réponse inutilisable (refusal).")
    panne = appeler_anthropic(_Messages(erreur=RuntimeError("boom")))(
        HAIKU, KBIS, b"%PDF", "application/pdf"
    )
    assert panne.lu is None and "RuntimeError" in panne.erreur
