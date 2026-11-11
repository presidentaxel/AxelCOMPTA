"""Relecture des registres officiels, INSEE et RNE (AXE-849).

Composition root, comme `nouveaux_contacts.py` : les appels HTTP sont ici,
la lecture des réponses et la comparaison dans `tenants/registres.py`.

- INSEE, API Sirene 3.11 (portail api.insee.fr) : clé `INSEE_API_KEY`,
  envoyée dans l'en-tête `X-INSEE-Api-Key-Integration`. Lecture vérifiée
  le 2026-11-11 (dénomination, forme, siège, état, activité). Le capital
  et les dirigeants ne sont pas dans Sirene : ils viennent du RNE.
- RNE (INPI) : compte `INPI_RNE_USERNAME` / `INPI_RNE_PASSWORD`, échangé
  contre un jeton (`POST /api/sso/login`). Vide : l'INSEE est lu seul.

Les deux sont des secrets : jamais dans le dépôt. Sans eux, rien n'est lu
et rien ne change. Sirene 3.11 a été lue sur un SIREN réel ; le format RNE
reste celui de la documentation tant qu'un compte INPI n'a pas répondu
(`python -m axelcompta.registres_officiels --siren …` affiche la fiche lue,
le `.env` racine est chargé).

Chaque dossier qui a un SIREN est relu au plus une fois par semaine, par
les tâches planifiées. La lecture est gardée avec sa date ; les écarts non
tranchés sont posés sur le dossier.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from axelcompta.core.db import engine_depuis_env
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.registres import (
    FicheOfficielle,
    combiner,
    ecarts,
    fiche_insee,
    fiche_rne,
    restants,
)
from axelcompta.tenants.registres_depot import RegistresPostgres, RegistresRepository
from axelcompta.tenants.repository import DossierRepository

URL_INSEE = "https://api.insee.fr/api-sirene/3.11"
URL_RNE = "https://registre-national-entreprises.inpi.fr/api"
_ENV = Path(__file__).resolve().parents[2] / ".env"
INTERVALLE = timedelta(days=7)
DELAI = 20.0

LireFiche = Callable[[str], FicheOfficielle | None]


def _json_ou_rien(reponse: httpx.Response) -> Mapping[str, Any] | None:
    if reponse.status_code == 404:
        return None
    reponse.raise_for_status()
    corps = reponse.json()
    return corps if isinstance(corps, dict) else None


@dataclass(frozen=True, slots=True)
class Insee:
    cle: str

    def lire(self, siren: str, aujourd_hui: date) -> FicheOfficielle | None:
        entetes = {"X-INSEE-Api-Key-Integration": self.cle, "accept": "application/json"}
        unite = _json_ou_rien(
            httpx.get(f"{URL_INSEE}/siren/{siren}", headers=entetes, timeout=DELAI)
        )
        if unite is None:
            return None
        periodes = unite.get("uniteLegale", {}).get("periodesUniteLegale") or [{}]
        nic = str(periodes[0].get("nicSiegeUniteLegale") or "")
        etablissement: Mapping[str, Any] = {}
        if len(nic) == 5:
            siege = _json_ou_rien(
                httpx.get(f"{URL_INSEE}/siret/{siren}{nic}", headers=entetes, timeout=DELAI)
            )
            etablissement = siege or {}
        return fiche_insee(unite, etablissement, siren, aujourd_hui)


@dataclass(slots=True)
class Rne:
    utilisateur: str
    mot_de_passe: str
    _jeton: str | None = None

    def _authentifier(self) -> str:
        if self._jeton is None:
            reponse = httpx.post(
                f"{URL_RNE}/sso/login",
                json={"username": self.utilisateur, "password": self.mot_de_passe},
                timeout=DELAI,
            )
            reponse.raise_for_status()
            self._jeton = str(reponse.json()["token"])
        return self._jeton

    def lire(self, siren: str, aujourd_hui: date) -> FicheOfficielle | None:
        entetes = {"Authorization": f"Bearer {self._authentifier()}"}
        reponse = httpx.get(f"{URL_RNE}/companies/{siren}", headers=entetes, timeout=DELAI)
        if reponse.status_code == 401:  # jeton expiré : un seul nouvel essai
            self._jeton = None
            entetes = {"Authorization": f"Bearer {self._authentifier()}"}
            reponse = httpx.get(f"{URL_RNE}/companies/{siren}", headers=entetes, timeout=DELAI)
        corps = _json_ou_rien(reponse)
        return fiche_rne(corps, siren, aujourd_hui) if corps is not None else None


def charger_env() -> None:
    """Le `.env` racine, sans écraser une variable déjà posée."""
    load_dotenv(_ENV)


def lecteur_depuis_env(environ: Mapping[str, str] | None = None) -> LireFiche | None:
    """`None` si aucune des deux API n'est configurée. Une seule suffit :
    l'autre manque simplement à la fiche."""
    valeurs = os.environ if environ is None else environ
    cle = valeurs.get("INSEE_API_KEY", "").strip()
    utilisateur = valeurs.get("INPI_RNE_USERNAME", "").strip()
    mot_de_passe = valeurs.get("INPI_RNE_PASSWORD", "").strip()
    insee = Insee(cle) if cle else None
    rne = Rne(utilisateur, mot_de_passe) if utilisateur and mot_de_passe else None
    if insee is None and rne is None:
        return None

    def lire(siren: str) -> FicheOfficielle | None:
        aujourd_hui = date.today()
        officielle = insee.lire(siren, aujourd_hui) if insee else None
        try:
            rne_fiche = rne.lire(siren, aujourd_hui) if rne else None
        except httpx.HTTPStatusError:
            # Compte sans droit API : Sirene reste lisible.
            rne_fiche = None
        return combiner(officielle, rne_fiche)

    return lire


def a_relire(registres: RegistresRepository, dossier: Dossier, maintenant: datetime) -> bool:
    if dossier.siren is None or dossier.retire_le is not None:
        return False
    derniere = registres.derniere_lecture(dossier.id)
    return derniere is None or maintenant - derniere[1] >= INTERVALLE


def relire_dossier(
    registres: RegistresRepository, dossier: Dossier, lire: LireFiche
) -> FicheOfficielle | None:
    assert dossier.siren is not None
    fiche = lire(dossier.siren)
    if fiche is None:
        return None
    a_trancher = restants(ecarts(dossier, fiche), registres.resolus(dossier.id))
    registres.enregistrer_lecture(dossier, fiche, a_trancher)
    return fiche


def relire_portefeuilles(
    depot: DossierRepository,
    registres: RegistresRepository,
    lire: LireFiche,
    maintenant: datetime,
) -> tuple[int, list[str]]:
    """Relit chaque dossier dû. Une erreur sur un dossier n'arrête pas les
    autres. Rend le nombre de dossiers relus et les erreurs."""
    relus, erreurs = 0, []
    for tenant in depot.lister_tenants():
        for dossier in depot.lister_par_tenant(tenant.id):
            if not a_relire(registres, dossier, maintenant):
                continue
            try:
                if relire_dossier(registres, dossier, lire) is not None:
                    relus += 1
            except Exception as exc:  # noqa: BLE001 — gardé, les autres continuent
                erreurs.append(f"{dossier.id} : {type(exc).__name__}: {exc}")
    return relus, erreurs


def relire_si_configure() -> str | None:
    """Pour les tâches planifiées : rien si les clés manquent."""
    charger_env()
    lire = lecteur_depuis_env()
    if lire is None:
        return None
    engine = engine_depuis_env()
    relus, erreurs = relire_portefeuilles(
        PostgresDossierRepository(engine), RegistresPostgres(engine), lire, datetime.now(UTC)
    )
    return f"registres : {relus} dossier(s) relu(s)" + (
        f", {len(erreurs)} erreur(s)" if erreurs else ""
    )


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--siren", help="affiche la fiche lue pour ce SIREN, sans rien écrire")
    args = parseur.parse_args()
    charger_env()
    lire = lecteur_depuis_env()
    if lire is None:
        print("Ni INSEE_API_KEY ni INPI_RNE_USERNAME/PASSWORD : rien à lire.", file=sys.stderr)
        return 1
    if args.siren:
        print(lire(args.siren))
        return 0
    print(relire_si_configure())
    return 0


if __name__ == "__main__":
    sys.exit(main())
