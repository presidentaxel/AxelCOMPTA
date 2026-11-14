"""Recherche d'un user Rollee par son nom, sur la carte déjà lue.

Le gestionnaire cherche le compte Rollee d'une entreprise parmi tous les
users des comptes Rollee du portefeuille. Chercher en direct chez Rollee
prend plus de dix minutes : la carte est remplie par le passage de
rapprochement.

Décision de Louis du 14/11 : le nom du user est montré en clair (ce sont
ses chauffeurs) ; l'e-mail reste masqué, il sert à départager deux
homonymes. Aucun montant.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from axelcompta.core.ids import TenantId

from .rapprochement_rollee import normaliser_nom

RESULTATS_MAX = 20
LETTRES_MIN = 2


def masquer_email(email: str | None) -> str | None:
    """« elodie.martin@exemple.fr » → « e•••n@exemple.fr »."""
    if not email or "@" not in email:
        return None
    local, domaine = email.strip().rsplit("@", 1)
    if len(local) <= 2:
        return f"{local[:1]}•••@{domaine}"
    return f"{local[0]}•••{local[-1]}@{domaine}"


@dataclass(frozen=True, slots=True)
class FicheAnnuaire:
    rollee_user_id: str
    tenant_id: TenantId
    branchement_id: str
    nom: str
    plateformes: tuple[str, ...]
    email_masque: str | None
    maj_le: datetime

    @property
    def nom_normalise(self) -> str:
        return normaliser_nom(self.nom)


def correspond(nom_normalise: str, requete: str) -> bool:
    """Chaque mot de la recherche commence un mot du nom, dans n'importe quel
    ordre, sans accents : « mart elo » trouve « Élodie Martin-Dupont »."""
    mots = nom_normalise.split()
    cherches = normaliser_nom(requete).split()
    return bool(cherches) and all(
        any(mot.startswith(cherche) for mot in mots) for cherche in cherches
    )


def chercher(
    fiches: Iterable[FicheAnnuaire], requete: str, limite: int = RESULTATS_MAX
) -> list[FicheAnnuaire]:
    """Les fiches dont le nom correspond, par nom. Rien sous 2 lettres."""
    if len(normaliser_nom(requete).replace(" ", "")) < LETTRES_MIN:
        return []
    trouvees = [fiche for fiche in fiches if correspond(fiche.nom_normalise, requete)]
    return sorted(trouvees, key=lambda fiche: (fiche.nom_normalise, fiche.rollee_user_id))[:limite]
