"""La synchro complète les fiches d'import du portefeuille (AXE-952).

Composition : lit en base ce qu'on sait de chaque dossier (comptes Rollee
reliés et leurs plateformes, comptes bancaires, première opération reçue),
laisse `tenants/fiches_import_dossiers.py` décider quoi écrire, et lit une
fois l'INSEE et le RNE pour une fiche qui a un SIREN mais pas encore de
lecture. Rien n'est écrit par-dessus une saisie.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from axelcompta.core.ids import TenantId
from axelcompta.tenants.contacts_proposes_postgres import PostgresContactsProposes
from axelcompta.tenants.fiches_import import FicheImport, fiches_des_contacts, preremplir
from axelcompta.tenants.fiches_import_dossiers import (
    PAR_SYNCHRO,
    CompteRolleeDuDossier,
    DonneesDossier,
    completer_portefeuille,
)
from axelcompta.tenants.fiches_import_etat import relier_toutes
from axelcompta.tenants.fiches_import_postgres import PostgresFichesImport
from axelcompta.tenants.fiches_import_reprise import preremplir_reprise
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.registres import FicheOfficielle
from axelcompta.validation_fiches_service import valider_portefeuille

LireRegistres = Callable[[str], FicheOfficielle | None]
# Nom d'un compte Rollee (« uber.com-fleet-rev ») → plateforme de la fiche.
_PLATEFORMES = (
    ("uber", "uber"),
    ("bolt", "bolt"),
    ("heetch", "heetch"),
    ("allocab", "allocab"),
    ("free-now", "freenow"),
    ("freenow", "freenow"),
)


def plateforme_du_compte(nom: str) -> str | None:
    bas = nom.lower()
    return next((cle for motif, cle in _PLATEFORMES if motif in bas), None)


def _rollee(engine: Engine, tenant_id: TenantId) -> dict[str, list[CompteRolleeDuDossier]]:
    with engine.connect() as connexion:
        lignes = connexion.execute(
            text(
                "SELECT c.dossier_id, c.rollee_user_id, c.nom AS compte, k.nom AS nom "
                "FROM comptes_rollee c JOIN dossiers d ON d.id = c.dossier_id "
                "LEFT JOIN cartes_rollee k ON k.rollee_user_id = c.rollee_user_id "
                "WHERE d.tenant_id = :t AND c.retenu AND NOT c.titulaire_autre"
            ),
            {"t": tenant_id},
        ).all()
    par_user: dict[tuple[str, str], tuple[str, set[str]]] = {}
    for ligne in lignes:
        nom, plateformes = par_user.setdefault(
            (ligne.dossier_id, ligne.rollee_user_id), (ligne.nom or "", set())
        )
        if (p := plateforme_du_compte(ligne.compte or "")) is not None:
            plateformes.add(p)
    resultat: dict[str, list[CompteRolleeDuDossier]] = {}
    for (dossier_id, user), (nom, plateformes) in par_user.items():
        resultat.setdefault(dossier_id, []).append(
            CompteRolleeDuDossier(user, nom, tuple(sorted(plateformes)))
        )
    return resultat


def _banque(engine: Engine, tenant_id: TenantId) -> tuple[dict[str, list[str]], dict[str, date]]:
    with engine.connect() as connexion:
        comptes = connexion.execute(
            text(
                "SELECT b.dossier_id, b.nom, b.retenu FROM comptes_bancaires b "
                "JOIN dossiers d ON d.id = b.dossier_id WHERE d.tenant_id = :t ORDER BY b.nom"
            ),
            {"t": tenant_id},
        ).all()
        debuts = connexion.execute(
            text(
                "SELECT e.dossier_id, min(e.date) AS debut FROM ecritures e "
                "JOIN dossiers d ON d.id = e.dossier_id "
                "WHERE d.tenant_id = :t AND e.journal = 'BQ' GROUP BY e.dossier_id"
            ),
            {"t": tenant_id},
        ).all()
    noms: dict[str, list[str]] = {}
    for ligne in comptes:
        etat = {True: "retenu", False: "écarté"}.get(ligne.retenu, "à choisir")
        noms.setdefault(ligne.dossier_id, []).append(f"{ligne.nom} ({etat})")
    return noms, {ligne.dossier_id: ligne.debut for ligne in debuts}


def donnees_du_portefeuille(
    engine: Engine, tenant_id: TenantId, dossiers: Sequence[Dossier]
) -> list[DonneesDossier]:
    rollee = _rollee(engine, tenant_id)
    comptes, debuts = _banque(engine, tenant_id)
    return [
        DonneesDossier(
            dossier=d,
            comptes_rollee=tuple(rollee.get(d.id, ())),
            comptes_bancaires=tuple(comptes.get(d.id, ())),
            debut_historique=debuts.get(d.id),
        )
        for d in dossiers
    ]


def _avec_registres(fiche: FicheImport, lire: LireRegistres | None, le: datetime) -> FicheImport:
    siren = fiche.champs.get("siren")
    if lire is None or not siren or fiche.registre is not None:
        return fiche
    officielle = lire(siren)
    return preremplir(fiche, officielle, PAR_SYNCHRO, le) if officielle else fiche


def _fiches(nombre: int, participe: str) -> str:
    pluriel = "s" if nombre > 1 else ""
    return f"{nombre} fiche{pluriel} d'import {participe}{pluriel}"


def resume(creees: int, completees: int) -> str:
    """« 15 fiches d'import créées, 2 fiches d'import complétées »."""
    morceaux = []
    if creees:
        morceaux.append(_fiches(creees, "créée"))
    if completees:
        morceaux.append(_fiches(completees, "complétée"))
    return ", ".join(morceaux)


def completer_fiches(
    engine: Engine,
    tenant_id: TenantId,
    lire: LireRegistres | None,
    maintenant: datetime | None = None,
) -> str:
    """Une fiche pour chaque dossier, complétée de ce qu'on sait ; le résumé
    s'ajoute à celui de la synchro (« » s'il n'y a rien à faire)."""
    le = maintenant or datetime.now(UTC)
    dossiers = PostgresDossierRepository(engine).lister_par_tenant(tenant_id)
    donnees = donnees_du_portefeuille(engine, tenant_id, dossiers)
    depot = PostgresFichesImport(engine)
    a_ecrire, creees, completees = completer_portefeuille(donnees, depot.toutes(tenant_id), le)
    for fiche in a_ecrire:
        depot.enregistrer(_avec_registres(fiche, lire, le))
    contacts = PostgresContactsProposes(engine)
    a_ouvrir = fiches_des_contacts(
        contacts.propositions(tenant_id),
        contacts.decisions(tenant_id),
        depot.toutes(tenant_id),
        tenant_id,
        le,
    )
    for fiche in a_ouvrir:
        depot.enregistrer(_avec_registres(fiche, lire, le))
    # AXE-976 : la reprise comptable de chaque fiche suit son dernier FEC.
    for fiche, documents in depot.lister(tenant_id):
        relue = preremplir_reprise(fiche, documents, le.date())
        if relue is not fiche:
            depot.enregistrer(relue)
    crees = relier_au_portefeuille_complet(engine, tenant_id)
    texte = resume(creees + len(a_ouvrir), completees)
    if crees:
        ajout = f"{crees} dossier(s) créé(s) depuis Imports"
        texte = f"{texte}, {ajout}" if texte else ajout
    # AXE-989 : un chauffeur importé a des données à jour, revues chaque heure.
    revues = valider_portefeuille(engine, tenant_id, le)
    if revues:
        texte = f"{texte}, {revues}" if texte else revues
    return texte


def relier_au_portefeuille_complet(engine: Engine, tenant_id: TenantId) -> int:
    """AXE-974 : chaque fiche active complète a son dossier, créé ici avec
    le rôle propriétaire (le rôle web de l'API ne crée pas de dossier). Une
    fiche Ignoré ou annulée n'en crée pas. Le nombre de dossiers créés."""
    depot = PostgresFichesImport(engine)
    dossiers = PostgresDossierRepository(engine)
    changees, a_creer = relier_toutes(
        depot.toutes(tenant_id), dossiers.lister_par_tenant(tenant_id)
    )
    crees = dossiers.enregistrer_lot(a_creer) if a_creer else 0
    for fiche in changees:
        depot.enregistrer(fiche)
    return crees
