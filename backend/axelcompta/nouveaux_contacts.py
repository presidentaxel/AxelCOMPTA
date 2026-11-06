"""Les chauffeurs ajoutés dans Digifactory arrivent dans Entreprises (AXE-845).

Serenity ajoute ses chauffeurs dans Digifactory, pas chez nous. La synchro
(planifiée, ou le bouton « Synchroniser ») repère les contacts qui n'ont
pas de dossier et les **propose** au gestionnaire, préparés depuis Sirene
(forme, premier exercice, activité, société cessée : AXE-834). Rien n'est
créé sans son clic : un contact hors VTC (SERENITY GROUPE) n'entre pas seul.

Les fonctions de décision sont pures ; la lecture Sirene est injectée.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date

import httpx

from axelcompta.core.ids import DossierId
from axelcompta.demo_digifactory import (
    dossier_depuis_contact,
    nom_affiche,
    numero_contact,
    preparer_dossier,
    siren_contact,
)
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.sirene import FicheSirene, fiche_depuis_reponse

URL_RECHERCHE_ENTREPRISES = "https://recherche-entreprises.api.gouv.fr/search"

LireFiche = Callable[[str | None], FicheSirene | None]


@dataclass(frozen=True, slots=True)
class Proposition:
    """Un contact Digifactory sans dossier, préparé pour le gestionnaire."""

    contact_nr: str
    nom: str
    siren: str | None
    dossier: Dossier | None  # None : société cessée, rien à créer
    avertissements: tuple[str, ...]

    @property
    def chauffeur(self) -> bool:
        """Activité VTC lue dans Sirene : la proposition « évidente »."""
        return self.dossier is not None and not self.avertissements


def fiche_sirene(siren: str | None) -> FicheSirene | None:
    """Recherche d'entreprises (data.gouv, sans clé). `None` sans SIREN ou
    sans fiche à ce SIREN exact."""
    if siren is None:
        return None
    reponse = httpx.get(
        URL_RECHERCHE_ENTREPRISES,
        params={"q": siren, "per_page": 1},
        headers={"accept": "application/json"},
        timeout=15.0,
    )
    reponse.raise_for_status()
    corps = reponse.json()
    return fiche_depuis_reponse(corps, siren) if isinstance(corps, dict) else None


def contacts_sans_dossier(
    contacts: Mapping[str, Mapping[str, object]], contacts_avec_dossier: Iterable[str]
) -> list[Mapping[str, object]]:
    """Les contacts Digifactory valides qui n'ont pas encore de dossier, par
    numéro croissant. Un contact au numéro illisible est écarté."""
    connus = set(contacts_avec_dossier)
    retenus = []
    for contact in contacts.values():
        try:
            numero = numero_contact(contact)
        except ValueError:
            continue
        if numero not in connus:
            retenus.append(contact)
    return sorted(retenus, key=lambda c: int(numero_contact(c)))


def proposer(
    contact: Mapping[str, object], lire_fiche: LireFiche, aujourd_hui: date
) -> Proposition:
    numero = numero_contact(contact)
    siren = siren_contact(contact)
    dossier, avertissements = preparer_dossier(
        dossier_depuis_contact(contact, aujourd_hui), lire_fiche(siren), aujourd_hui
    )
    return Proposition(numero, nom_affiche(contact, numero), siren, dossier, avertissements)


def id_du_dossier(contact_nr: str) -> DossierId:
    """Même identifiant que l'import manuel : `DIGI_<nr>`."""
    return DossierId(f"DIGI_{contact_nr}")
