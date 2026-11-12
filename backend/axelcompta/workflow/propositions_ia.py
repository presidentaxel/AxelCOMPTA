"""Propositions de l'IA, gardées par libellé normalisé (AXE-888, AXE-887).

Un libellé déjà envoyé ne repart jamais : sa réponse est relue ici, même
« à vérifier ». Une proposition IA ne fait que proposer ; l'écriture reste au
compte d'attente jusqu'à la décision d'un humain.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from axelcompta.categorize.llm import (
    CATEGORIE_A_VERIFIER,
    DemandeIa,
    cle_libelle,
    lire_reponse,
    texte_demande,
)
from axelcompta.core.ids import DossierId
from axelcompta.pseudonymize.llm import LLMProvider
from axelcompta.pseudonymize.service import Correspondance, PartieConnue, pseudonymiser
from axelcompta.tenants.models import Dossier

TAILLE_LOT = 80  # libellés par appel : une réponse courte, jamais coupée


@dataclass(frozen=True, slots=True)
class PropositionIa:
    dossier_id: DossierId
    cle: str
    version: str
    categorie: str
    confiance: float
    justification: str
    modele: str
    cree_le: datetime

    @property
    def proposable(self) -> bool:
        return self.categorie != CATEGORIE_A_VERIFIER


class PropositionsIa(Protocol):
    def lister(self, dossier_id: DossierId, version: str) -> dict[str, PropositionIa]: ...

    def enregistrer(self, propositions: Sequence[PropositionIa]) -> None: ...


class PropositionsIaMemoire:
    def __init__(self) -> None:
        self._par_cle: dict[tuple[DossierId, str, str], PropositionIa] = {}

    def lister(self, dossier_id: DossierId, version: str) -> dict[str, PropositionIa]:
        return {
            cle: p for (d, cle, v), p in self._par_cle.items() if d == dossier_id and v == version
        }

    def enregistrer(self, propositions: Sequence[PropositionIa]) -> None:
        for p in propositions:
            self._par_cle.setdefault((p.dossier_id, p.cle, p.version), p)


def demandes_a_envoyer(
    operations: Iterable[tuple[str, int, str | None]], deja: Iterable[str]
) -> list[DemandeIa]:
    """`operations` : (libellé, montant, type d'opération) des opérations à
    trancher. Une demande par libellé normalisé encore inconnu."""
    vues = set(deja)
    demandes: list[DemandeIa] = []
    for libelle, montant_cts, type_operation in operations:
        cle = cle_libelle(libelle)
        if not cle or cle in vues:
            continue
        vues.add(cle)
        demandes.append(DemandeIa(cle, libelle, montant_cts, type_operation))
    return demandes


def parties_du_dossier(dossier: Dossier) -> tuple[PartieConnue, ...]:
    """Ce que le modèle ne doit jamais lire en clair : la société et ses associés."""
    parties = [PartieConnue(dossier.nom, "societe")]
    if dossier.identite is not None:
        parties.append(PartieConnue(dossier.identite.denomination, "societe"))
        for associe in dossier.identite.associes:
            parties.append(PartieConnue(associe.nom, "personne"))
            parties.append(PartieConnue(f"{associe.prenoms} {associe.nom}", "personne"))
    return tuple(parties)


def proposer(
    dossier: Dossier,
    demandes: Sequence[DemandeIa],
    fournisseur: LLMProvider,
    categories: Sequence[str],
    contexte: tuple[str, str, datetime],
) -> list[PropositionIa]:
    """Un appel pour un lot. `contexte` : (modèle, version du prompt, date).
    Le texte est pseudonymisé avant de partir ; `pseudonymiser` refuse de
    construire le prompt s'il reste une partie connue."""
    modele, version, maintenant = contexte
    texte = texte_demande(demandes, categories)
    prompt = pseudonymiser(dossier.id, texte, parties_du_dossier(dossier), Correspondance())
    reponses = lire_reponse(fournisseur.completer(prompt), demandes, categories)
    return [
        PropositionIa(
            dossier.id,
            r.cle,
            version,
            r.categorie,
            r.confiance,
            r.justification,
            modele,
            maintenant,
        )
        for r in reponses
    ]


def par_lots(demandes: Sequence[DemandeIa], taille: int = TAILLE_LOT) -> list[list[DemandeIa]]:
    return [list(demandes[i : i + taille]) for i in range(0, len(demandes), taille)]


# Catégories du pack qu'un humain ne choisit pas sur une opération bancaire.
_HORS_PROPOSITION = frozenset(
    {
        "operation_capital_hors_perimetre",
        "a_verifier_location_materiel",
        "ecarts_reglement_arrondis",
        "dotations_amortissements",
        "dividendes_associes",
    }
)


def categories_proposables(comptes_pack: Iterable[str]) -> list[str]:
    """La taxonomie montrée au modèle : les catégories du pack qu'une décision
    accepte, l'usage personnel, et « à vérifier » pour s'abstenir."""
    retenues = sorted(set(comptes_pack) - _HORS_PROPOSITION)
    return [*retenues, "usage_personnel", CATEGORIE_A_VERIFIER]
