"""L'avis de chaque étage sur une opération à trancher (AXE-901).

Pur. Au moment de la décision, on garde ce que chaque étage disait, même
quand ce n'est pas lui qui était affiché : de quoi savoir, plus tard, si la
règle, le modèle ou l'IA avaient vu juste, et choisir les seuils sur des
décisions réelles. Rien n'est recalculé : la proposition de la synchro est
celle enregistrée, l'IA est celle déjà en base.

La proposition « affichée » suit l'ordre de la file à trancher : une règle,
puis l'IA, puis le modèle ou la banque. Une opération semblable déjà
tranchée passe avant tout à l'écran ; elle n'est pas reprise ici, faute de
relire tout le dossier à chaque décision.
"""

from __future__ import annotations

from typing import Any

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.rules_and_ml import CATEGORIE_PAR_DEFAUT

from .propositions_ia import PropositionIa

AVIS_SYNCHRO = "synchro"
AVIS_IA = "ia"


def avis_etages(proposition: ProposedEntry, ia: PropositionIa | None) -> dict[str, dict[str, Any]]:
    avis: dict[str, dict[str, Any]] = {
        AVIS_SYNCHRO: {
            "etage": proposition.etage.name,
            "categorie": proposition.categorie,
            "confiance": proposition.confiance,
        }
    }
    if ia is not None:
        avis[AVIS_IA] = {
            "categorie": ia.categorie,
            "confiance": ia.confiance,
            "justification": ia.justification,
            "modele": ia.modele,
            "version": ia.version,
        }
    return avis


def proposition_affichee(
    proposition: ProposedEntry, ia: PropositionIa | None
) -> tuple[str | None, str | None, float | None]:
    """(catégorie, étage, confiance) de ce que la file montrait."""
    utile = proposition.categorie != CATEGORIE_PAR_DEFAUT
    if utile and proposition.etage is Etage.REGLE:
        return proposition.categorie, proposition.etage.name, proposition.confiance
    if ia is not None and ia.proposable:
        return ia.categorie, Etage.LLM.name, ia.confiance
    return proposition.categorie, proposition.etage.name, proposition.confiance
