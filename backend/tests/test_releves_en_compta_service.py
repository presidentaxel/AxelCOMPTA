"""AXE-833 : les relevés d'avant Digifactory, prouvés par le solde, écrits
une fois en comptabilité par la synchro ordinaire."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.categorize.pipeline import SansClassement
from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ingestion.comptes_bancaires import CompteBancaire, CompteBancaireMemoire
from axelcompta.ingestion.journal import InMemoryJournalIngestion
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.releves_en_compta_service import Depots, ecrire_releves
from axelcompta.tenants.fiches_import import document_import, nouvelle_fiche
from axelcompta.tenants.fiches_import_depot import FichesImportMemoire
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.traitement_documents_import import traiter as traiter_document_import
from axelcompta.workflow.propositions import InMemoryPropositionRepository

T = TenantId("t")
D = DossierId("DIGI_24951")
LE = datetime(2026, 11, 18, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 18)
DOSSIER = Dossier(
    id=D,
    tenant_id=T,
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="KERFICE SERVICE",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
    contact_nr="24951",
)
# Le relevé Bred : décembre 2025 (avant l'exercice) à mai 2026.
OPERATIONS = [
    (date(2025, 12, 10), 50_000, "VIR CAPITAL"),
    (date(2026, 1, 12), -4_500, "CB TOTAL"),
    (date(2026, 3, 2), 120_000, "VIR UBER"),
    (date(2026, 3, 2), 120_000, "VIR UBER"),  # deux virements identiques le même jour
    (date(2026, 5, 31), -2_000, "FRAIS BANCAIRES"),
]


def _qif(operations: list[tuple[date, int, str]]) -> bytes:
    lignes = ["!Type:Bank"]
    for jour, cts, libelle in operations:
        lignes += [f"D{jour:%d/%m/%Y}", f"T{cts / 100:.2f}", f"P{libelle}", "^"]
    return "\n".join(lignes).encode()


def _depots(ecart_cts: int = 0) -> tuple[Depots, str]:
    dossiers = InMemoryDossierRepository()
    dossiers.enregistrer_tenant(Tenant(T))
    dossiers.enregistrer(DOSSIER)
    ledger = InMemoryLedgerService()
    # Digifactory : une recette le 01/06/2026, la première qu'il a remontée.
    ledger.enregistrer(
        Ecriture(
            id=EcritureId(f"{D}:digifactory-tx1"),
            dossier_id=D,
            journal=Journal.BQ,
            date=date(2026, 6, 1),
            libelle="VIR BOLT",
            reference_piece=None,
            lignes=(
                LigneEcriture("5121", Sens.DEBIT, Money(10_000)),
                LigneEcriture("706", Sens.CREDIT, Money(10_000)),
            ),
        )
    )
    total = sum(cts for _j, cts, _l in OPERATIONS) + 10_000
    comptes = CompteBancaireMemoire()
    comptes.ajouter(
        CompteBancaire(
            D,
            "67499359",
            "5121",
            "Bred",
            total + ecart_cts,
            datetime(2026, 11, 17, tzinfo=UTC),
            retenu=True,
        )
    )
    fiches = FichesImportMemoire()
    fiche = nouvelle_fiche("fiche", T, "Konate", "K", "908771033", "b", LE)
    contenu = _qif(OPERATIONS)
    document = document_import(
        "qif-bred", fiche, "banque:releve_bancaire", "bred.qif", "", contenu, "b", LE
    )
    lu = traiter_document_import(document.categorie, document.nom_fichier, contenu)
    champs = {
        **fiche.champs,
        "date_creation": "2025-12-01",
        "debut_historique": "2026-06-01",
        "banque_rattachements": json.dumps({"doc:qif-bred": "digi:67499359"}),
    }
    fiches.enregistrer(replace(fiche, dossier_id=D, champs=champs))
    fiches.deposer(replace(document, donnees=lu.donnees), contenu)
    depots = Depots(
        fiches,
        dossiers,
        comptes,
        ledger,
        InMemoryJournalIngestion(),
        InMemoryPropositionRepository(),
    )
    return depots, fiche.id


def _ecrire(depots: Depots, fiche_id: str) -> str:
    return ecrire_releves(depots, T, fiche_id, SansClassement(), {}, AUJOURD_HUI)


def test_les_mois_d_avant_digifactory_sont_ecrits_une_seule_fois() -> None:
    depots, fiche_id = _depots()
    resume = _ecrire(depots, fiche_id)
    assert "Bred : 4 opération(s) écrite(s) du 01/01/2026 au 01/06/2026 exclu" in resume
    ecritures = [e for e in depots.ledger.grand_livre(D) if ":releve-" in e.id]
    assert sorted(e.date for e in ecritures) == [
        date(2026, 1, 12),
        date(2026, 3, 2),
        date(2026, 3, 2),
        date(2026, 5, 31),
    ]
    assert all(any(x.compte == "5121" for x in e.lignes) for e in ecritures)
    # Rejouer n'écrit rien de plus.
    assert "0 opération(s) écrite(s)" in _ecrire(depots, fiche_id)


def test_un_solde_qui_ne_tombe_pas_juste_n_ecrit_rien() -> None:
    depots, fiche_id = _depots(ecart_cts=1_000)
    resume = _ecrire(depots, fiche_id)
    assert "Bred : non écrit" in resume
    assert "n'est pas prouvée par le solde" in resume
    assert not [e for e in depots.ledger.grand_livre(D) if ":releve-" in e.id]


def test_une_fiche_sans_dossier_n_ecrit_rien() -> None:
    depots, fiche_id = _depots()
    fiche = depots.fiches.lire(T, fiche_id)
    depots.fiches.enregistrer(replace(fiche, dossier_id=None))
    assert "pas encore de dossier" in _ecrire(depots, fiche_id)
