"""Point d'entrée HTTP du produit.

Les corps de routes vivent encore dans `demo_api` (composition root).
Ce module est la façade : uvicorn pointe ici, et `/sante` est à nous.
Chaque route migrera vers la façade publique de son module, une par une.
"""

from __future__ import annotations

from fastapi import FastAPI

from axelcompta.core.schema import tete_unique, verification_demandee, verifier_schema


def verifier_schema_au_demarrage() -> None:
    """Refuse de démarrer sur une base en retard (AXE-841). Lu au démarrage
    du serveur, pas à l'import : les tests importent l'app sans base."""
    if not verification_demandee():
        return
    from axelcompta import demo_api

    verifier_schema(demo_api._engine(), tete_unique())


def recuperer_modele_au_demarrage() -> None:
    """Récupère le modèle de catégorisation s'il manque (AXE-847). Au
    démarrage du serveur, pas à l'import : les tests importent l'app. Ne
    lève jamais : sans modèle, l'API sert les écrans avec les règles seules."""
    from axelcompta.modeles_distants import assurer_modele

    assurer_modele()


def create_app() -> FastAPI:
    # Import local : demo_api construit son app au chargement, et ne doit
    # pas être tiré par un simple import de ce module.
    from axelcompta import demo_api

    app: FastAPI = demo_api.app
    if verifier_schema_au_demarrage not in app.router.on_startup:
        app.router.on_startup.append(verifier_schema_au_demarrage)
    if recuperer_modele_au_demarrage not in app.router.on_startup:
        app.router.on_startup.append(recuperer_modele_au_demarrage)
    if not any(getattr(route, "path", "") == "/sante" for route in app.routes):

        @app.get("/sante")
        def sante() -> dict[str, str]:
            return {"statut": "ok"}

    return app


app = create_app()
