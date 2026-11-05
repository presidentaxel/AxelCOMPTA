"""Amorçage du dossier de review UX (Sophie) et, pour les tests, des trois
dossiers chauffeur type (doc 17 §4).

**Depuis le 2026-11-05, la base Supabase est la base réelle du portefeuille
Serenity.** La commande ne pose plus que `DOSSIER_REVUE_UX`, le seul dossier
fictif gardé pour les reviews UX ; Karim et Yanis n'existent plus que dans
les tests (`amorcer_demo` sans filtre).

Composition root comme `demo_api.py` (doc 18). Avant le 2026-09-21, l'API
recalculait tout ça à chaque requête depuis `chauffeurs_demo.py` ; depuis,
elle lit Postgres, et ce module y écrit **une fois** ce que le pipeline
calculait à la volée. Ce sera aussi le point d'entrée des vrais dossiers du
pilote : mêmes tables, autre source de données (Digifactory, doc 16).

Usage, depuis backend/ (DATABASE_URL défini, migrations appliquées) :

    alembic upgrade head
    python -m axelcompta.demo_seed
"""

from __future__ import annotations

import dataclasses
import io
import sys
from datetime import UTC, datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.models import ParametresCloture
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, EcritureId, TenantId, UserId
from axelcompta.demo_chauffeurs_type import construire_ledger, fin_exercice
from axelcompta.demo_identites import IDENTITES_DEMO
from axelcompta.demo_jalons import JALONS_EXERCICE
from axelcompta.filings.inpi_depot import PdfDepotInpiRenderer
from axelcompta.ingestion.providers.chauffeurs_demo import PROFILS_DEMO, ProfilChauffeurType
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository
from axelcompta.workflow.propositions import PropositionRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.signature import DocumentSigne, SignatureRepository
from axelcompta.workflow.signature_postgres import PostgresSignatureRepository

# Identifiant historique du portefeuille, gardé tel quel en base : c'est
# aujourd'hui celui de Serenity (nom affiché « Serenity »).
TENANT_DEMO = TenantId("TENANT_DEMO")
# Le seul dossier fictif gardé en base, pour les reviews UX (décision du
# 2026-11-05). Compte : demo-sophie@axelcompta.fr.
DOSSIER_REVUE_UX = DossierId("DEMO_sophie")
_SIGNATAIRE_JALON = UserId("seed-demo")

# Préfixe de preuves de l'exercice 2025. Karim s'arrête à la clôture,
# Sophie au greffe, Yanis à la signature légale. L'ordre est celui de
# `JALONS_EXERCICE` : un trou plus loin ne fait pas avancer la frise.
JALONS_PAR_DOSSIER: dict[str, tuple[str, ...]] = {
    "DEMO_karim": ("cloture",),
    "DEMO_sophie": ("cloture", "validation_comptes", "greffe_inpi"),
    "DEMO_yanis": (
        "cloture",
        "validation_comptes",
        "greffe_inpi",
        "depot_impots",
        "signature_legale",
    ),
}

_DATE_JALON = {
    "cloture": datetime(2026, 3, 12, 9, 0, tzinfo=UTC),
    "validation_comptes": datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
    "greffe_inpi": datetime(2026, 5, 18, 11, 0, tzinfo=UTC),
    "depot_impots": datetime(2026, 5, 22, 14, 0, tzinfo=UTC),
    "signature_legale": datetime(2026, 6, 2, 16, 0, tzinfo=UTC),
}


class AmorcageIncompletError(RuntimeError):
    """Le ledger d'un dossier existe mais est incomplet : un amorçage
    précédent a été interrompu. Pas de reprise silencieuse (doc 08 §2.7),
    on ne complète pas un ledger à moitié écrit."""


def _dossier_depuis_profil(profil: ProfilChauffeurType) -> Dossier:
    return Dossier(
        id=profil.dossier_id,
        tenant_id=TENANT_DEMO,
        forme_juridique=profil.forme_juridique,
        regime_imposition="IS",
        # La franchise vaut pour la déclaration comme pour les recettes.
        regime_tva=("franchise" if profil.tva_recettes_regime == "franchise" else "reel_normal"),
        nom=profil.nom,
        tva_recettes_regime=profil.tva_recettes_regime,
        exercice_debut=profil.date_debut,
        plateformes=tuple(p.nom for p in profil.plateformes),
        mode_acces_bancaire=profil.mode_acces_bancaire,
        exercice_fin=fin_exercice(profil),
        identite=IDENTITES_DEMO[profil.dossier_id],
    )


def _id_unique(dossier_id: str, ecriture_id: EcritureId) -> EcritureId:
    """Le pipeline numérote les écritures par dossier (`categorise-1`,
    `settlement-72`...) : deux dossiers produisent les mêmes ids. Les tables
    `ecritures` et `propositions_categorisation` ont l'id pour clé primaire,
    il doit donc être unique globalement. Préfixe par le dossier plutôt que
    d'imposer une clé composite à tout le ledger. `:` et non `/`, car l'id
    passe dans une URL (`/transactions/{ecriture_id}/decision`)."""
    return EcritureId(f"{dossier_id}:{ecriture_id}")


def amorcer_demo(
    dossiers: DossierRepository,
    ledger: LedgerService,
    propositions: PropositionRepository,
    profils: tuple[ProfilChauffeurType, ...] = PROFILS_DEMO,
) -> list[str]:
    """Idempotent : un dossier dont le ledger est complet est laissé tel quel.
    Retourne les ids des dossiers effectivement écrits. Le portefeuille n'est
    créé que s'il n'existe pas (son nom en base n'est jamais écrasé)."""
    dossiers.enregistrer_tenant(Tenant(id=TENANT_DEMO, nom="Portefeuille démo"))
    ecrits: list[str] = []
    for profil in profils:
        dossiers.enregistrer(_dossier_depuis_profil(profil))
        ledger_calcule, props = construire_ledger(profil)
        attendues = ledger_calcule.grand_livre(profil.dossier_id)
        existantes = ledger.grand_livre(profil.dossier_id)
        if existantes:
            if len(existantes) != len(attendues):
                raise AmorcageIncompletError(
                    f"{profil.dossier_id} : {len(existantes)} écritures en base pour "
                    f"{len(attendues)} attendues. Vider les tables puis relancer."
                )
            continue
        for ecriture in attendues:
            ledger.enregistrer(
                dataclasses.replace(ecriture, id=_id_unique(profil.dossier_id, ecriture.id))
            )
        for ecriture_id, proposition in props.items():
            propositions.enregistrer(_id_unique(profil.dossier_id, ecriture_id), proposition)
        ecrits.append(profil.dossier_id)
    return ecrits


def _pdf_jalon(titre: str) -> bytes:
    """Pièce minimale : la frise ne lit que la présence de la ligne, pas
    le contenu. Le dépôt greffe, lui, reprend le PDF de synthèse réel."""
    tampon = io.BytesIO()
    dessin = canvas.Canvas(tampon, pagesize=A4)
    dessin.setFont("Helvetica", 14)
    dessin.drawString(72, 750, titre)
    dessin.setFont("Helvetica", 11)
    dessin.drawString(72, 720, "Exercice 2025 — pièce de démo AxeLCompta.")
    dessin.save()
    return tampon.getvalue()


def _contenu_jalon(type_document: str, dossier: Dossier, ledger: LedgerService) -> bytes:
    if type_document != "greffe_inpi":
        nom = next(libelle for type_, libelle in JALONS_EXERCICE if type_ == type_document)
        return _pdf_jalon(f"{nom} — {dossier.nom}")
    liasse = ClotureSimplifieeService(ledger).cloturer(
        dossier.id,
        exercice=str(dossier.exercice_debut.year),
        parametres=ParametresCloture(
            exercice_debut=dossier.exercice_debut,
            exercice_fin=dossier.fin_exercice(),
            forme_juridique=dossier.forme_juridique,
            identite=dossier.identite,
        ),
    )
    return PdfDepotInpiRenderer().rendre(liasse)


def poser_jalons_demo(
    dossiers: DossierRepository,
    ledger: LedgerService,
    signatures: SignatureRepository,
    seulement: frozenset[str] | None = None,
) -> list[str]:
    """Enregistre les preuves manquantes de l'exercice 2025. Idempotent :
    une preuve déjà là n'est pas réécrite (table append-only)."""
    poses: list[str] = []
    for dossier_id, types in JALONS_PAR_DOSSIER.items():
        if seulement is not None and dossier_id not in seulement:
            continue
        dossier = dossiers.obtenir(DossierId(dossier_id))
        if dossier is None:
            continue
        for type_document in types:
            if signatures.dernier(dossier.id, type_document) is not None:
                continue
            signatures.enregistrer(
                dossier.id,
                type_document,
                DocumentSigne(
                    contenu_pdf=_contenu_jalon(type_document, dossier, ledger),
                    signataire=_SIGNATAIRE_JALON,
                    signe_le=_DATE_JALON[type_document],
                    provider="demo",
                    qualifie=False,
                ),
            )
            poses.append(f"{dossier.id}:{type_document}")
    return poses


def main() -> int:
    engine = engine_depuis_env()
    dossiers = PostgresDossierRepository(engine)
    ledger = PostgresLedgerService(engine)
    profils = tuple(p for p in PROFILS_DEMO if p.dossier_id == DOSSIER_REVUE_UX)
    ecrits = amorcer_demo(dossiers, ledger, PostgresPropositionRepository(engine), profils)
    jalons = poser_jalons_demo(
        dossiers, ledger, PostgresSignatureRepository(engine), frozenset({DOSSIER_REVUE_UX})
    )
    if ecrits:
        print(f"Amorçage terminé : {', '.join(ecrits)}")
    else:
        print("Ledger déjà amorcé.")
    if jalons:
        print(f"Jalons 2025 posés : {', '.join(jalons)}")
    else:
        print("Jalons 2025 déjà en place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
