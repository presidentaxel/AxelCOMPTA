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


def construire_ecriture_categorisee(
    transaction: NormalizedTransaction,
    proposition: ProposedEntry,
    compte: str,
    numero: int,
    compte_banque: str = COMPTE_BANQUE,
) -> Ecriture:
    """Banque (512, ou le sous-compte 512x du compte bancaire de l'opération,
    AXE-832) en contrepartie du compte de la catégorie (doc 06 §2). Le sens de
    chaque ligne suit le signe de la transaction (positif = argent reçu),
    pas la nature du compte — les deux s'accordent toujours en partie
    double. Pas de ventilation TVA ici : réservée au settlement plateforme
    (doc 13 §5.3), hors scope pour les dépenses courantes (doc 17 §3).
    """
    montant = Money(abs(transaction.montant_cts))
    sens_512 = Sens.DEBIT if transaction.montant_cts > 0 else Sens.CREDIT
    sens_compte = Sens.CREDIT if sens_512 is Sens.DEBIT else Sens.DEBIT
    return Ecriture(
        id=EcritureId(f"categorise-{numero}"),
        dossier_id=transaction.dossier_id,
        journal=Journal.BQ,
        date=transaction.date,
        libelle=f"{transaction.libelle} ({proposition.categorie})",
        reference_piece=None,
        lignes=(
            LigneEcriture(compte=compte_banque, sens=sens_512, montant=montant),
            LigneEcriture(compte=compte, sens=sens_compte, montant=montant),
        ),
    )
