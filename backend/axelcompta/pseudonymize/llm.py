"""Fournisseurs interchangeables. Ils n'acceptent qu'un prompt déjà pseudonymisé."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .detecter import affirmer_sans_fuite
from .prompt import PseudonymizedPrompt


@dataclass(frozen=True, slots=True)
class EntreeJournal:
    """Ce qui part vraiment : le texte pseudonymisé, jamais la table de correspondance."""

    dossier_id: str
    fournisseur: str
    prompt: str


class JournalPrompts:
    def __init__(self) -> None:
        self.entrees: list[EntreeJournal] = []

    def ecrire(self, prompt: PseudonymizedPrompt, fournisseur: str) -> None:
        affirmer_sans_fuite(prompt.texte, prompt.secrets)
        self.entrees.append(
            EntreeJournal(
                dossier_id=str(prompt.dossier_id), fournisseur=fournisseur, prompt=prompt.texte
            )
        )


class LLMProvider(Protocol):
    nom: str

    def completer(self, prompt: PseudonymizedPrompt) -> str:
        """Réponse JSON contrainte. `prompt` est le seul argument texte admis."""


class FournisseurMemoire:
    """Aucun appel réseau. Sert les tests et le câblage tant qu'aucun
    fournisseur réel n'est branché."""

    def __init__(self, journal: JournalPrompts, nom: str = "memoire") -> None:
        self.nom = nom
        self._journal = journal

    def completer(self, prompt: PseudonymizedPrompt) -> str:
        self._journal.ecrire(prompt, self.nom)
        return '{"categorie": null, "confiance": 0, "justification_courte": ""}'
