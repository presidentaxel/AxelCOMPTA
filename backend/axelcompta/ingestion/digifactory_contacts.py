"""Dossiers du portefeuille branchés sur les contacts Digifactory.

Mapping contact Digifactory → dossier. Aucun compte n'est créé ici
(depuis le 2026-11-05) : le dirigeant est invité avec sa vraie adresse. Les
transactions viennent de l'API au moment de la synchro : rien de bancaire
n'est écrit dans le dépôt.

Digifactory ne donne ni la forme juridique ni la date de création. Le
dossier part en SASU à l'IS sur l'année civile, puis `preparer_dossier`
reprend de Sirene la forme, le premier exercice et l'activité (AXE-834,
`tenants/sirene.py`), en marquant « à confirmer » ce que Sirene ne tranche
pas. Une société cessée n'a pas de dossier. L'identité légale complète
(siège, capital, associés) reste vide : Sirene ne suffit pas à la remplir.

Usage, depuis backend/ (`.env` à la racine) :

    python scripts/ajouter_chauffeurs_digifactory.py
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.sirene import (
    A_CONFIRMER_EXERCICE,
    A_CONFIRMER_FORME,
    FicheSirene,
    configurer_depuis_sirene,
)

TENANT_DEMO = TenantId("TENANT_DEMO")


def numero_contact(contact: Mapping[str, object]) -> str:
    """`nr` Digifactory, chiffres seuls. On ne fabrique pas d'identifiant
    à partir d'un libellé."""
    brut = contact.get("nr")
    numero = str(brut).strip() if brut is not None else ""
    if not numero.isdigit():
        raise ValueError("numéro de contact Digifactory invalide")
    return numero


def nom_affiche(contact: Mapping[str, object], contact_nr: str) -> str:
    societe = _texte(contact, "companyName")
    if societe:
        return societe
    personne = f"{_texte(contact, 'firstname')} {_texte(contact, 'lastname')}".strip()
    return personne or f"Contact {contact_nr}"


def dossier_depuis_contact(contact: Mapping[str, object], aujourd_hui: date) -> Dossier:
    """Exercice civil de `aujourd_hui` : la première synchro lit mois par
    mois depuis le 1er janvier (doc 16 §5)."""
    numero = numero_contact(contact)
    return Dossier(
        id=DossierId(f"DIGI_{numero}"),
        tenant_id=TENANT_DEMO,
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="reel_normal",
        nom=nom_affiche(contact, numero),
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(aujourd_hui.year, 1, 1),
        exercice_fin=date(aujourd_hui.year, 12, 31),
        mode_acces_bancaire="gestionnaire",
        contact_nr=numero,
        pack_metier="vtc",
        siren=siren_contact(contact),
    )


def siren_contact(contact: Mapping[str, object]) -> str | None:
    """SIREN à 9 chiffres, ou les 9 premiers du SIRET. Rien si les deux
    manquent : on ne déduit pas un SIREN d'un nom."""
    siren = _texte(contact, "siren")
    if len(siren) == 9 and siren.isdigit():
        return siren
    siret = _texte(contact, "siret")
    if len(siret) == 14 and siret.isdigit():
        return siret[:9]
    return None


def _texte(contact: Mapping[str, object], cle: str) -> str:
    valeur = contact.get(cle)
    return valeur.strip() if isinstance(valeur, str) else ""


def preparer_dossier(
    voulu: Dossier, fiche: FicheSirene | None, aujourd_hui: date
) -> tuple[Dossier | None, tuple[str, ...]]:
    """Dossier à créer pour un contact, d'après sa fiche Sirene (AXE-834),
    et les avertissements à afficher. `None` : la société est cessée, pas de
    dossier. Sans fiche, le dossier garde ses valeurs par défaut et toute sa
    configuration est à confirmer."""
    if fiche is None:
        a_confirmer = (A_CONFIRMER_EXERCICE, A_CONFIRMER_FORME)
        return replace(voulu, a_confirmer=a_confirmer), ("pas de fiche Sirene",)
    if not fiche.active:
        return None, (f"société cessée (Sirene : {fiche.etat_administratif})",)
    avertissements: tuple[str, ...] = ()
    if not fiche.chauffeur:
        avertissements = (
            f"activité {fiche.code_naf or 'inconnue'} : pas un chauffeur, à vérifier",
        )
    return configurer_depuis_sirene(voulu, fiche, aujourd_hui), avertissements
