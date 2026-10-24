"""Faits que les détecteurs lisent, et alertes qu'ils rendent (doc 05 §6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from axelcompta.core.ids import DossierId, EcritureId


@dataclass(frozen=True, slots=True)
class MouvementSurveille:
    """Une dépense déjà catégorisée. `montant_centimes` est signé :
    négatif = sortie. `nature_ticket` vaut ``courses`` ou ``carburant``
    quand le ticket a été lu, sinon None."""

    dossier_id: DossierId
    ecriture_id: EcritureId
    date: date
    libelle: str
    montant_centimes: int
    categorie: str
    justificatif_id: str | None = None
    nature_ticket: str | None = None


@dataclass(frozen=True, slots=True)
class Alerte:
    """Signal à qualifier par un humain. `libelle_ui` n'est jamais une
    qualification juridique (doc 05 §6.1)."""

    id: str
    dossier_id: DossierId
    ecriture_id: EcritureId
    code: str
    libelle_ui: str
    detail: str
    libelle_mouvement: str
    montant_centimes: int
    date: date
