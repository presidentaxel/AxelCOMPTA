"""Claude derrière `LLMProvider` (AXE-888, AXE-887).

N'accepte qu'un `PseudonymizedPrompt`. Chaque appel est journalisé avant de
partir, et son coût est compté : au-delà du plafond, plus aucun appel.

La clé vient de l'environnement (`ANTHROPIC_API_KEY`), jamais du code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

from .llm import JournalPrompts
from .prompt import PseudonymizedPrompt

MODELE_PAR_DEFAUT = "claude-fable-5-2"
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


def _client_reel() -> ClientMessages:
    """Le client officiel, importé seulement quand on appelle vraiment."""
    import anthropic

    client: Any = anthropic.Anthropic(max_retries=2).beta.messages
    return cast(ClientMessages, client)


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
        entree, sortie = _jetons_entree(reponse.usage), int(reponse.usage.output_tokens)
        self.consommations.append(Consommation(entree, sortie, cout(self._modele, entree, sortie)))
        if reponse.stop_reason in ("refusal", "max_tokens"):
            raise ReponseInutilisable(f"Réponse inutilisable ({reponse.stop_reason}).")
        return str(next(b.text for b in reponse.content if b.type == "text"))
