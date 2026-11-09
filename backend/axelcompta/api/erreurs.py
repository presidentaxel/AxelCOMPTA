"""Les erreurs métier répondent 4xx avec leur phrase, jamais 500 (AXE-839).

Un seul gestionnaire pour `DomaineError` : le code HTTP vient de la famille
de l'erreur (`core.errors`), 400 par défaut. Une route n'a plus besoin de
rattraper une erreur métier pour la traduire ; un oubli ne fait plus de 500.
Un bug (`InvariantViole`, toute autre exception) reste un 500.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from axelcompta.core.errors import Conflit, DomaineError, Introuvable, SaisieInvalide

_STATUT_PAR_FAMILLE: tuple[tuple[type[DomaineError], int], ...] = (
    (Conflit, 409),
    (Introuvable, 404),
    (SaisieInvalide, 422),
)


def statut_de(erreur: DomaineError) -> int:
    return next((s for famille, s in _STATUT_PAR_FAMILLE if isinstance(erreur, famille)), 400)


async def repondre_erreur_metier(_requete: Request, erreur: Exception) -> JSONResponse:
    assert isinstance(erreur, DomaineError)
    return JSONResponse(status_code=statut_de(erreur), content={"detail": str(erreur)})


def brancher_erreurs(app: FastAPI) -> None:
    app.add_exception_handler(DomaineError, repondre_erreur_metier)
