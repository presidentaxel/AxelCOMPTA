"""Tâches planifiées : pour chaque portefeuille, synchro Digifactory, bascules
de régime dues (fin d'option IR, doc 06 §7), puis notifications internes
(doc 12, J3 et J5).

Un seul point d'entrée pour le planificateur, quel qu'il soit : le crontab
du poste de Louis pour la démo, celui du serveur (ou un timer systemd) en
production, via `scripts/taches_planifiees.sh`. En attendant la file de
jobs (ADR-002), c'est ce module qui porte l'ordre des étapes.

Les notifications passent même si la synchro échoue : un dossier peut avoir
des opérations en attente depuis un passage précédent. Le code de sortie
vaut 1 dès qu'une étape a échoué quelque part, pour que le planificateur le
signale.

Usage, depuis backend/ (DATABASE_URL, DIGIFACTORY_BASE_URL et
DIGIFACTORY_TOKEN définis) :

    python -m axelcompta.taches
    python -m axelcompta.taches --sans-synchro
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from axelcompta.api.observabilite import installer_sentry
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.metriques import METRIQUES
from axelcompta.demo_api import prechauffer_caches
from axelcompta.ledger.balance import SoldeJournal, ecarts
from axelcompta.ledger.repository import soldes_par_journal
from axelcompta.notifier import notifier_depuis_base
from axelcompta.synchro_digifactory import ResultatDossier, synchroniser_portefeuille
from axelcompta.tenants.avenants import programmer_bascules
from axelcompta.tenants.avenants_postgres import PostgresAvenantRegimeRepository
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository
from axelcompta.tenants.tags import SANS_TAGS, EtatTags, etat_du_portefeuille, exclus, retenus
from axelcompta.tenants.tags_postgres import PostgresTagsRepository
from axelcompta.workflow.notifications import ResultatNotification

# Reçoit aussi les dossiers à synchroniser sans classement automatique.
Synchroniser = Callable[[tuple[Dossier, ...], frozenset[DossierId]], list[ResultatDossier]]
Notifier = Callable[[tuple[Dossier, ...]], list[ResultatNotification]]
# Renvoie le nombre d'avenants de régime enregistrés.
ProgrammerBascules = Callable[[tuple[Dossier, ...]], int]
# Tags et exclusions d'un portefeuille (AXE-829).
Perimetre = Callable[[TenantId], EtatTags]
# Renvoie le nombre de dossiers recalculés (agrégats, file expert).
Prechauffer = Callable[[tuple[Dossier, ...]], int]


@dataclass
class BilanTaches:
    lignes: list[str] = field(default_factory=list)
    echec: bool = False


def lancer_taches(
    depot: DossierRepository,
    synchroniser: Synchroniser | None,
    notifier: Notifier,
    programmer_bascules: ProgrammerBascules | None = None,
    perimetre: Perimetre | None = None,
    prechauffer: Prechauffer | None = None,
) -> BilanTaches:
    """`synchroniser` à None saute la synchro (`--sans-synchro`). Un
    portefeuille sans aucun contact Digifactory n'appelle pas Digifactory.
    Un dossier qu'un tag exclut de la synchro, du classement ou des rappels
    saute l'étape correspondante (`perimetre`, AXE-829)."""
    bilan = BilanTaches()
    for tenant in depot.lister_tenants():
        dossiers = depot.lister_par_tenant(tenant.id)
        if not dossiers:
            continue
        etat = perimetre(tenant.id) if perimetre is not None else SANS_TAGS
        if synchroniser is not None:
            _synchroniser(bilan, tenant.id, dossiers, etat, synchroniser)
        if programmer_bascules is not None:
            _programmer_bascules(bilan, tenant.id, dossiers, programmer_bascules)
        if prechauffer is not None:
            _prechauffer(bilan, tenant.id, dossiers, prechauffer)
        _notifier(bilan, tenant.id, retenus(dossiers, etat, "rappels"), notifier)
    return bilan


def _synchroniser(
    bilan: BilanTaches,
    tenant_id: TenantId,
    dossiers: tuple[Dossier, ...],
    etat: EtatTags,
    synchroniser: Synchroniser,
) -> None:
    a_synchroniser = retenus(dossiers, etat, "synchro")
    if not any(d.contact_nr for d in a_synchroniser):
        return
    try:
        resultats = synchroniser(a_synchroniser, exclus(dossiers, etat, "categorisation"))
    except Exception as exc:  # noqa: BLE001 — la notification passe quand même
        bilan.echec = True
        bilan.lignes.append(f"{tenant_id} synchro : échec ({type(exc).__name__}: {exc})")
        return
    erreurs = [r for r in resultats if r.erreur]
    bilan.echec |= bool(erreurs)
    bilan.lignes.append(
        f"{tenant_id} synchro : {len(resultats) - len(erreurs)} ok, {len(erreurs)} en échec"
    )


def _programmer_bascules(
    bilan: BilanTaches,
    tenant_id: TenantId,
    dossiers: tuple[Dossier, ...],
    programmer_bascules: ProgrammerBascules,
) -> None:
    try:
        nb = programmer_bascules(dossiers)
    except Exception as exc:  # noqa: BLE001 — une étape n'arrête pas les autres
        bilan.echec = True
        bilan.lignes.append(f"{tenant_id} bascules : échec ({type(exc).__name__})")
        return
    if nb:
        bilan.lignes.append(f"{tenant_id} bascules de régime : {nb} enregistrées")


def _notifier(
    bilan: BilanTaches, tenant_id: TenantId, dossiers: tuple[Dossier, ...], notifier: Notifier
) -> None:
    notifs = notifier(dossiers)
    creees = sum(1 for r in notifs if r.statut == "creee")
    echecs = sum(1 for r in notifs if r.statut == "echec")
    bilan.echec |= echecs > 0
    bilan.lignes.append(f"{tenant_id} notifications : {creees} créées, {echecs} en échec")


def _prechauffer(
    bilan: BilanTaches, tenant_id: TenantId, dossiers: tuple[Dossier, ...], prechauffer: Prechauffer
) -> None:
    """Après la synchro : le premier affichage du matin lit des valeurs
    gardées (AXE-824). Un échec ne bloque rien : l'affichage recalculera."""
    try:
        nombre = prechauffer(dossiers)
    except Exception as exc:  # noqa: BLE001 — une étape n'arrête pas les autres
        bilan.lignes.append(f"{tenant_id} caches : échec ({type(exc).__name__})")
        return
    if nombre:
        bilan.lignes.append(f"{tenant_id} caches : {nombre} dossiers recalculés")


# Une fois par jour : le planificateur passe toutes les heures (I7, AXE-807).
HEURE_CONTROLE_BALANCE = 3
VARIABLE_FICHIER_METRIQUES = "AXELCOMPTA_METRIQUES_FICHIER"


def controler_balance(
    bilan: BilanTaches,
    lire_soldes: Callable[[], list[SoldeJournal]],
    alerter: Callable[[str], None],
) -> None:
    """Invariant I7 : chaque écart est alerté (Sentry), écrit dans le journal
    des tâches et compté (`balance_desequilibree_total`). Rien n'est corrigé
    automatiquement. Le passage est en échec tant qu'un écart existe."""
    trouves = ecarts(lire_soldes())
    METRIQUES.jauger("balance_desequilibree_total", len(trouves))
    if not trouves:
        bilan.lignes.append("balance : équilibrée")
        return
    bilan.echec = True
    for ecart in trouves:
        bilan.lignes.append(f"ALERTE {ecart.message}")
        alerter(ecart.message)


def _alerter_sentry(message: str) -> None:
    try:
        import sentry_sdk
    except ImportError:
        return
    sentry_sdk.capture_message(message, level="error")


def _ecrire_metriques() -> None:
    """Le planificateur n'est pas l'API : ses métriques passent par un
    fichier lu par le collecteur (format texte Prometheus), si configuré."""
    chemin = os.environ.get(VARIABLE_FICHIER_METRIQUES)
    if chemin:
        Path(chemin).write_text(METRIQUES.texte(), encoding="utf-8")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--sans-synchro", action="store_true")
    args = parseur.parse_args()

    debut = datetime.now(UTC)
    engine = engine_depuis_env()
    bilan = lancer_taches(
        PostgresDossierRepository(engine),
        None if args.sans_synchro else (lambda d, s: synchroniser_portefeuille(engine, d, s)),
        lambda d: notifier_depuis_base(engine, d),
        lambda d: len(
            programmer_bascules(
                d,
                PostgresAvenantRegimeRepository(engine),
                datetime.now(UTC).replace(tzinfo=None),
            )
        ),
        lambda tenant_id: etat_du_portefeuille(PostgresTagsRepository(engine), tenant_id),
        lambda d: prechauffer_caches(engine, d),
    )
    if debut.hour == HEURE_CONTROLE_BALANCE:
        installer_sentry()
        controler_balance(bilan, lambda: soldes_par_journal(engine), _alerter_sentry)
        _ecrire_metriques()
    print(f"[{debut.isoformat(timespec='seconds')}] tâches planifiées")
    for ligne in bilan.lignes:
        print(f"  {ligne}")
    return 1 if bilan.echec else 0


if __name__ == "__main__":
    sys.exit(main())
