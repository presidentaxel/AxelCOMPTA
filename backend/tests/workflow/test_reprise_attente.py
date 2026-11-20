"""AXE-850 : les opérations restées au 471 repassent dans le pipeline, avec
la même règle qu'une synchro neuve."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.pipeline import CategorizationPipeline
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.ecritures_semaines import id_solde
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.packs.vtc_demo import charger_compte_par_categorie
from axelcompta.workflow.reprise_attente import candidates, reprendre

D = DossierId("D")
COMPTES: tuple[dict[str, str | None], dict[str, str]] = ({}, charger_compte_par_categorie())


def _banque(ident: str, cts: int, libelle: str) -> Ecriture:
    entree = cts > 0
    return Ecriture(
        id=EcritureId(ident),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 10, 3),
        libelle=libelle,
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT if entree else Sens.CREDIT, Money(abs(cts))),
            LigneEcriture("471", Sens.CREDIT if entree else Sens.DEBIT, Money(abs(cts))),
        ),
    )


class Pipeline(CategorizationPipeline):
    """Carburant sûr par règle, péage incertain, Uber en attente de settlement."""

    def categoriser(self, dossier_id: DossierId, t: NormalizedTransaction) -> ProposedEntry:
        if "TOTAL" in t.libelle:
            return ProposedEntry(dossier_id, t.id, "carburant", Etage.REGLE, 0.95)
        if "UBER" in t.libelle:
            return ProposedEntry(dossier_id, t.id, "recettes_plateformes", Etage.REGLE, 0.99)
        return ProposedEntry(dossier_id, t.id, "peages", Etage.ML, 0.40)


def test_seule_une_proposition_sure_est_reclassee_le_512_ne_bouge_pas() -> None:
    ecritures = [
        _banque("total", -6000, "CB TOTAL ENERGIES"),
        _banque("peage", -320, "SANEF"),
        _banque("uber", 104600, "STICHTING CUSTODIAN UBER"),
    ]
    reprise = reprendre(D, ecritures, (), {}, Pipeline(), COMPTES)
    assert reprise.candidates == 3
    (od,) = reprise.reclassements
    assert od.id.startswith("total")
    assert not any(lg.compte.startswith("512") for lg in od.lignes)
    assert {lg.compte for lg in od.lignes} >= {"471"}


def test_decidee_soldee_ou_deja_reclassee_ne_repasse_pas() -> None:
    uber = _banque("uber", 104600, "UBER")
    solde = Ecriture(
        id=id_solde("uber"),
        dossier_id=D,
        journal=Journal.OD,
        date=date(2026, 10, 3),
        libelle="Versement Uber",
        reference_piece=None,
        lignes=(
            LigneEcriture("471", Sens.DEBIT, Money(104600)),
            LigneEcriture("4671", Sens.CREDIT, Money(104600)),
        ),
    )
    decidee = _banque("decidee", -1000, "CB TOTAL")
    total = _banque("total", -6000, "CB TOTAL")
    ecritures: Sequence[Ecriture] = [uber, solde, decidee, total]
    assert [e.id for e in candidates(ecritures, {EcritureId("decidee")})] == ["total"]
    premiere = reprendre(D, ecritures, {EcritureId("decidee")}, {}, Pipeline(), COMPTES)
    # Rejouable : une fois l'OD écrite, l'opération n'est plus candidate.
    apres = [*ecritures, *premiere.reclassements]
    assert reprendre(D, apres, {EcritureId("decidee")}, {}, Pipeline(), COMPTES).reclassements == ()
