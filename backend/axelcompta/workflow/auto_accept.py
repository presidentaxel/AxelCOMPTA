"""AutoAcceptWorkflow — stand-in minimal pour la démo (doc 17 §3 : pas de
revue humaine). `workflow` est le seul module autorisé à transformer une
`ProposedEntry` en écriture réelle via `ledger` (doc 03 §3) : ici, tout est
accepté sans validation — simplification assumée pour la démo, pas
l'architecture cible (la vraie file de revue reste à construire, doc 05 §5).
"""

from __future__ import annotations

from axelcompta.categorize.models import ProposedEntry
from axelcompta.core.ids import EcritureId
from axelcompta.core.money import Money
from axelcompta.core.pcg import COMPTE_BANQUE
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.packs.tva_deductible import RegleTva

from .tva_imputation import lignes_imputees


def construire_ecriture_categorisee(
    transaction: NormalizedTransaction,
    proposition: ProposedEntry,
    compte: str,
    numero: int,
    compte_banque: str = COMPTE_BANQUE,
    regle_tva: RegleTva | None = None,
) -> Ecriture:
    """Banque (512, ou le sous-compte 512x du compte bancaire de l'opération,
    AXE-832) en contrepartie du compte de la catégorie (doc 06 §2). Le sens de
    chaque ligne suit le signe de la transaction (positif = argent reçu),
    pas la nature du compte — les deux s'accordent toujours en partie
    double. `regle_tva` (AXE-831) sépare la TVA déductible estimée du compte
    de la catégorie ; sans elle, tout le montant va au compte.
    """
    montant = Money(abs(transaction.montant_cts))
    sens_512 = Sens.DEBIT if transaction.montant_cts > 0 else Sens.CREDIT
    sens_compte = Sens.CREDIT if sens_512 is Sens.DEBIT else Sens.DEBIT
    return Ecriture(
        id=EcritureId(f"categorise-{numero}"),
        dossier_id=transaction.dossier_id,
        journal=Journal.BQ,
        date=transaction.date,
        # Le libellé de la banque, tel quel : la catégorie est dans la
        # proposition enregistrée, plus dans le libellé (AXE-848).
        libelle=transaction.libelle,
        reference_piece=None,
        lignes=(
            LigneEcriture(compte=compte_banque, sens=sens_512, montant=montant),
            *lignes_imputees(compte, sens_compte, montant, regle_tva),
        ),
    )
