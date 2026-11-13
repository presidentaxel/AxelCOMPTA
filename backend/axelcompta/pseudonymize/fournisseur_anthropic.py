"""Claude derrière `LLMProvider` (AXE-888, AXE-887).

N'accepte qu'un `PseudonymizedPrompt`. Chaque appel est journalisé avant de
partir, et son coût est compté : au-delà du plafond, plus aucun appel.

La clé vient de l'environnement (`ANTHROPIC_API_KEY`), jamais du code.
`ANTHROPIC_WORKSPACE_ID` part en en-tête quand la clé n'est pas limitée à un
workspace. `ANTHROPIC_MODEL` choisit le modèle, sinon Claude Fable 5.2.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, cast

from .llm import JournalPrompts
from .prompt import PseudonymizedPrompt

MODELE_PAR_DEFAUT = "claude-fable-5-2"
VARIABLE_MODELE = "ANTHROPIC_MODEL"
VARIABLE_WORKSPACE = "ANTHROPIC_WORKSPACE_ID"
ENTETE_WORKSPACE = "anthropic-workspace-id"
# Dollars par million de jetons (entrée, sortie), prix publics au 12/11/2026.
# Un modèle inconnu est compté au prix de Fable : on surestime, jamais l'inverse.
PRIX_PAR_MODELE = {
    "claude-fable-5-2": (8.0, 40.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.1, 0.5),
}
BETA_REPLI = "server-side-fallback-2026-07-01"


class BudgetDepasse(RuntimeError):
    """Le plafond de dépense de ce lancement est atteint : aucun appel ne part."""


class ReponseInutilisable(RuntimeError):
    """Refus du modèle, ou réponse coupée : l'opération reste à l'humain."""


class WorkspaceRequis(RuntimeError):
    """La clé n'est pas limitée à un workspace et `ANTHROPIC_WORKSPACE_ID` est absent."""


class ClientMessages(Protocol):
    """Ce qu'on utilise du client `anthropic` (remplaçable dans les tests)."""

    def create(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class Consommation:
    entree: int
    sortie: int
    cout_usd: float


def cout(modele: str, jetons_entree: int, jetons_sortie: int) -> float:
    prix_entree, prix_sortie = PRIX_PAR_MODELE.get(modele, PRIX_PAR_MODELE[MODELE_PAR_DEFAUT])
    return (jetons_entree * prix_entree + jetons_sortie * prix_sortie) / 1_000_000


def _jetons_entree(usage: Any) -> int:
    return sum(
        int(getattr(usage, champ, 0) or 0)
        for champ in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )


def modele_configure(explicite: str | None = None) -> str:
    """Le modèle demandé en argument, sinon `ANTHROPIC_MODEL`, sinon Fable."""
    if explicite is not None and explicite.strip():
        return explicite.strip()
    depuis_env = os.environ.get(VARIABLE_MODELE, "").strip()
    return depuis_env or MODELE_PAR_DEFAUT


def entetes_anthropic() -> dict[str, str]:
    """L'en-tête workspace, seulement si `ANTHROPIC_WORKSPACE_ID` est posé."""
    workspace = os.environ.get(VARIABLE_WORKSPACE, "").strip()
    if not workspace:
        return {}
    return {ENTETE_WORKSPACE: workspace}


def _client_reel() -> ClientMessages:
    """Le client officiel, importé seulement quand on appelle vraiment."""
    import anthropic

    parametres: dict[str, Any] = {"max_retries": 2}
    entetes = entetes_anthropic()
    if entetes:
        parametres["default_headers"] = entetes
    client: Any = anthropic.Anthropic(**parametres).beta.messages
    return cast(ClientMessages, client)


def _lever_si_workspace_requis(erreur: Exception) -> None:
    if "not scoped to a workspace" in str(erreur):
        raise WorkspaceRequis(
            "ANTHROPIC_WORKSPACE_ID manquant : cette clé n'est pas limitée à un workspace."
        ) from erreur


class FournisseurAnthropic:
    nom = "anthropic"

    def __init__(
        self,
        schema: dict[str, Any],
        journal: JournalPrompts,
        plafond_usd: float,
        messages: ClientMessages | None = None,
        modele: str = MODELE_PAR_DEFAUT,
        max_tokens: int = 16_000,
    ) -> None:
        self._messages: ClientMessages = messages if messages is not None else _client_reel()
        self._schema = schema
        self._journal = journal
        self._modele = modele
        self._max_tokens = max_tokens
        self.plafond_usd = plafond_usd
        self.consommations: list[Consommation] = []

    @property
    def depense_usd(self) -> float:
        return sum(c.cout_usd for c in self.consommations)

    def completer(self, prompt: PseudonymizedPrompt) -> str:
        if self.depense_usd >= self.plafond_usd:
            raise BudgetDepasse(f"Plafond de {self.plafond_usd:.2f} $ atteint.")
        self._journal.ecrire(prompt, self.nom)
        try:
            reponse = self._messages.create(
                model=self._modele,
                max_tokens=self._max_tokens,
                betas=[BETA_REPLI],
                fallbacks="default",
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": self._schema},
                },
                messages=[{"role": "user", "content": prompt.texte}],
            )
        except Exception as erreur:
            _lever_si_workspace_requis(erreur)
            raise
        entree, sortie = _jetons_entree(reponse.usage), int(reponse.usage.output_tokens)
        self.consommations.append(Consommation(entree, sortie, cout(self._modele, entree, sortie)))
        if reponse.stop_reason in ("refusal", "max_tokens"):
            raise ReponseInutilisable(f"Réponse inutilisable ({reponse.stop_reason}).")
        return str(next(b.text for b in reponse.content if b.type == "text"))


# --- API Batch (AXE-887) : moitié prix, la latence ne compte pas -------------


@dataclass(frozen=True, slots=True)
class RequeteLot:
    """Un lot de libellés d'un dossier : une requête de l'API Batch."""

    custom_id: str
    prompt: PseudonymizedPrompt
    max_tokens: int


@dataclass(frozen=True, slots=True)
class ResultatLot:
    custom_id: str
    statut: str  # termine | echec | refus
    texte: str = ""
    entree: int = 0
    sortie: int = 0
    cache: int = 0  # jetons lus depuis le cache de prompt


class ClientLots(Protocol):
    """Ce qu'on utilise de `client.messages.batches` (remplaçable dans les tests)."""

    def create(self, **kwargs: Any) -> Any: ...

    def retrieve(self, message_batch_id: str) -> Any: ...

    def results(self, message_batch_id: str) -> Any: ...


def _client_lots_reel() -> ClientLots:
    import anthropic

    client: Any = anthropic.Anthropic(max_retries=2).messages.batches
    return cast(ClientLots, client)


def _resultat(brut: Any) -> ResultatLot:
    """Un résultat de l'API Batch. Refus et réponse coupée : `refus`, le
    libellé n'est pas renvoyé. Erreur, annulation, expiration : `echec`."""
    custom_id = str(brut.custom_id)
    if brut.result.type != "succeeded":
        return ResultatLot(custom_id, "echec")
    message = brut.result.message
    usage = message.usage
    jetons = (
        _jetons_entree(usage),
        int(usage.output_tokens),
        int(getattr(usage, "cache_read_input_tokens", 0) or 0),
    )
    if message.stop_reason in ("refusal", "max_tokens"):
        return ResultatLot(custom_id, "refus", "", *jetons)
    texte = next((b.text for b in message.content if b.type == "text"), "")
    return ResultatLot(custom_id, "termine", str(texte), *jetons)


class FournisseurLotsAnthropic:
    """Soumet des lots à l'API Batch, puis les relève à un passage suivant.

    `systeme` (consignes et taxonomie) ne contient aucune donnée du dossier :
    il est marqué pour le cache de prompt. Chaque prompt pseudonymisé est
    journalisé et revérifié avant de partir."""

    nom = "anthropic-batch"

    def __init__(
        self,
        schema: dict[str, Any],
        systeme: str,
        journal: JournalPrompts,
        lots: ClientLots | None = None,
        modele: str = MODELE_PAR_DEFAUT,
    ) -> None:
        self._lots: ClientLots = lots if lots is not None else _client_lots_reel()
        self._schema = schema
        self._systeme = systeme
        self._journal = journal
        self.modele = modele

    @property
    def taille_systeme(self) -> int:
        return len(self._systeme)

    def _params(self, requete: RequeteLot) -> dict[str, Any]:
        return {
            "model": self.modele,
            "max_tokens": requete.max_tokens,
            "system": [
                {"type": "text", "text": self._systeme, "cache_control": {"type": "ephemeral"}}
            ],
            "output_config": {
                "effort": "low",
                "format": {"type": "json_schema", "schema": self._schema},
            },
            "messages": [{"role": "user", "content": requete.prompt.texte}],
        }

    def soumettre(self, requetes: list[RequeteLot]) -> str:
        """L'identifiant du lot Anthropic."""
        for requete in requetes:
            self._journal.ecrire(requete.prompt, self.nom)
        lot = self._lots.create(
            requests=[{"custom_id": r.custom_id, "params": self._params(r)} for r in requetes]
        )
        return str(lot.id)

    def relever(self, batch_id: str) -> list[ResultatLot] | None:
        """None tant que le lot n'est pas fini."""
        if self._lots.retrieve(batch_id).processing_status != "ended":
            return None
        return [_resultat(brut) for brut in self._lots.results(batch_id)]
