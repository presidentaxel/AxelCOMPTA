"""RulesAndMlPipeline — implémentation concrète pour la démo (doc 17 §3) :
étage 1 (règles) puis étage 2 (ML), pas de LLM ni de revue humaine.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from threading import Lock

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.packs.vtc_demo import RegleCategorisation

from .ml_fallback import Calibration, ModeleSklearn, predire_lot, sens_compatible
from .models import Etage, ProposedEntry
from .pipeline import CategorizationPipeline

CONFIANCE_PAR_NIVEAU = {"haute": 0.95, "moyenne": 0.75, "basse": 0.5}
CATEGORIE_PAR_DEFAUT = "non_categorise_a_verifier"

# Sous ce seuil, le modèle ne propose rien : l'indiv voit « pas de proposition
# automatique » plutôt qu'une catégorie fausse à confirmer d'un geste. Choisi
# sur des dossiers jamais vus à l'entraînement (validation croisée en 5 plis
# par dossier sur le jeu d'audit, 2026-09-27) : à 0,5, 64 % des lignes
# reçoivent une proposition, juste dans 92 % des cas, contre 76 % sans seuil.
# Réglé sur ce jeu seulement, jamais sur les dossiers réels à qui on
# l'applique. Distinct
# du seuil d'imputation automatique (`workflow/synchro.py`, 0,90).
SEUIL_PROPOSITION_ML = 0.5

# Bornée : au-delà, les résultats les moins récemment lus sont oubliés.
CAPACITE_MEMOIRE = 50_000


@dataclass
class RulesAndMlPipeline(CategorizationPipeline):
    """Étage 1 : première règle du pack qui matche le libellé.
    Étage 2 : modèle ML si aucune règle ne matche, qui s'abstient sous
    `SEUIL_PROPOSITION_ML`. Modèle absent
    (`modele=None`, ex. fichier gitignoré manquant sur ce poste) → dégradation
    explicite en catégorie par défaut à confiance nulle, pas un plantage
    (doc 08 §5)."""

    regles: tuple[RegleCategorisation, ...]
    modele: ModeleSklearn | None = None
    # Sans calibration, confiance brute et seuils historiques.
    calibration: Calibration | None = None
    # Résultat par (libellé, montant), le plus récemment lu en dernier. Propre
    # à cette instance : règles, modèle et calibration ne changent pas après
    # sa construction, donc la mémoire ne périme pas. Elle ne survit pas à un
    # redémarrage et n'est pas partagée entre workers.
    _memoire: OrderedDict[tuple[str, int], ProposedEntry] = field(
        default_factory=OrderedDict, init=False, repr=False, compare=False
    )
    _verrou: Lock = field(default_factory=Lock, init=False, repr=False, compare=False)

    def categoriser(
        self, dossier_id: DossierId, transaction: NormalizedTransaction
    ) -> ProposedEntry:
        return self.categoriser_lot(dossier_id, [transaction])[0]

    def categoriser_lot(
        self, dossier_id: DossierId, transactions: Sequence[NormalizedTransaction]
    ) -> list[ProposedEntry]:
        """Même résultat que `categoriser` ligne par ligne. Le résultat ne
        dépend que du libellé et du montant : une opération déjà vue les
        reprend de la mémoire, sans règle ni modèle. Seules les autres vont à
        `_calculer`, une fois par couple (libellé, montant)."""
        cles = [(t.libelle, t.montant_cts) for t in transactions]
        with self._verrou:
            connues = {cle: self._memoire[cle] for cle in set(cles) if cle in self._memoire}
            for cle in connues:
                self._memoire.move_to_end(cle)
        inconnues: dict[tuple[str, int], NormalizedTransaction] = {}
        for cle, transaction in zip(cles, transactions, strict=True):
            if cle not in connues:
                inconnues.setdefault(cle, transaction)
        if inconnues:
            calculees = dict(
                zip(
                    inconnues,
                    self._calculer(dossier_id, list(inconnues.values())),
                    strict=True,
                )
            )
            self._retenir(calculees)
            connues = {**connues, **calculees}
        return [
            replace(connues[cle], dossier_id=dossier_id, transaction_id=transaction.id)
            for cle, transaction in zip(cles, transactions, strict=True)
        ]

    def _retenir(self, calculees: dict[tuple[str, int], ProposedEntry]) -> None:
        with self._verrou:
            self._memoire.update(calculees)
            while len(self._memoire) > CAPACITE_MEMOIRE:
                self._memoire.popitem(last=False)

    def _calculer(
        self, dossier_id: DossierId, transactions: Sequence[NormalizedTransaction]
    ) -> list[ProposedEntry]:
        """Règles d'abord, puis un seul appel au modèle pour toutes les
        transactions qu'aucune règle ne couvre."""
        propositions: list[ProposedEntry | None] = [
            self._via_regles(dossier_id, transaction) for transaction in transactions
        ]
        sans_regle = [i for i, proposition in enumerate(propositions) if proposition is None]
        for i, proposition in zip(
            sans_regle,
            self._via_ml(dossier_id, [transactions[i] for i in sans_regle]),
            strict=True,
        ):
            propositions[i] = proposition
        return [proposition for proposition in propositions if proposition is not None]

    def _via_regles(
        self, dossier_id: DossierId, transaction: NormalizedTransaction
    ) -> ProposedEntry | None:
        for regle in self.regles:
            # Même garde que l'étage ML : « uber » dans un paiement sortant
            # n'est pas une recette. La règle suivante, puis le modèle, prennent
            # le relais.
            if not sens_compatible(regle.categorie, transaction.montant_cts):
                continue
            if regle.motif.search(transaction.libelle):
                return ProposedEntry(
                    dossier_id=dossier_id,
                    transaction_id=transaction.id,
                    categorie=regle.categorie,
                    etage=Etage.REGLE,
                    confiance=CONFIANCE_PAR_NIVEAU.get(regle.confiance, 0.5),
                )
        return None

    def _via_ml(
        self, dossier_id: DossierId, transactions: Sequence[NormalizedTransaction]
    ) -> list[ProposedEntry]:
        if self.modele is None:
            predictions = [(CATEGORIE_PAR_DEFAUT, 0.0)] * len(transactions)
        else:
            predictions = predire_lot(
                self.modele,
                [(t.libelle, t.montant_cts) for t in transactions],
                self.calibration,
            )
        seuil = (
            self.calibration.seuil_proposition
            if self.calibration is not None
            else SEUIL_PROPOSITION_ML
        )
        return [
            ProposedEntry(
                dossier_id=dossier_id,
                transaction_id=transaction.id,
                categorie=categorie if confiance >= seuil else CATEGORIE_PAR_DEFAUT,
                etage=Etage.ML,
                confiance=confiance,
                seuil_imputation=(
                    self.calibration.seuil_imputation_de(categorie)
                    if self.calibration is not None
                    else None
                ),
            )
            for transaction, (categorie, confiance) in zip(transactions, predictions, strict=True)
        ]
