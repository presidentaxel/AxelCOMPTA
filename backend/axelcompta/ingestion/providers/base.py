"""ABC DataProvider + types partagés (doc 13 §2.2).

Contrat unique pour toute source de données d'entrée — la config du dossier
détermine quel(s) provider(s) sont actifs, jamais de branchement conditionnel
dans le code métier. Squelette : signatures uniquement, aucune implémentation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime

from axelcompta.core.ids import DossierId, TenantId, TransactionId


@dataclass(frozen=True, slots=True)
class NormalizedTransaction:
    """Transaction bancaire normalisée (doc 04 §5 : la sortie unique du module).

    `id` : clé de déduplication stable (doc 16 §5 — "bloquant"). Chaque
    provider construit son propre id de façon déterministe (id natif du
    fournisseur si disponible, sinon dérivé du dossier + de la référence de
    pièce + de la date).
    """

    id: TransactionId
    dossier_id: DossierId
    date: date
    montant_cts: int
    libelle: str
    source_provider: str
    raw_payload: dict[str, object]
    # Identifiant du compte bancaire chez le fournisseur (Digifactory :
    # `account_id`). Sert à choisir le sous-compte 512x (AXE-832). `None`
    # quand la source ne le donne pas : l'écriture va alors au 512.
    compte_bancaire: str | None = None
    # Signaux de la banque (AXE-826), `None` quand la source ne les donne pas.
    # `type_operation` : « card », « transfer », « direct_debit »… ;
    # `categorie_banque` : catégorie de l'agrégateur (Bridge, via Digifactory
    # `category_id`). Un indice, jamais une décision : voir
    # `categorize/rules_and_ml.py`.
    type_operation: str | None = None
    categorie_banque: str | None = None


@dataclass(frozen=True, slots=True)
class Rejet:
    """Une ligne du fournisseur que le parseur n'a pas pu normaliser. Jamais
    ignorée en silence : elle part en quarantaine avec sa raison."""

    payload: dict[str, object]
    raison: str


@dataclass(frozen=True, slots=True)
class LotTransactions:
    """Résultat d'une lecture incrémentale (doc 16 §5).

    `brutes` : tout ce que le fournisseur a renvoyé, pour l'archivage
    immuable (doc 12 §1.2). `supprimees` : ids marqués `deleted`, à ne jamais
    comptabiliser mais à signaler s'ils l'étaient déjà. `curseur` : plus grand
    `updated_at` vu (y compris sur les lignes filtrées), point de reprise du
    prochain appel ; `None` si rien n'a été renvoyé."""

    transactions: tuple[NormalizedTransaction, ...]
    rejets: tuple[Rejet, ...] = ()
    supprimees: tuple[TransactionId, ...] = ()
    brutes: tuple[dict[str, object], ...] = field(default_factory=tuple)
    curseur: datetime | None = None


@dataclass(frozen=True, slots=True)
class PlatformSettlement:
    """Relevé de plateforme gig — Uber, Bolt... (doc 13 §4.1)."""

    dossier_id: DossierId
    platform: str
    period_start: date
    period_end: date
    payout_date: date
    gross_earnings_cts: int
    commission_cts: int
    commission_tva_regime: str
    net_payout_cts: int
    currency: str
    source_provider: str
    raw_payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Santé de la connexion (consentement valide, quota restant...)."""

    ok: bool
    message: str


class DataProvider(ABC):
    """Contrat unique pour toute source de données d'entrée (doc 13 §2.2)."""

    @abstractmethod
    async def fetch_transactions(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        since: date,
        until: date,
    ) -> list[NormalizedTransaction]:
        """Transactions bancaires normalisées."""

    @abstractmethod
    async def fetch_platform_settlements(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        since: date,
        until: date,
    ) -> list[PlatformSettlement]:
        """Relevés de plateformes (Uber, Bolt...). Peut retourner [] si non supporté."""

    @abstractmethod
    async def health(self) -> ProviderHealth:
        """Santé de la connexion (consentement valide, quota restant...)."""
