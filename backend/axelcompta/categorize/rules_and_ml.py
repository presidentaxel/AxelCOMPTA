"""RulesAndMlPipeline — étages déterministes et ML (doc 05), pas de LLM.

Ordre, pour chaque opération (AXE-826) :

0. **virement interne** : deux jambes opposées sur deux comptes du dossier
   (`virements_internes.py`), avant toute règle — sinon « carburant » ou
   « cotisation URSSAF » sur un virement entre enveloppes passe pour une
   dépense ;
1. **règles** du pack, sauf les règles de paiement sur un virement
   (`type_operation == "transfer"`) ;
2. **modèle** ML, qui s'abstient sous son seuil ;
3. **catégorie de la banque** (Bridge), seulement si le modèle s'abstient :
   une proposition, jamais une imputation (`Etage.BANQUE`).
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from threading import Lock

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.packs.vtc_demo import RegleCategorisation

from .ml_fallback import Calibration, ModeleSklearn, predire_lot, sens_compatible
from .models import Etage, ProposedEntry
from .pipeline import CategorizationPipeline
from .virements_internes import CATEGORIE_VIREMENT_INTERNE, apparier_virements_internes

CONFIANCE_PAR_NIVEAU = {"haute": 0.95, "moyenne": 0.75, "basse": 0.5}
# Retrait au distributeur (AXE-844) : la catégorie n'a pas de compte, il
# reste à trancher et le chauffeur répond à une question dédiée.
CATEGORIE_RETRAIT_ESPECES = "retrait_especes"
TYPE_RETRAIT = "withdrawal"
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

# Deux jambes appariées : quasi certain, impute au 580 (seuil des règles 0,75).
CONFIANCE_VIREMENT_INTERNE = 0.95
# Catégorie de la banque : sous tout seuil d'imputation, elle ne fait que
# proposer. Bridge range TOTAL en « Supermarchés » et un virement « carburant »
# en « Bars & Clubs » : pas de quoi écrire en comptabilité sans regard humain.
CONFIANCE_CATEGORIE_BANQUE = 0.5

# Ce qu'on paie à un commerçant (carte, prélèvement). Sur un virement, ces
# règles ne valent rien : un virement libellé « carburant » entre deux
# enveloppes n'est pas un plein.
CATEGORIES_DE_PAIEMENT = frozenset(
    {
        "carburant",
        "peage_stationnement",
        "entretien_reparation_vehicule",
        "assurance_vehicule",
        "telecommunications",
        "repas_et_receptions",
        "usage_personnel_suspect",
        "amendes_infractions",
        "charges_sociales_impots",
    }
)

Cle = tuple[str, int, str | None, str | None]


def _cle(transaction: NormalizedTransaction) -> Cle:
    """Tout ce dont dépend le résultat hors appariement."""
    return (
        transaction.libelle,
        transaction.montant_cts,
        transaction.type_operation,
        transaction.categorie_banque,
    )


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
    # `{category_id de la banque: catégorie du pack}` (AXE-826).
    categories_banque: Mapping[str, str] = field(default_factory=dict)
    # Résultat par clé (`_cle`), le plus récemment lu en dernier. Propre
    # à cette instance : règles, modèle et calibration ne changent pas après
    # sa construction, donc la mémoire ne périme pas. Elle ne survit pas à un
    # redémarrage et n'est pas partagée entre workers.
    _memoire: OrderedDict[Cle, ProposedEntry] = field(
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
        """Les virements internes se voient dans le lot entier : à passer ici
        plutôt que ligne par ligne. Hors virement interne, le résultat ne
        dépend que de `_cle` : une opération déjà vue le reprend de la
        mémoire, sans règle ni modèle."""
        paires = apparier_virements_internes(transactions)
        propositions = self._hors_virements(
            dossier_id, [t for t in transactions if t.id not in paires]
        )
        par_id = {p.transaction_id: p for p in propositions}
        return [
            par_id[t.id]
            if t.id not in paires
            else ProposedEntry(
                dossier_id=dossier_id,
                transaction_id=t.id,
                categorie=CATEGORIE_VIREMENT_INTERNE,
                etage=Etage.REGLE,
                confiance=CONFIANCE_VIREMENT_INTERNE,
            )
            for t in transactions
        ]

    def _hors_virements(
        self, dossier_id: DossierId, transactions: Sequence[NormalizedTransaction]
    ) -> list[ProposedEntry]:
        """Une fois par clé : la mémoire, sinon règles puis modèle."""
        cles = [_cle(t) for t in transactions]
        with self._verrou:
            connues = {cle: self._memoire[cle] for cle in set(cles) if cle in self._memoire}
            for cle in connues:
                self._memoire.move_to_end(cle)
        inconnues: dict[Cle, NormalizedTransaction] = {}
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

    def _retenir(self, calculees: dict[Cle, ProposedEntry]) -> None:
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
            propositions[i] = self._via_banque(transactions[i], proposition)
        return [proposition for proposition in propositions if proposition is not None]

    def _via_banque(
        self, transaction: NormalizedTransaction, proposition: ProposedEntry
    ) -> ProposedEntry:
        """Le modèle s'abstient : la catégorie de la banque, si la table la
        connaît et qu'elle va dans le bon sens, devient la proposition."""
        if proposition.categorie != CATEGORIE_PAR_DEFAUT or transaction.categorie_banque is None:
            return proposition
        categorie = self.categories_banque.get(transaction.categorie_banque)
        if categorie is None or not sens_compatible(categorie, transaction.montant_cts):
            return proposition
        return replace(
            proposition,
            categorie=categorie,
            etage=Etage.BANQUE,
            confiance=CONFIANCE_CATEGORIE_BANQUE,
            seuil_imputation=None,
        )

    def _via_regles(
        self, dossier_id: DossierId, transaction: NormalizedTransaction
    ) -> ProposedEntry | None:
        if transaction.type_operation == TYPE_RETRAIT and transaction.montant_cts < 0:
            # AXE-844 : la banque dit « retrait », quel que soit le libellé.
            return ProposedEntry(
                dossier_id=dossier_id,
                transaction_id=transaction.id,
                categorie=CATEGORIE_RETRAIT_ESPECES,
                etage=Etage.REGLE,
                confiance=CONFIANCE_PAR_NIVEAU["haute"],
            )
        for regle in self.regles:
            # Même garde que l'étage ML : « uber » dans un paiement sortant
            # n'est pas une recette. La règle suivante, puis le modèle, prennent
            # le relais.
            if not sens_compatible(regle.categorie, transaction.montant_cts):
                continue
            if (
                transaction.type_operation == "transfer"
                and regle.categorie in CATEGORIES_DE_PAIEMENT
            ):
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
