"""Erreurs métier typées (doc 08 §2.7) — jamais d'exception avalée, jamais de
code magique. Squelette : hiérarchie de base seulement.
"""

from __future__ import annotations


class DomaineError(Exception):
    """Racine des erreurs métier attendues (à distinguer d'un bug/invariant violé).

    L'API la traduit en 4xx avec son message, jamais en 500 (AXE-839) :
    400 par défaut, ou selon la famille ci-dessous. Le domaine dit ce qui
    se passe, pas le code HTTP."""


class Conflit(DomaineError):
    """L'état ne le permet pas : déjà fait, déjà clos, période close…"""


class Introuvable(DomaineError):
    """Ce qui est demandé n'existe pas (ou plus)."""


class SaisieInvalide(DomaineError):
    """La saisie est lue mais ses valeurs ne tiennent pas."""


class Interdit(DomaineError):
    """L'appelant est identifié mais n'a pas ce droit (rôle, habilitation)."""


class InvariantViole(Exception):
    """Un invariant du domaine (ex. doc 06 §1) a été violé — fail-fast, jamais
    rattrapé en silence (doc 08 §5)."""
