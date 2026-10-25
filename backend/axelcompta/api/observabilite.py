"""Sentry et métriques HTTP, branchés sur l'application qui sert le front.

Sentry ne démarre que si `SENTRY_DSN` est posé. Sans DSN, rien n'est envoyé.
"""

from __future__ import annotations

import os
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from axelcompta.core.metriques import METRIQUES

Suite = Callable[[Request], Awaitable[Response]]


def installer_sentry(dsn: str | None = None) -> bool:
    effectif = os.environ.get("SENTRY_DSN") if dsn is None else dsn
    if not effectif:
        return False
    try:
        import sentry_sdk
    except ImportError:
        return False
    sentry_sdk.init(dsn=effectif, send_default_pii=False)
    return True


def brancher(app: FastAPI) -> None:
    installer_sentry()

    @app.middleware("http")
    async def mesurer(requete: Request, suite: Suite) -> Response:
        debut = time.perf_counter()
        try:
            reponse = await suite(requete)
        except Exception:
            METRIQUES.incrementer("http_request_count", method=requete.method, status="500")
            raise
        duree_ms = (time.perf_counter() - debut) * 1000
        METRIQUES.incrementer(
            "http_request_count", method=requete.method, status=str(reponse.status_code)
        )
        METRIQUES.incrementer("http_request_duration_ms", duree_ms, method=requete.method)
        return reponse

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return METRIQUES.texte()
