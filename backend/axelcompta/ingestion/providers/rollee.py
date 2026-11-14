"""Rollee : revenus des plateformes (Uber, Bolt…) d'un chauffeur (doc 13 §3,
AXE-818).

**API utilisateur** (AXE-817) : un « user » Rollee par dossier, qui relie
lui-même ses comptes de plateformes dans Rollee Connect (AXE-819). Ce module
lit leurs revenus et les traduit en `PlatformSettlement`, sans écrire en
comptabilité (AXE-821).

Ce que la doc Rollee dit, et ce qu'elle ne dit pas (vérifié le 2026-11-11,
developers.getrollee.com) :

* jeton JWT du tableau de bord, en `Authorization: Bearer`, renouvelé par
  `GET /token/refresh` → `{"token": …}` ; jetons sandbox et production
  distincts ;
* `GET /accounts/{id}/income` donne, **par période** (`time_period_type` :
  daily, weekly, monthly, yearly, custom), `gross_earnings`, `platform_fee`,
  `other_fees`, `net_amount`, `payouts` (un total, pas la liste des
  virements), `currency` ;
* l'unité des montants n'est pas documentée. On lit des euros décimaux
  (`UNITE_MONTANTS`) ; le test de contrat contre le sandbox
  (`ROLLEE_JETON_SANDBOX`) le confirme ou le fera échouer ;
* la date du virement n'est pas donnée : on prend la fin de la période,
  la réconciliation cherche le virement de -3 à +5 jours autour.

Sans client (`RolleeProvider()`), le provider rend la fixture du golden test
doc 17 §7, comme avant : les démos et les tests ne changent pas.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import time as temps
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.packs.vtc_demo import Plateforme, plateforme_de

from .base import DataProvider, NormalizedTransaction, PlatformSettlement, ProviderHealth

_journal = logging.getLogger("uvicorn.error")

SOURCE = "rollee"
URLS = {
    "sandbox": "https://api.sand.getrollee.com/api/v0.5",
    "production": "https://api.getrollee.com/api/v0.5",
}
UNITE_MONTANTS = "euros"  # à confirmer sur le sandbox (AXE-817)
# Un passage sur tous les users Rollee touche la limite de débit (AXE-917) ;
# 1, 2, 4 puis 8 s d'attente avant d'abandonner.
ESSAIS = 5
ATTENTE_MAX_S = 30.0

SurNouveauJeton = Callable[[str], None]


class RolleeAuthError(RuntimeError):
    """401 même après renouvellement du jeton : jeton révoqué ou mauvais
    environnement (un jeton sandbox sur la production, par exemple)."""


class RolleeIndisponible(RuntimeError):
    """429 ou 5xx après tous les essais."""

    def __init__(self, message: str, statut: int | None = None) -> None:
        super().__init__(message)
        self.statut = statut


class RevenuIllisible(ValueError):
    """Une période de revenus qu'on ne sait pas comptabiliser telle quelle.
    Le message dit pourquoi ; la ligne part en quarantaine, jamais arrondie."""


def _debut_unix(jour: date) -> int:
    return int(datetime.combine(jour, time.min, tzinfo=UTC).timestamp())


def _fin_unix(jour: date) -> int:
    return int(datetime.combine(jour, time.max, tzinfo=UTC).timestamp())


def premiere_fiche(reponse: object) -> dict[str, Any]:
    """AXE-917 : Rollee enveloppe le profil et les coordonnées bancaires d'un
    compte (`{account_id, connected, data, user_id}`), `data` étant une liste
    de fiches, parfois vide (Bolt sans IBAN). Rend la première fiche, ou la
    réponse elle-même si elle n'a pas d'enveloppe."""
    if not isinstance(reponse, dict):
        return {}
    if "data" not in reponse:
        return reponse
    donnees = reponse["data"]
    if isinstance(donnees, list):
        return next((d for d in donnees if isinstance(d, dict)), {})
    return donnees if isinstance(donnees, dict) else {}


class RolleeHttpClient:
    """Vrais appels à l'API utilisateur Rollee. N'appelle rien à la
    construction. `sur_nouveau_jeton` reçoit le jeton renouvelé, pour que le
    branchement le garde (sinon le prochain lancement repartirait de l'ancien)."""

    def __init__(
        self,
        environnement: str,
        jeton: str,
        *,
        client: httpx.AsyncClient | None = None,
        sur_nouveau_jeton: SurNouveauJeton | None = None,
        attendre: Callable[[float], Awaitable[None]] = asyncio.sleep,
        timeout: float = 30.0,
    ) -> None:
        if environnement not in URLS:
            raise ValueError(f"environnement Rollee inconnu : {environnement}")
        self.environnement = environnement
        self._jeton = jeton
        self._client = client or httpx.AsyncClient(base_url=URLS[environnement], timeout=timeout)
        self._sur_nouveau_jeton = sur_nouveau_jeton
        self._attendre = attendre
        # AXE-917 : des appels en parallèle peuvent prendre un 401 ensemble ;
        # un seul renouvelle, les autres reprennent le nouveau jeton.
        self._verrou_jeton = asyncio.Lock()

    @classmethod
    def depuis_parametres(
        cls, parametres: dict[str, str], sur_nouveau_jeton: SurNouveauJeton | None = None
    ) -> RolleeHttpClient:
        """Un branchement Rollee du portefeuille (AXE-872)."""
        return cls(
            parametres["environnement"], parametres["jeton"], sur_nouveau_jeton=sur_nouveau_jeton
        )

    async def _une_requete(self, methode: str, chemin: str, **options: Any) -> httpx.Response:
        en_tetes = {"Authorization": f"Bearer {self._jeton}", "accept": "application/json"}
        for essai in range(ESSAIS):
            debut = temps.monotonic()
            reponse = await self._client.request(methode, chemin, headers=en_tetes, **options)
            duree = temps.monotonic() - debut
            if reponse.status_code == 429 or duree >= 5:
                _journal.info(
                    "Rollee %s %s → %s en %.1fs (essai %s)",
                    methode,
                    chemin,
                    reponse.status_code,
                    duree,
                    essai + 1,
                )
            if reponse.status_code != 429 and reponse.status_code < 500:
                return reponse
            if essai < ESSAIS - 1:
                await self._attendre(_attente(reponse, essai))
        raise RolleeIndisponible(
            f"{methode} {chemin} : {reponse.status_code} après {ESSAIS} essais",
            reponse.status_code,
        )

    async def _requete(self, methode: str, chemin: str, **options: Any) -> Any:
        """Un 401 renouvelle le jeton une fois, puis réessaie."""
        jeton_utilise = self._jeton
        reponse = await self._une_requete(methode, chemin, **options)
        if reponse.status_code == 401:
            async with self._verrou_jeton:
                if self._jeton == jeton_utilise:
                    await self.renouveler()
            reponse = await self._une_requete(methode, chemin, **options)
            if reponse.status_code == 401:
                raise RolleeAuthError(f"401 sur {chemin} : jeton refusé ({self.environnement})")
        reponse.raise_for_status()
        return reponse.json() if reponse.content else None

    async def renouveler(self) -> str:
        reponse = await self._une_requete("GET", "/token/refresh")
        if reponse.status_code == 401:
            raise RolleeAuthError(f"jeton refusé au renouvellement ({self.environnement})")
        reponse.raise_for_status()
        jeton = str(reponse.json()["token"])
        self._jeton = jeton
        if self._sur_nouveau_jeton is not None:
            self._sur_nouveau_jeton(jeton)
        return jeton

    async def creer_utilisateur(self, metadonnees: dict[str, str]) -> dict[str, Any]:
        """`POST /users` : `id`, `link`, `session`, `session_expires_at`…"""
        resultat: dict[str, Any] = await self._requete(
            "POST", "/users", json={"metadata": metadonnees}
        )
        return resultat

    async def nouvelle_session(self, user_id: str) -> dict[str, Any]:
        """`POST /users/{id}/sessions/new` : `link`, `session`, `session_expires_at`."""
        resultat: dict[str, Any] = await self._requete("POST", f"/users/{user_id}/sessions/new")
        return resultat

    async def comptes(self, user_id: str) -> list[dict[str, Any]]:
        """`GET /users/{id}/accounts` : `id`, `name`, `connected`, `reconnecting`…"""
        resultat: list[dict[str, Any]] = await self._requete("GET", f"/users/{user_id}/accounts")
        return resultat

    async def utilisateurs(self, limite_pages: int = 200) -> list[dict[str, Any]]:
        """`GET /users`, toutes les pages (`next_page_link`) : `id`, `metadata`…
        AXE-911 : lecture seule, pour relier les users existants aux dossiers."""
        tous: list[dict[str, Any]] = []
        chemin: str | None = "/users"
        for _page in range(limite_pages):
            if chemin is None:
                break
            reponse = await self._requete("GET", chemin)
            if isinstance(reponse, list):
                return tous + [u for u in reponse if isinstance(u, dict)]
            page = reponse or {}
            donnees = page.get("data") or page.get("users") or page.get("results") or []
            tous += [u for u in donnees if isinstance(u, dict)]
            suivant = page.get("next_page_link")
            chemin = str(suivant) if suivant else None
        return tous

    async def profil(self, account_id: str) -> dict[str, Any]:
        """`GET /accounts/{id}/profile`, déballé : `first_name`, `last_name`,
        `full_name`, `email`, `phone`… Lu pour comparer (AXE-911, AXE-917)."""
        return premiere_fiche(await self._requete("GET", f"/accounts/{account_id}/profile"))

    async def coordonnees_bancaires(self, account_id: str) -> dict[str, Any]:
        """`GET /accounts/{id}/banking_info`, déballé : `iban`, `recipient`,
        `swift`. Vide pour Bolt ; Uber répond 400 (levé). AXE-911, AXE-917."""
        return premiere_fiche(await self._requete("GET", f"/accounts/{account_id}/banking_info"))

    async def revenus(self, account_id: str, depuis: date, jusqua: date) -> dict[str, Any]:
        """`GET /accounts/{id}/income` sur la période, bornes comprises."""
        resultat: dict[str, Any] = await self._requete(
            "GET",
            f"/accounts/{account_id}/income",
            params={"start_date": _debut_unix(depuis), "end_date": _fin_unix(jusqua)},
        )
        return resultat

    async def configurer_webhook(self, type_: str, url: str, secret: str) -> None:
        """`PUT /webhooks/{type}` (AXE-820). Un PUT remplace toute la
        configuration de ce type : tous les champs sont envoyés."""
        await self._requete(
            "PUT",
            f"/webhooks/{type_}",
            json={"url": url, "method": "POST", "enabled": True, "secret": secret, "headers": {}},
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _attente(reponse: httpx.Response, essai: int) -> float:
    """`Retry-After` s'il est lisible, sinon 1 s, 2 s, 4 s… plafonné."""
    try:
        return min(float(reponse.headers.get("Retry-After", "")), ATTENTE_MAX_S)
    except ValueError:
        return min(float(2**essai), ATTENTE_MAX_S)


def centimes(valeur: object, champ: str) -> int:
    """Euros décimaux → centimes, sans arrondi : une troisième décimale est
    une erreur, pas un arrondi silencieux."""
    if valeur is None:
        return 0
    try:
        montant = Decimal(str(valeur))
    except InvalidOperation as exc:
        raise RevenuIllisible(f"{champ} illisible : {valeur!r}") from exc
    en_centimes = montant * 100
    if en_centimes != en_centimes.to_integral_value():
        raise RevenuIllisible(f"{champ} a plus de deux décimales : {valeur!r}")
    return int(en_centimes)


def fin_de_periode(debut: date, type_periode: str) -> date:
    if type_periode == "daily":
        return debut
    if type_periode == "weekly":
        return debut + timedelta(days=6)
    if type_periode == "monthly":
        return debut.replace(day=calendar.monthrange(debut.year, debut.month)[1])
    if type_periode == "yearly":
        return date(debut.year, 12, 31)
    raise RevenuIllisible(f"période « {type_periode} » sans fin connue")


@dataclass(frozen=True, slots=True)
class CompteRollee:
    """Un compte de plateforme relié par le chauffeur dans Rollee."""

    account_id: str
    nom: str  # « Uber », « Bolt »… tel que Rollee le nomme
    connecte: bool = True


def settlement_depuis_revenu(
    dossier_id: DossierId, plateforme: Plateforme, revenu: dict[str, Any]
) -> PlatformSettlement:
    """Une période de revenus → un `PlatformSettlement`. Lève
    `RevenuIllisible` si la période ne tient pas : brut − frais doit égaler
    le versement au centime (des pourboires ou du cash hors versement
    feraient un écart qu'on ne comptabilise pas à l'aveugle)."""
    if str(revenu.get("currency", "")).upper() != "EUR":
        raise RevenuIllisible(f"devise {revenu.get('currency')!r} : seul l'euro est pris en charge")
    try:
        debut = date.fromisoformat(str(revenu["time_period_start_date"]))
    except (KeyError, ValueError) as exc:
        raise RevenuIllisible("début de période illisible") from exc
    fin = fin_de_periode(debut, str(revenu.get("time_period_type", "")))
    brut = centimes(revenu.get("gross_earnings"), "gross_earnings")
    frais = centimes(revenu.get("platform_fee"), "platform_fee") + centimes(
        revenu.get("other_fees"), "other_fees"
    )
    verse = centimes(revenu.get("payouts"), "payouts")
    if brut - frais != verse:
        raise RevenuIllisible(
            f"brut {brut} − frais {frais} ≠ versé {verse} (centimes) : écart à revoir"
        )
    return PlatformSettlement(
        dossier_id=dossier_id,
        platform=plateforme.nom,
        period_start=debut,
        period_end=fin,
        payout_date=fin,
        gross_earnings_cts=brut,
        commission_cts=frais,
        commission_tva_regime=plateforme.commission_tva_regime,
        net_payout_cts=verse,
        currency="EUR",
        source_provider=SOURCE,
        raw_payload=dict(revenu),
    )


@dataclass(frozen=True, slots=True)
class Rejet:
    """Une période lue mais pas comptabilisable : en quarantaine (AXE-424)."""

    account_id: str
    motif: str
    payload: dict[str, Any]


@dataclass
class Releve:
    """Ce qu'une lecture rapporte : les settlements, et ce qui a été écarté."""

    settlements: list[PlatformSettlement] = field(default_factory=list)
    rejets: list[Rejet] = field(default_factory=list)


def lire_revenus(
    dossier_id: DossierId,
    compte: CompteRollee,
    reponse: dict[str, Any],
    plateformes: tuple[Plateforme, ...],
) -> Releve:
    releve = Releve()
    plateforme = plateforme_de(compte.nom, plateformes)
    for revenu in reponse.get("data") or []:
        if plateforme is None:
            motif = f"plateforme « {compte.nom} » absente du pack (plateformes.csv)"
            releve.rejets.append(Rejet(compte.account_id, motif, revenu))
            continue
        try:
            releve.settlements.append(settlement_depuis_revenu(dossier_id, plateforme, revenu))
        except RevenuIllisible as exc:
            releve.rejets.append(Rejet(compte.account_id, str(exc), revenu))
    return releve


class RolleeProvider(DataProvider):
    """doc 13 §3. Avec un client : les revenus des comptes reliés du
    dossier (`comptes_du_dossier`). Sans client : la fixture du golden test
    doc 17 §7, ou les `settlements` injectés."""

    def __init__(
        self,
        settlements: tuple[PlatformSettlement, ...] | None = None,
        *,
        client: RolleeHttpClient | None = None,
        comptes_du_dossier: Callable[[DossierId], Sequence[CompteRollee]] | None = None,
        plateformes: tuple[Plateforme, ...] = (),
    ) -> None:
        self._settlements = settlements
        self._client = client
        self._comptes = comptes_du_dossier
        self._plateformes = plateformes

    async def fetch_transactions(
        self, tenant_id: TenantId, dossier_id: DossierId, since: date, until: date
    ) -> list[NormalizedTransaction]:
        return []  # Rollee ne fournit pas de transactions bancaires (doc 13 §1)

    async def releve(self, dossier_id: DossierId, since: date, until: date) -> Releve:
        """Revenus de chaque compte relié et connecté du dossier."""
        if self._client is None or self._comptes is None:
            settlements = self._settlements or _fixture_par_defaut(dossier_id)
            return Releve([s for s in settlements if since <= s.payout_date <= until])
        total = Releve()
        for compte in self._comptes(dossier_id):
            if not compte.connecte:
                continue
            reponse = await self._client.revenus(compte.account_id, since, until)
            lu = lire_revenus(dossier_id, compte, reponse, self._plateformes)
            total.settlements.extend(lu.settlements)
            total.rejets.extend(lu.rejets)
        return total

    async def fetch_platform_settlements(
        self, tenant_id: TenantId, dossier_id: DossierId, since: date, until: date
    ) -> list[PlatformSettlement]:
        return (await self.releve(dossier_id, since, until)).settlements

    async def health(self) -> ProviderHealth:
        if self._client is None:
            return ProviderHealth(
                ok=False, message="aucun branchement Rollee — chemin B (fixtures) actif"
            )
        try:
            await self._client.renouveler()
        except (RolleeAuthError, RolleeIndisponible, httpx.HTTPError) as exc:
            return ProviderHealth(ok=False, message=f"{type(exc).__name__} : {exc}")
        return ProviderHealth(
            ok=True, message=f"jeton Rollee accepté ({self._client.environnement})"
        )


def _fixture_par_defaut(dossier_id: DossierId) -> tuple[PlatformSettlement, ...]:
    return (
        PlatformSettlement(
            dossier_id=dossier_id,
            platform="uber",
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            payout_date=date(2026, 9, 2),
            gross_earnings_cts=1_040_00,
            commission_cts=192_00,
            commission_tva_regime="france_20",
            net_payout_cts=848_00,
            currency="EUR",
            source_provider=SOURCE,
            raw_payload={},
        ),
    )
