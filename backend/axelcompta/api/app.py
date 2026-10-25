"""Point d'entrée HTTP du produit.

Les corps de routes vivent encore dans `demo_api` (composition root).
Ce module est la façade : uvicorn pointe ici, et `/sante` est à nous.
Chaque route migrera vers la façade publique de son module, une par une.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    # Import local : demo_api construit son app au chargement, et ne doit
    # pas être tiré par un simple import de ce module.
    from axelcompta import demo_api

    app: FastAPI = demo_api.app
    if not any(getattr(route, "path", "") == "/sante" for route in app.routes):

        @app.get("/sante")
        def sante() -> dict[str, str]:
            return {"statut": "ok"}

    return app


app = create_app()
