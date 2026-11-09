"""Le modèle de catégorisation est requis en production (AXE-825).

Le 05/11, `tfidf_logreg_v2.joblib` manquait sur le poste. La synchro a
continué avec les règles seules, sans rien dire, et a envoyé 93 % des
opérations d'un dossier au compte d'attente. Désormais :

- la synchro ne démarre pas sans modèle ; elle le dit (sortie d'erreur et
  Sentry si branché) ;
- l'API garde les règles seules pour servir les écrans, mais expose l'état
  « catégorisation dégradée » au gestionnaire ;
- le repli silencieux n'est permis que si `AXELCOMPTA_SANS_MODELE=1`
  (développement, tests).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .ml_fallback import (
    CHEMIN_MODELE_PAR_DEFAUT,
    ModeleMlCorrompu,
    ModeleMlIndisponible,
    ModeleSklearn,
    charger_modele,
    repli_sans_modele_permis,
)

MESSAGE_ABSENT = "Modèle de catégorisation absent : synchro arrêtée."
MESSAGE_CORROMPU = "Modèle de catégorisation altéré (empreinte) : synchro arrêtée."


@dataclass(frozen=True, slots=True)
class EtatCategorisation:
    """Ce que voit le gestionnaire sur l'écran Intégrations."""

    modele_charge: bool
    fichier: str  # nom du fichier attendu, sans le chemin du poste
    raison: str | None = None


@dataclass(frozen=True, slots=True)
class ModeleCharge:
    modele: ModeleSklearn | None
    etat: EtatCategorisation


def charger(chemin: Path | None = None) -> ModeleCharge:
    """Le modèle et son état. Ne lève jamais : à l'appelant de décider."""
    fichier = (chemin or CHEMIN_MODELE_PAR_DEFAUT).name
    try:
        modele = charger_modele(chemin)
    except ModeleMlCorrompu:
        return ModeleCharge(None, EtatCategorisation(False, fichier, MESSAGE_CORROMPU))
    except ModeleMlIndisponible:
        return ModeleCharge(None, EtatCategorisation(False, fichier, MESSAGE_ABSENT))
    return ModeleCharge(modele, EtatCategorisation(True, fichier))


class SynchroSansModele(RuntimeError):
    """La synchro refuse de tourner sans modèle (AXE-825)."""


def modele_pour_synchro(
    chemin: Path | None = None, environ: Mapping[str, str] | None = None
) -> ModeleSklearn | None:
    """Le modèle, ou `None` si le repli est explicitement permis. Sinon,
    signale et lève `SynchroSansModele`."""
    charge = charger(chemin)
    if charge.modele is not None:
        return charge.modele
    raison = charge.etat.raison or MESSAGE_ABSENT
    if repli_sans_modele_permis(environ):
        print(f"{raison} Repli sur les règles seules (AXELCOMPTA_SANS_MODELE=1).", file=sys.stderr)
        return None
    signaler(raison)
    raise SynchroSansModele(raison)


def signaler(message: str) -> None:
    """Sortie d'erreur, et Sentry s'il a été initialisé dans ce processus."""
    print(message, file=sys.stderr)
    try:
        import sentry_sdk
    except ImportError:
        return
    if sentry_sdk.is_initialized():
        sentry_sdk.capture_message(message, level="error")
