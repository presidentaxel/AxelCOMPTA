"""Dossiers du portefeuille branchés sur les contacts Digifactory.

Composition root, comme `demo_seed.py`. Aucun compte n'est créé ici
(depuis le 2026-11-05) : le dirigeant est invité avec sa vraie adresse. Les
transactions viennent de l'API au moment de la synchro : rien de bancaire
n'est écrit dans le dépôt.

Digifactory ne donne pas la forme juridique. Le dossier est posé en SASU à
l'IS le temps du premier enregistrement, puis la forme est reprise du
répertoire Sirene (code `nature_juridique`) quand le contact a un SIREN.
L'identité légale complète (siège, capital, associés) reste vide : Sirene
ne suffit pas à la remplir, et on n'invente rien.

Usage, depuis backend/ (`.env` à la racine) :

    python scripts/ajouter_chauffeurs_digifactory.py
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.models import Dossier

TENANT_DEMO = TenantId("TENANT_DEMO")
# Nomenclature des catégories juridiques, niveau III.
# Depuis juillet 2020, l'INSEE a fondu la SASU (5720) dans la SAS (5710)
# et l'EURL (5498) dans la SARL (5499). On ne devine pas l'associé unique.
_FORME_PAR_NATURE_JURIDIQUE = {
    "1000": "EI",
    "5498": "EURL",
    "5499": "SARL",
    "5710": "SAS",
    "5720": "SASU",
}


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


def forme_depuis_nature_juridique(nature: str) -> str | None:
    """Forme de notre matrice, ou `None` si le code Sirene ne la détermine
    pas (SAS et SASU partagent 5710 depuis 2020)."""
    return _FORME_PAR_NATURE_JURIDIQUE.get(nature.strip())


def _texte(contact: Mapping[str, object], cle: str) -> str:
    valeur = contact.get(cle)
    return valeur.strip() if isinstance(valeur, str) else ""
