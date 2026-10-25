"""Le seul type qu'un fournisseur LLM accepte."""

from __future__ import annotations

from dataclasses import dataclass

from axelcompta.core.ids import DossierId

from .detecter import affirmer_sans_fuite


@dataclass(frozen=True, slots=True)
class PseudonymizedPrompt:
    """Un prompt déjà passé par `pseudonymiser`. La construction échoue
    si le texte contient encore un identifiant ou une partie connue."""

    dossier_id: DossierId
    texte: str
    secrets: tuple[str, ...]

    def __post_init__(self) -> None:
        affirmer_sans_fuite(self.texte, self.secrets)
