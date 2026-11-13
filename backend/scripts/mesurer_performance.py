"""Mesure p50/p95 des routes lentes sur un portefeuille synthétique (AXE-824).

Postgres **local** seulement (le script vide puis remplit un portefeuille) :
`DATABASE_URL` et `DATABASE_URL_WEB` pointent sur le Docker de dev. Les
routes passent par l'API réelle, sous le rôle `axelcompta_web` (RLS
comprise) ; seuls Supabase Auth et le stockage des justificatifs sont
remplacés.

    PYTHONPATH=. python scripts/mesurer_performance.py --dossiers 200 --ecritures 300

Imprime un tableau Markdown, à coller dans le ticket. AXE-843 : toutes les
routes de lecture appelées par le front, par profil (chauffeur,
gestionnaire admin, expert-comptable habilité), avec la cible du ticket
(p95 < 1 s, file expert < 2 s) ; `--route` limite à quelques routes.
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import jwt
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

import axelcompta.api.auth as demo_auth
import axelcompta.api.routes as demo_api
from axelcompta.comptes_memoire import InMemoryCompteRepository
from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.documents.justificatifs import InMemoryJustificatifRepository
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.expert_comptable import (
    ROLE_EXPERT,
    TEXTE_ENGAGEMENT,
    VERSION_ENGAGEMENT,
    Engagement,
    ExpertMemoire,
    Habilitation,
)

HOTES_LOCAUX = frozenset({"localhost", "127.0.0.1", "::1", "db"})
TENANT = "TENANT_PERF"
_CLE = ec.generate_private_key(ec.SECP256R1())
# (libellé, compte, part) : ~70 % classées, ~30 % au 471 (à trancher).
_MODELES = (
    ("CB TOTAL STATION", "6061", 0.35),
    ("PEAGE APRR", "6251", 0.15),
    ("VIR UBER BV", "706", 0.2),
    ("PAIEMENT INCONNU", "471", 0.3),
)


def _moteur_local(variable: str) -> Engine:
    url = os.environ.get(variable, "")
    moteur = create_engine(url)
    if moteur.url.host not in HOTES_LOCAUX:
        raise SystemExit(f"{variable} n'est pas une base locale : refusé.")
    return moteur


def _alembic() -> Config:
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(racine, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(racine, "migrations"))
    return cfg


def _vider(proprietaire: Engine) -> None:
    with proprietaire.begin() as connexion:
        connexion.execute(text("SET session_replication_role = replica"))  # verrous I2
        for requete in (
            "DELETE FROM lignes_ecriture WHERE ecriture_id IN "
            "(SELECT id FROM ecritures WHERE dossier_id LIKE 'PERF_%')",
            "DELETE FROM propositions_categorisation WHERE dossier_id LIKE 'PERF_%'",
            "DELETE FROM agregats_dossier WHERE dossier_id LIKE 'PERF_%'",
            "DELETE FROM ecritures WHERE dossier_id LIKE 'PERF_%'",
            "DELETE FROM dossiers WHERE id LIKE 'PERF_%'",
        ):
            connexion.execute(text(requete))
        connexion.execute(text("SET session_replication_role = origin"))


def _semer(proprietaire: Engine, nb_dossiers: int, nb_ecritures: int) -> None:
    hasard = random.Random(42)
    debut = date(2026, 1, 1)
    with proprietaire.begin() as connexion:
        connexion.execute(
            text("INSERT INTO tenants (id, nom) VALUES (:t, 'Perf') ON CONFLICT DO NOTHING"),
            {"t": TENANT},
        )
        for numero in range(nb_dossiers):
            dossier = f"PERF_{numero:03d}"
            connexion.execute(
                text(
                    "INSERT INTO dossiers (id, tenant_id, forme_juridique, regime_imposition, "
                    "regime_tva, nom, tva_recettes_regime, exercice_debut, plateformes, "
                    "mode_acces_bancaire) VALUES (:d, :t, 'SASU', 'IS', 'franchise', :n, "
                    "'franchise', :e, '[]', 'gestionnaire')"
                ),
                {"d": dossier, "t": TENANT, "n": f"Chauffeur {numero:03d}", "e": debut},
            )
            _semer_dossier(connexion, dossier, nb_ecritures, hasard)


def _semer_dossier(connexion: object, dossier: str, nb: int, hasard: random.Random) -> None:
    entetes, lignes, propositions = [], [], []
    for rang in range(nb):
        libelle, compte, _part = hasard.choices(_MODELES, [m[2] for m in _MODELES])[0]
        ecriture = f"{dossier}:perf-{rang}"
        montant = hasard.randint(500, 30_000)
        entree = compte == "706"
        entetes.append(
            {
                "id": ecriture,
                "dossier_id": dossier,
                "journal": "BQ",
                "date": date(2026, 1, 1) + timedelta(days=rang % 300),
                "libelle": f"{libelle} {rang}",
                "reference_piece": None,
            }
        )
        for compte_ligne, sens in (
            ("512", "DEBIT" if entree else "CREDIT"),
            (compte, "CREDIT" if entree else "DEBIT"),
        ):
            lignes.append(
                {
                    "id": str(uuid.uuid4()),
                    "ecriture_id": ecriture,
                    "compte": compte_ligne,
                    "sens": sens,
                    "montant_centimes": montant,
                    "devise": "EUR",
                }
            )
        propositions.append(
            {
                "ecriture_id": ecriture,
                "dossier_id": dossier,
                "categorie": "carburant" if compte == "6061" else "autre",
                "etage": "REGLE" if compte != "471" else "ML",
                "confiance": 0.97 if compte != "471" else 0.4,
            }
        )
    execute = connexion.execute  # type: ignore[attr-defined]
    execute(
        text(
            "INSERT INTO ecritures VALUES "
            "(:id, :dossier_id, :journal, :date, :libelle, :reference_piece)"
        ),
        entetes,
    )
    execute(
        text(
            "INSERT INTO lignes_ecriture (id, ecriture_id, compte, sens, montant_centimes, devise) "
            "VALUES (:id, :ecriture_id, :compte, :sens, :montant_centimes, :devise)"
        ),
        lignes,
    )
    execute(
        text(
            "INSERT INTO propositions_categorisation "
            "(ecriture_id, dossier_id, categorie, etage, confiance) "
            "VALUES (:ecriture_id, :dossier_id, :categorie, :etage, :confiance)"
        ),
        propositions,
    )


def _client(web: Engine) -> TestClient:
    os.environ.setdefault("SUPABASE_URL", "https://exemple.supabase.co")
    demo_auth._jwks_client = lambda url: SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda jeton: SimpleNamespace(key=_CLE.public_key())
    )
    demo_api._ENGINE_DEMO = web
    app = demo_api.create_app()
    comptes, justificatifs = InMemoryCompteRepository(), InMemoryJustificatifRepository()
    app.dependency_overrides[demo_api.get_comptes] = lambda: comptes
    app.dependency_overrides[demo_api.get_justificatifs] = lambda: justificatifs
    return TestClient(app)


def _en_tete(**lien: str) -> dict[str, str]:
    """`tenant_id=…` : gestionnaire ; `dossier_id=…` : chauffeur."""
    charge = {
        "sub": "u-perf",
        "email": "perf@example.com",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "aal": "aal2",  # double authentification (AXE-812)
        "app_metadata": lien,
    }
    return {"Authorization": f"Bearer {jwt.encode(charge, _CLE, algorithm='ES256')}"}


def _appel(client: TestClient, chemin: str, en_tete: dict[str, str]) -> Callable[[], object]:
    return lambda: client.get(chemin, headers=en_tete)


def _chronometrer(appel: Callable[[], object], repetitions: int) -> tuple[float, float]:
    durees = []
    for _ in range(repetitions):
        debut = time.perf_counter()
        appel()
        durees.append(time.perf_counter() - debut)
    durees.sort()
    p95 = durees[min(len(durees) - 1, round(0.95 * (len(durees) - 1)))]
    return statistics.median(durees), p95


DOSSIER = "PERF_000"
# (route, profil, chemin) : les lectures appelées par le front (AXE-843).
ROUTES: tuple[tuple[str, str, str], ...] = (
    ("/dossiers/{id}", "chauffeur", f"/dossiers/{DOSSIER}"),
    ("/dossiers/{id}/transactions", "chauffeur", f"/dossiers/{DOSSIER}/transactions"),
    ("/dossiers/{id}/notifications", "chauffeur", f"/dossiers/{DOSSIER}/notifications"),
    ("/dossiers/{id}/cloture-exercice", "chauffeur", f"/dossiers/{DOSSIER}/cloture-exercice"),
    ("/dossiers/{id}/provisions-cloture", "chauffeur", f"/dossiers/{DOSSIER}/provisions-cloture"),
    ("/dossiers/{id}/tva", "chauffeur", f"/dossiers/{DOSSIER}/tva"),
    ("/dossiers/{id}/configuration", "chauffeur", f"/dossiers/{DOSSIER}/configuration"),
    ("/dossiers/{id}/comptes-bancaires", "chauffeur", f"/dossiers/{DOSSIER}/comptes-bancaires"),
    ("/dossiers/{id}/dividendes", "chauffeur", f"/dossiers/{DOSSIER}/dividendes"),
    ("/dossiers/{id}/bulletins", "chauffeur", f"/dossiers/{DOSSIER}/bulletins"),
    ("/dossiers/{id}/acces", "chauffeur", f"/dossiers/{DOSSIER}/acces"),
    ("/dossiers/{id}/affectation", "chauffeur", f"/dossiers/{DOSSIER}/affectation"),
    ("/dossiers/{id}/identite", "chauffeur", f"/dossiers/{DOSSIER}/identite"),
    ("/portefeuille/moi", "gestionnaire", "/portefeuille/moi"),
    ("/dossiers", "gestionnaire", "/dossiers"),
    ("/portefeuille", "gestionnaire", "/portefeuille"),
    ("/portefeuille/connexions-bancaires", "gestionnaire", "/portefeuille/connexions-bancaires"),
    ("/portefeuille/nouveaux-chauffeurs", "gestionnaire", "/portefeuille/nouveaux-chauffeurs"),
    ("/portefeuille/categorisation", "gestionnaire", "/portefeuille/categorisation"),
    ("/portefeuille/synchronisation", "gestionnaire", "/portefeuille/synchronisation"),
    ("/portefeuille/membres", "gestionnaire", "/portefeuille/membres"),
    ("/portefeuille/retires", "gestionnaire", "/portefeuille/retires"),
    ("/rappels", "gestionnaire", "/rappels"),
    ("/regles-rappel", "gestionnaire", "/regles-rappel"),
    ("/tags", "gestionnaire", "/tags"),
    ("/dossiers/{id}/envois", "gestionnaire", f"/dossiers/{DOSSIER}/envois"),
    ("/portefeuille/integrations/envoi", "gestionnaire", "/portefeuille/integrations/envoi"),
    ("/portefeuille/import-dossiers", "gestionnaire", "/portefeuille/import-dossiers"),
    (
        "/portefeuille/import-dossiers/modele.csv",
        "gestionnaire",
        "/portefeuille/import-dossiers/modele.csv",
    ),
    ("/expert/file", "expert", "/expert/file"),
    ("/expert/classees", "expert", "/expert/classees"),
    ("/dossiers/{id}/anomalies", "expert", f"/dossiers/{DOSSIER}/anomalies"),
    ("/dossiers/{id}/quarantaine", "expert", f"/dossiers/{DOSSIER}/quarantaine"),
    ("/expert/engagement", "expert", "/expert/engagement"),
)
# Cibles du ticket AXE-843 : p95 < 1 s, file expert < 2 s.
CIBLES_MS = {"/expert/file": 2000}
CIBLE_PAR_DEFAUT_MS = 1000
EMAIL = "perf@example.com"


def _habiliter_expert(client: TestClient, web: Engine, nb_dossiers: int) -> None:
    """AXE-800 : l'expert du portefeuille, habilité sur tous ses dossiers,
    engagement accepté. En mémoire : seule la vérification d'accès change,
    les lectures passent toujours par Postgres."""
    le = datetime.now(UTC)
    experts = ExpertMemoire(PostgresLedgerService(web))
    experts.habiliter(
        Habilitation(
            tenant_id=TenantId(TENANT),
            email=EMAIL,
            nom="Expert Perf",
            cabinet="Cabinet Perf",
            numero_ordre="00-000000",
            lettre_mission="LM-PERF",
            date_lettre=date(2026, 1, 1),
            dossiers=tuple(DossierId(f"PERF_{n:03d}") for n in range(nb_dossiers)),
            accordee_par=UserId("u-perf"),
            accordee_le=le,
        )
    )
    experts.accepter(
        Engagement(
            tenant_id=TenantId(TENANT),
            email=EMAIL,
            version=VERSION_ENGAGEMENT,
            texte=TEXTE_ENGAGEMENT,
            adresse="banc",
            acteur=UserId("u-perf"),
            accepte_le=le,
        )
    )
    client.app.dependency_overrides[demo_api.get_experts] = lambda: experts  # type: ignore[attr-defined]


def _profil(client: TestClient, profil: str) -> dict[str, str]:
    """Le rôle du membre est en Postgres (`droits_membre`) : fixé ici."""
    role = ROLE_EXPERT if profil == "expert" else "admin"
    client.app.dependency_overrides[demo_api.get_role_membre] = lambda: role  # type: ignore[attr-defined]
    if profil == "chauffeur":
        return _en_tete(dossier_id=DOSSIER)
    return _en_tete(tenant_id=TENANT)


def _mesurer(client: TestClient, nom: str, profil: str, chemin: str, repetitions: int) -> None:
    en_tete = _profil(client, profil)
    debut = time.perf_counter()
    reponse = client.get(chemin, headers=en_tete)
    premier = time.perf_counter() - debut
    if reponse.status_code != 200:
        print(f"| `{nom}` | {profil} | HTTP {reponse.status_code} | | | |")
        return
    p50, p95 = _chronometrer(_appel(client, chemin, en_tete), repetitions)
    cible = CIBLES_MS.get(nom, CIBLE_PAR_DEFAUT_MS)
    verdict = "ok" if p95 * 1000 < cible else f"**> {cible} ms**"
    print(
        f"| `{nom}` | {profil} | {premier * 1000:.0f} ms | {p50 * 1000:.0f} ms "
        f"| {p95 * 1000:.0f} ms | {verdict} |"
    )


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--dossiers", type=int, default=200)
    parseur.add_argument("--ecritures", type=int, default=300)
    parseur.add_argument("--repetitions", type=int, default=5)
    parseur.add_argument("--sans-semis", action="store_true", help="réutilise le portefeuille")
    parseur.add_argument(
        "--prechauffer", action="store_true", help="comme les tâches planifiées après la synchro"
    )
    parseur.add_argument("--route", action="append", help="ne mesure que ces routes (morceau)")
    arguments = parseur.parse_args()

    proprietaire = _moteur_local("DATABASE_URL")
    command.upgrade(_alembic(), "head")
    web_url = make_url(str(proprietaire.url)).set(
        username="axelcompta_web", password="web_password_dev"
    )
    web = create_engine(web_url)
    if not arguments.sans_semis:
        _vider(proprietaire)
        _semer(proprietaire, arguments.dossiers, arguments.ecritures)
    if arguments.prechauffer:
        portefeuille = PostgresDossierRepository(proprietaire).lister_par_tenant(TenantId(TENANT))
        debut = time.perf_counter()
        recalcules = demo_api.prechauffer_caches(proprietaire, portefeuille)
        print(f"Préchauffage : {recalcules} dossiers en {time.perf_counter() - debut:.1f} s\n")
    client = _client(web)
    _habiliter_expert(client, web, arguments.dossiers)
    print(f"{arguments.dossiers} dossiers × {arguments.ecritures} écritures")
    print(f"{arguments.repetitions} appels par route\n")
    print("| Route | Profil | 1er appel | p50 | p95 | Cible |\n|---|---|---|---|---|---|")
    for nom, profil, chemin in ROUTES:
        if arguments.route and not any(morceau in nom for morceau in arguments.route):
            continue
        _mesurer(client, nom, profil, chemin, arguments.repetitions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
