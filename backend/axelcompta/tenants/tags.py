"""Tags d'entreprises et exclusion des traitements (AXE-829).

Le portefeuille de Serenity contient des sociétés qui ne sont pas des
chauffeurs (ses propres sociétés, une personne de chez Bolt). Un tag les
range ; un réglage par portefeuille dit, traitement par traitement, quels
tags en excluent un dossier. Un dossier exclu n'est jamais supprimé : ses
données restent, l'exclusion se lève en retirant le tag ou en changeant le
réglage.

Pur ici : les dépôts sont dans `tags_memoire.py` et `tags_postgres.py`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId, TenantId, UserId

from .models import Dossier
from .sirene import CODES_NAF_CHAUFFEUR

TAG_CHAUFFEUR = "chauffeur"
TAG_SOCIETE_DU_GESTIONNAIRE = "societe_du_gestionnaire"
TAG_HORS_PERIMETRE = "hors_perimetre"
TAG_TEST = "test"

# Proposés à chaque portefeuille ; le gestionnaire en crée d'autres.
TAGS_PROPOSES: Mapping[str, str] = {
    TAG_CHAUFFEUR: "Chauffeur VTC ou taxi",
    TAG_SOCIETE_DU_GESTIONNAIRE: "Société du gestionnaire, pas un client",
    TAG_HORS_PERIMETRE: "Contact sans dossier comptable à tenir",
    TAG_TEST: "Dossier de test",
}

# Traitements qu'un tag peut faire sauter, avec leur nom à l'écran.
TRAITEMENTS: Mapping[str, str] = {
    "synchro": "Synchronisation bancaire",
    "categorisation": "Classement automatique des opérations",
    "expert": "File du mode expert",
    "anomalies": "Détection d'anomalies",
    "rappels": "Rappels et notifications",
    "compteurs": "Compteurs et filtres d'Entreprises",
}

# Sans réglage enregistré : les sociétés du gestionnaire, les contacts hors
# périmètre et les dossiers de test sont exclus de tout. Ils restent visibles
# dans la liste Entreprises, grisés.
EXCLUSIONS_PAR_DEFAUT: Mapping[str, frozenset[str]] = {
    traitement: frozenset({TAG_SOCIETE_DU_GESTIONNAIRE, TAG_HORS_PERIMETRE, TAG_TEST})
    for traitement in TRAITEMENTS
}

_NOM_VALIDE = re.compile(r"^[a-z0-9][a-z0-9_]{1,39}$")


class TagInvalide(DomaineError):
    """Nom de tag ou traitement inconnu, ou tag absent du portefeuille."""


@dataclass(frozen=True, slots=True)
class Tag:
    tenant_id: TenantId
    nom: str
    description: str


@dataclass(frozen=True, slots=True)
class EtatTags:
    """Ce qu'il faut pour décider d'une exclusion dans un portefeuille."""

    par_dossier: Mapping[DossierId, frozenset[str]]
    exclusions: Mapping[str, frozenset[str]]

    def tags_de(self, dossier_id: DossierId) -> frozenset[str]:
        return self.par_dossier.get(dossier_id, frozenset())

    def exclu(self, dossier_id: DossierId, traitement: str) -> bool:
        return est_exclu(self.tags_de(dossier_id), self.exclusions, traitement)


def nom_de_tag(brut: str) -> str:
    """Minuscules, chiffres et `_`, 2 à 40 caractères ; les espaces deviennent
    des `_`. Lève `TagInvalide` sinon."""
    nom = re.sub(r"\s+", "_", brut.strip().lower())
    if not _NOM_VALIDE.match(nom):
        raise TagInvalide("Un tag s'écrit en minuscules, chiffres et « _ », de 2 à 40 caractères.")
    return nom


def verifier_traitement(traitement: str) -> str:
    if traitement not in TRAITEMENTS:
        raise TagInvalide(f"Traitement inconnu : {traitement}.")
    return traitement


def est_exclu(
    tags_du_dossier: Iterable[str], exclusions: Mapping[str, frozenset[str]], traitement: str
) -> bool:
    """Un dossier est exclu d'un traitement si l'un de ses tags y est exclu."""
    exclus = exclusions.get(verifier_traitement(traitement), frozenset())
    return any(tag in exclus for tag in tags_du_dossier)


def exclusions_completes(enregistrees: Mapping[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """Le réglage enregistré d'un traitement l'emporte ; un traitement jamais
    réglé suit `EXCLUSIONS_PAR_DEFAUT`."""
    return {
        traitement: enregistrees.get(traitement, EXCLUSIONS_PAR_DEFAUT[traitement])
        for traitement in TRAITEMENTS
    }


def tag_depuis_naf(code_naf: str | None) -> str | None:
    """`chauffeur` pour une activité de transport de personnes (AXE-834)."""
    return TAG_CHAUFFEUR if code_naf in CODES_NAF_CHAUFFEUR else None


# Auteur des tags posés par l'import (pas un utilisateur).
POSE_PAR_IMPORT = UserId("import-sirene")


def a_taguer_chauffeur(dossiers: Sequence[Dossier]) -> tuple[DossierId, ...]:
    """Dossiers dont l'activité Sirene est du transport de personnes. Un
    autre NAF ne reçoit aucun tag : le gestionnaire tranche."""
    return tuple(d.id for d in dossiers if tag_depuis_naf(d.code_naf) == TAG_CHAUFFEUR)


class TagsRepository(Protocol):
    def lister_tags(self, tenant_id: TenantId) -> tuple[Tag, ...]:
        """Les tags du portefeuille, proposés compris (créés au besoin)."""
        ...

    def creer_tag(self, tag: Tag) -> None:
        """Sans effet si le tag existe déjà."""
        ...

    def tags_des_dossiers(self, tenant_id: TenantId) -> dict[DossierId, frozenset[str]]: ...

    def poser(
        self, tenant_id: TenantId, dossier_id: DossierId, tag: str, par: UserId, le: datetime
    ) -> None:
        """Lève `TagInvalide` si le tag n'existe pas dans le portefeuille.
        Sans effet si le dossier le porte déjà."""
        ...

    def retirer(
        self, tenant_id: TenantId, dossier_id: DossierId, tag: str, par: UserId, le: datetime
    ) -> None: ...

    def exclusions(self, tenant_id: TenantId) -> dict[str, frozenset[str]]:
        """Réglage en vigueur, complété par `EXCLUSIONS_PAR_DEFAUT`."""
        ...

    def regler_exclusion(
        self,
        tenant_id: TenantId,
        traitement: str,
        tags: frozenset[str],
        par: UserId,
        le: datetime,
    ) -> None:
        """Ajoute un réglage (historique gardé) ; le dernier fait foi."""
        ...


def retenus(dossiers: Sequence[Dossier], etat: EtatTags, traitement: str) -> tuple[Dossier, ...]:
    """Les dossiers qu'aucun tag n'exclut de `traitement`."""
    return tuple(d for d in dossiers if not etat.exclu(d.id, traitement))


def exclus(dossiers: Sequence[Dossier], etat: EtatTags, traitement: str) -> frozenset[DossierId]:
    return frozenset(d.id for d in dossiers if etat.exclu(d.id, traitement))


SANS_TAGS = EtatTags({}, EXCLUSIONS_PAR_DEFAUT)


def etat_du_portefeuille(depot: TagsRepository, tenant_id: TenantId) -> EtatTags:
    return EtatTags(depot.tags_des_dossiers(tenant_id), depot.exclusions(tenant_id))
