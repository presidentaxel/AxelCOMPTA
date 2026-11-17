"""AXE-970 : le bucket des documents d'import, à part de celui des modèles."""

from __future__ import annotations

from typing import Any

import pytest

from axelcompta import stockage_documents
from axelcompta.stockage_documents import BUCKET_DOCUMENTS, depot_documents_depuis_env


def test_sans_stockage_les_contenus_restent_en_base() -> None:
    assert depot_documents_depuis_env({}) is None


def test_le_bucket_des_documents_a_son_nom(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()
    monkeypatch.setattr(stockage_documents, "client_s3_depuis_env", lambda _env: client)
    depot: Any = depot_documents_depuis_env({})
    assert (depot._client, depot._bucket) == (client, BUCKET_DOCUMENTS)
    depot = depot_documents_depuis_env({"DOCUMENTS_BUCKET": "archives"})
    assert depot._bucket == "archives"
