"""DigifactoryProvider — transactions bancaires, agrège Bridge par contact (doc 16).

**Débloqué le 2026-09-11** (doc 16 §7) : le 401 venait d'un mauvais type
d'en-tête documenté depuis le début (`Authorization: Bearer`), pas d'un
problème Digifactory ou client. Le bon en-tête est `X_DIGI_TOKEN` (shared
secret). Vérifié par appel réel sur `/contacts`, `/categories`,
`/accounts/{nr}` et `/transactions/{nr}` — voir `DigifactoryHttpClient`
ci-dessous pour le chemin A (vrais appels HTTP).

`DigifactoryProvider` (chemin `DataProvider`, en bas de fichier) reste sur
fixtures par défaut : brancher `client_reel` (`DigifactoryHttpClient`) fait
passer `health()` en vrai appel, mais `fetch_transactions`/
`fetch_platform_settlements` ne peuvent pas encore appeler l'API réelle
pour un `dossier_id` donné — il manque la table de correspondance
`contact_nr → dossier_id` (doc 16 §9 point 5, jamais construite, ~200
chauffeurs). Pas fait ici : inventer ce mapping avant d'avoir la vraie
liste serait fabriqué, pas réel.

`parser_transactions` a un vrai écart trouvé en testant contre de vraies
données (2026-09-11) : le payload réel indexe chaque compte par un **dict
`{transactionId: transaction}`**, pas une liste comme documenté au départ
(doc 16 §3.1) — `_transactions_de_compte` normalise les deux formes.
"""

from __future__ import annotations

import calendar
import os
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

import httpx

from axelcompta.core.ids import DossierId, TenantId, TransactionId
from axelcompta.tenants.models import Dossier

from .base import (
    DataProvider,
    LotTransactions,
    NormalizedTransaction,
    PlatformSettlement,
    ProviderHealth,
    Rejet,
)

# Payload JSON brut du fournisseur — forme non figée à dessein (`Any` au
# niveau compte) : un compte peut être une liste de transactions (doc 16
# §3.1 documenté) ou un dict {transactionId: transaction} (réel, vérifié
# 2026-09-11, voir `_transactions_de_compte`) ; `Mapping` plutôt que `dict`
# pour rester covariant (les littéraux de test n'ont pas besoin de coller
# exactement au type).
PayloadTransactions = Mapping[str, Any]

# Payload figé au schéma doc 16 §3.1 (objet indexé par accountId) et §4 (champs
# confirmés). Un `deleted` et un `future` sont inclus exprès pour prouver que
# le filtrage (doc 16 §4 : « ne jamais comptabiliser ») fonctionne vraiment.
FIXTURE_PAYLOAD_PAR_DEFAUT: PayloadTransactions = {
    "acc_demo_1": [
        {
            "id": "tx_1",
            "account_id": "acc_demo_1",
            "provider_description": "VIR RECU UBER BV",
            "clean_description": "Uber BV",
            "amount": 848.00,
            "currency_code": "EUR",
            "date": "2026-09-03",
            "updated_at": "2026-09-03T10:00:00",
            "deleted": False,
            "future": False,
            "operation_type": "transfer",
            "category_id": "income",
        },
        {
            "id": "tx_2",
            "account_id": "acc_demo_1",
            "provider_description": "PRELEVEMENT ANNULE",
            "amount": 42.00,
            "currency_code": "EUR",
            "date": "2026-09-04",
            "updated_at": "2026-09-04T08:00:00",
            "deleted": True,
            "future": False,
        },
        {
            "id": "tx_3",
            "account_id": "acc_demo_1",
            "provider_description": "VIREMENT PROGRAMME",
            "amount": 100.00,
            "currency_code": "EUR",
            "date": "2099-01-01",
            "updated_at": "2026-09-04T08:00:00",
            "deleted": False,
            "future": True,
        },
    ]
}


def _vers_centimes(montant: float | str) -> int:
    return int((Decimal(str(montant)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _transactions_de_compte(valeur: Any) -> list[dict[str, Any]]:
    """Chaque compte du payload `/transactions` est documenté (doc 16 §3.1)
    comme une **liste** de transactions. **Réel, vérifié le 2026-09-11** :
    c'est en fait un **dict `{transactionId: transaction}`**. Accepte les
    deux formes plutôt que de figer sur l'une — la fixture de test garde
    le format liste (plus simple à lire), le payload réel capturé est un
    dict ; aucune raison de réécrire les fixtures existantes pour ça."""
    if isinstance(valeur, dict):
        return cast("list[dict[str, Any]]", list(valeur.values()))
    return cast("list[dict[str, Any]]", valeur)


def _horodatage(valeur: object) -> datetime:
    """`updated_at` sans fuseau (doc 16 §5, fuseau source encore à confirmer) :
    normalisé en naïf UTC pour que les comparaisons ne mélangent jamais naïf
    et aware."""
    horodatage = datetime.fromisoformat(str(valeur))
    if horodatage.tzinfo is not None:
        horodatage = horodatage.astimezone(UTC).replace(tzinfo=None)
    return horodatage


def _normaliser(tx: dict[str, Any], dossier_id: DossierId) -> NormalizedTransaction:
    """Lève `ValueError` avec une raison lisible si la ligne est inexploitable."""
    for champ in ("id", "date", "amount", "updated_at"):
        if tx.get(champ) in (None, ""):
            raise ValueError(f"champ obligatoire manquant : {champ}")
    try:
        date_operation = datetime.fromisoformat(str(tx["date"])).date()
        montant = _vers_centimes(tx["amount"])
        _horodatage(tx["updated_at"])
    except (ValueError, ArithmeticError) as erreur:
        raise ValueError(f"valeur illisible : {erreur}") from erreur
    return NormalizedTransaction(
        id=TransactionId(str(tx["id"])),
        dossier_id=dossier_id,
        date=date_operation,
        montant_cts=montant,
        libelle=str(tx.get("provider_description", "")),
        source_provider="digifactory",
        raw_payload=tx,
        compte_bancaire=_identifiant_compte(tx.get("account_id")),
    )


def _identifiant_compte(valeur: object) -> str | None:
    """`account_id` de la transaction (doc 16 §3.1 : la clé du payload n'est
    pas fiable, ce champ l'est). Absent ou vide : banque inconnue."""
    if valeur is None:
        return None
    texte = str(valeur).strip()
    return texte or None


def fenetres_mensuelles(debut: date, jusqua: date) -> tuple[tuple[datetime, datetime], ...]:
    """Découpe [debut, jusqua] en mois calendaires (doc 16 §5).

    Le premier chargement, sans curseur, ne doit pas appeler `/transactions`
    sans borne : un contact a déjà renvoyé ~2 000 lignes d'un bloc. `from`/`to`
    filtrent la date d'opération ; le sync suivant repart sur `since`.
    """
    if debut > jusqua:
        return ()
    fenetres: list[tuple[datetime, datetime]] = []
    curseur = debut
    while curseur <= jusqua:
        dernier_jour = calendar.monthrange(curseur.year, curseur.month)[1]
        fin_mois = date(curseur.year, curseur.month, dernier_jour)
        fin = min(fin_mois, jusqua)
        fenetres.append(
            (
                datetime(curseur.year, curseur.month, curseur.day),
                datetime(fin.year, fin.month, fin.day, 23, 59, 59),
            )
        )
        curseur = fin_mois + timedelta(days=1)
    return tuple(fenetres)


def fusionner_lots(lots: tuple[LotTransactions, ...]) -> LotTransactions:
    """Réunit les mois d'un premier chargement. Un même id gardé une fois,
    à l'`updated_at` le plus récent."""
    if not lots:
        return LotTransactions(transactions=())
    par_id: dict[str, NormalizedTransaction] = {}
    for lot in lots:
        for transaction in lot.transactions:
            existante = par_id.get(str(transaction.id))
            plus_recente = existante is None or _horodatage(
                transaction.raw_payload["updated_at"]
            ) >= _horodatage(existante.raw_payload["updated_at"])
            if plus_recente:
                par_id[str(transaction.id)] = transaction
    curseurs = [lot.curseur for lot in lots if lot.curseur is not None]
    identifiants = dict.fromkeys(identifiant for lot in lots for identifiant in lot.supprimees)
    return LotTransactions(
        transactions=tuple(sorted(par_id.values(), key=lambda transaction: transaction.date)),
        rejets=tuple(rejet for lot in lots for rejet in lot.rejets),
        supprimees=tuple(identifiants),
        brutes=tuple(brute for lot in lots for brute in lot.brutes),
        curseur=max(curseurs) if curseurs else None,
    )


def parser_lot(
    payload: PayloadTransactions | list[Any],
    dossier_id: DossierId,
    depuis: date = date.min,
    jusqua: date = date.max,
) -> LotTransactions:
    """Ne dépend pas de la clé du payload (⚠️ doc 16 §3.1) : la clé indexe la
    réponse mais chaque transaction est prise telle quelle. Filtre
    deleted/future (doc 16 §4) et déduplique par `id`, en gardant
    l'`updated_at` le plus récent (doc 16 §5).

    Une ligne malformée n'interrompt pas le lot : elle devient un `Rejet`
    (quarantaine), les autres sont traitées. Avant le 2026-09-21, une seule
    ligne sans `id` faisait échouer toute la synchro d'un dossier."""
    brutes: list[dict[str, object]] = []
    rejets: list[Rejet] = []
    supprimees: set[str] = set()
    plus_recentes: dict[str, dict[str, Any]] = {}
    curseur: datetime | None = None

    if not isinstance(payload, Mapping):
        return LotTransactions(transactions=())

    for compte in payload.values():
        for tx in _transactions_de_compte(compte):
            brutes.append(tx)
            try:
                maj = _horodatage(tx["updated_at"])
                curseur = maj if curseur is None or maj > curseur else curseur
            except (KeyError, ValueError):
                pass  # signalé plus bas si la ligne est retenue
            if tx.get("deleted"):
                if tx.get("id") is not None:
                    supprimees.add(str(tx["id"]))
                continue
            if tx.get("future"):
                continue
            try:
                _normaliser(tx, dossier_id)
            except ValueError as erreur:
                rejets.append(Rejet(payload=tx, raison=str(erreur)))
                continue
            existante = plus_recentes.get(str(tx["id"]))
            if existante is None or _horodatage(tx["updated_at"]) > _horodatage(
                existante["updated_at"]
            ):
                plus_recentes[str(tx["id"])] = tx

    retenues = [_normaliser(tx, dossier_id) for tx in plus_recentes.values()]
    return LotTransactions(
        transactions=tuple(
            sorted((t for t in retenues if depuis <= t.date <= jusqua), key=lambda t: t.date)
        ),
        rejets=tuple(rejets),
        supprimees=tuple(TransactionId(i) for i in sorted(supprimees)),
        brutes=tuple(brutes),
        curseur=curseur,
    )


def parser_transactions(
    payload: PayloadTransactions,
    dossier_id: DossierId,
    depuis: date,
    jusqua: date,
) -> list[NormalizedTransaction]:
    """Fenêtre de dates, sans le détail du lot (rejets, curseur) : voir
    `parser_lot` pour la synchronisation incrémentale."""
    return list(parser_lot(payload, dossier_id, depuis, jusqua).transactions)


FORMAT_DATE_DIGIFACTORY = "%Y-%m-%d %H:%M:%S"  # doc 16 §1, sans fuseau (⚠️ à confirmer)


class ContactNonMappeError(RuntimeError):
    """Le dossier n'a pas de `contact_nr` : on ne devine jamais quel contact
    Digifactory appeler (doc 16 §9 point 5)."""


def chauffeur_peut_connecter_sa_banque(dossier: Dossier) -> bool:
    """doc 19 §4. Le bouton n'existe que si l'indiv relie lui-même sa banque.
    Un `contact_nr` posé veut dire que Digifactory est branché par le
    gestionnaire : on ne propose pas une seconde connexion."""
    if dossier.contact_nr:
        return False
    return dossier.mode_acces_bancaire == "chauffeur_direct"


def _filtrer_depuis(lot: LotTransactions, depuis_maj: datetime) -> LotTransactions:
    """Stand-in du filtre `since` de l'API pour le mode fixture : ne garde que
    les transactions mises à jour depuis le curseur."""
    return LotTransactions(
        transactions=tuple(
            t for t in lot.transactions if _horodatage(t.raw_payload["updated_at"]) >= depuis_maj
        ),
        rejets=lot.rejets,
        supprimees=lot.supprimees,
        brutes=lot.brutes,
        curseur=lot.curseur,
    )


class DigifactoryAuthError(RuntimeError):
    """401 réel de l'API — distinct d'une erreur réseau (doc 16 §1 : le
    token est révocable à tout moment, ce cas doit être géré explicitement)."""


class DigifactoryHttpClient:
    """Chemin A (doc 16 §7) : vrais appels HTTP à l'API Digifactory.

    Auth confirmée en réel le 2026-09-11 : en-tête `X_DIGI_TOKEN: <token>`
    — **pas** `Authorization: Bearer` (doc 16 §2, deux types de token chez
    Digifactory, la spec initiale nous avait donné l'autre). `/contacts`,
    `/categories`, `/accounts/{nr}` et `/transactions/{nr}` tous vérifiés
    200 en réel avec cet en-tête.

    N'appelle jamais l'API à la construction (même règle que
    `SupabaseCompteRepository`, doc 17 §9 bloc B) — seulement à la première
    méthode effectivement invoquée.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._client_fourni = client is not None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            headers={"accept": "*/*", "X_DIGI_TOKEN": token},
            timeout=timeout,
        )

    @classmethod
    def depuis_env(cls) -> DigifactoryHttpClient:
        """Lit `DIGIFACTORY_BASE_URL`/`DIGIFACTORY_TOKEN` (`.env`, doc 16 §2)."""
        base_url = os.environ.get("DIGIFACTORY_BASE_URL")
        token = os.environ.get("DIGIFACTORY_TOKEN")
        if not base_url or not token:
            raise RuntimeError(
                "DIGIFACTORY_BASE_URL/DIGIFACTORY_TOKEN manquantes — "
                "voir .env.example à la racine du repo"
            )
        return cls(base_url, token)

    async def _get(self, chemin: str, params: dict[str, str] | None = None) -> Any:
        reponse = await self._client.get(chemin, params=params)
        if reponse.status_code == 401:
            raise DigifactoryAuthError(f"401 sur {chemin} — token invalide/révoqué (doc 16 §1)")
        reponse.raise_for_status()
        return reponse.json()

    async def contacts(self) -> dict[str, Any]:
        """doc 16 §3.3 : objet indexé par `nr`."""
        return cast(dict[str, Any], await self._get("/contacts"))

    async def accounts(self, contact_nr: str | int) -> dict[str, Any] | list[Any]:
        """doc 16 §3.2. **Réel (2026-09-11)** : `[]` (liste vide, pas `{}`)
        quand le contact n'a aucun compte connecté."""
        return cast("dict[str, Any] | list[Any]", await self._get(f"/accounts/{contact_nr}"))

    async def transactions(
        self,
        contact_nr: str | int,
        since: datetime | None = None,
        debut: datetime | None = None,
        fin: datetime | None = None,
    ) -> PayloadTransactions | list[Any]:
        """doc 16 §3.1. `since` filtre `updated_at` (sync courant). `debut`/`fin`
        deviennent `from`/`to` (date d'opération) pour le premier chargement,
        découpé par mois."""
        params: dict[str, str] = {}
        if since is not None:
            params["since"] = since.strftime(FORMAT_DATE_DIGIFACTORY)
        if debut is not None:
            params["from"] = debut.strftime(FORMAT_DATE_DIGIFACTORY)
        if fin is not None:
            params["to"] = fin.strftime(FORMAT_DATE_DIGIFACTORY)
        return cast(
            "PayloadTransactions | list[Any]",
            await self._get(f"/transactions/{contact_nr}", params or None),
        )

    async def categories(self) -> dict[str, Any]:
        return cast(dict[str, Any], await self._get("/categories"))

    async def aclose(self) -> None:
        if not self._client_fourni:
            await self._client.aclose()


class DigifactoryProvider(DataProvider):
    """doc 16. `payload` injectable pour les tests ; par défaut la fixture
    ci-dessus (chemin B, doc 16 §7).

    `client_reel` (optionnel) : un `DigifactoryHttpClient` pour que
    `health()` fasse un vrai appel plutôt que de retourner le message figé
    "fixtures actives". **`fetch_transactions`/`fetch_platform_settlements`
    n'utilisent pas encore `client_reel`** — il manque la table de
    correspondance `contact_nr → dossier_id` (doc 16 §9 point 5, jamais
    construite) pour savoir quel contact Digifactory appeler pour un
    `dossier_id` donné. Le brancher pour de vrai est la suite logique une
    fois cette table réelle disponible, pas avant."""

    def __init__(
        self,
        payload: PayloadTransactions | None = None,
        client_reel: DigifactoryHttpClient | None = None,
    ) -> None:
        self._payload = payload if payload is not None else FIXTURE_PAYLOAD_PAR_DEFAUT
        self._client_reel = client_reel

    async def fetch_transactions(
        self, tenant_id: TenantId, dossier_id: DossierId, since: date, until: date
    ) -> list[NormalizedTransaction]:
        """Fenêtre de dates. Sans `client_reel`, la fixture ; avec, l'API réelle
        **sans** filtre `since` (une fenêtre de dates ne se traduit pas en
        `updated_at`) : lourd (doc 16 §5), à réserver aux relectures
        ponctuelles. La synchro courante passe par `lire_lot`."""
        if self._client_reel is None:
            return parser_transactions(self._payload, dossier_id, since, until)
        raise ContactNonMappeError(
            "fetch_transactions ne connaît pas le contact Digifactory : "
            "utiliser lire_lot(dossier, curseur)"
        )

    async def lire_lot(self, dossier: Dossier, depuis_maj: datetime | None) -> LotTransactions:
        """Lecture incrémentale d'un dossier réel (doc 16 §5, §9 points 2 et 5) :
        le `contact_nr` vient du dossier (`dossiers.contact_nr`), `depuis_maj`
        est le curseur `updated_at` de la synchro précédente. Le recouvrement
        (la borne est inclusive côté fournisseur, à confirmer) est sans effet :
        la synchro est idempotente."""
        if dossier.contact_nr is None:
            raise ContactNonMappeError(
                f"dossier {dossier.id} sans contact Digifactory (dossiers.contact_nr)"
            )
        if self._client_reel is None:
            lot = parser_lot(self._payload, dossier.id)
            if depuis_maj is None:
                return lot
            return _filtrer_depuis(lot, depuis_maj)
        if depuis_maj is not None:
            payload = await self._client_reel.transactions(dossier.contact_nr, since=depuis_maj)
            return parser_lot(payload, dossier.id)
        lots: list[LotTransactions] = []
        for debut, fin in fenetres_mensuelles(dossier.exercice_debut, date.today()):
            payload = await self._client_reel.transactions(dossier.contact_nr, debut=debut, fin=fin)
            lots.append(parser_lot(payload, dossier.id))
        return fusionner_lots(tuple(lots))

    async def fetch_platform_settlements(
        self, tenant_id: TenantId, dossier_id: DossierId, since: date, until: date
    ) -> list[PlatformSettlement]:
        return []  # Digifactory ne fournit pas de settlements plateforme (doc 13 §1)

    async def health(self) -> ProviderHealth:
        if self._client_reel is None:
            return ProviderHealth(
                ok=False, message="chemin B (fixtures) actif — aucun DigifactoryHttpClient fourni"
            )
        try:
            await self._client_reel.categories()
        except DigifactoryAuthError as erreur:
            return ProviderHealth(ok=False, message=str(erreur))
        except httpx.HTTPError as erreur:
            return ProviderHealth(ok=False, message=f"erreur réseau/HTTP : {erreur}")
        return ProviderHealth(
            ok=True, message="X_DIGI_TOKEN valide (doc 16 §7, débloqué 2026-09-11)"
        )
