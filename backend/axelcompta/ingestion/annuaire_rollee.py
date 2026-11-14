"""L'annuaire des users Rollee d'un portefeuille (AXE-919). Pur.

Le gestionnaire cherche le compte Rollee d'une entreprise par son nom, parmi
tous les users des comptes Rollee du portefeuille (environ 2 200, partagés
avec d'autres cabinets). Chercher en direct chez Rollee prend plus de dix
minutes : l'annuaire est rempli par le passage de rapprochement (bouton
« Rapprocher Rollee », AXE-918, ou la nuit).

Décision de Louis du 14/11 : le nom du user est montré en clair au
gestionnaire (ce sont ses chauffeurs) ; l'e-mail reste masqué, il sert
seulement à départager deux homonymes. Aucun montant.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from axelcompta.core.ids import TenantId

from .rapprochement_rollee import normaliser_nom

RESULTATS_MAX = 20
LETTRES_MIN = 2


@dataclass(frozen=True, slots=True)
class FicheAnnuaire:
    rollee_user_id: str
    tenant_id: TenantId
    branchement_id: str
    nom: str  # tel que Rollee le donne : « Élodie Martin »
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
    return bool(cherches) and all(any(m.startswith(c) for m in mots) for c in cherches)


def chercher(
    fiches: Iterable[FicheAnnuaire], requete: str, limite: int = RESULTATS_MAX
) -> list[FicheAnnuaire]:
    """Les fiches dont le nom correspond, par nom. Rien sous 2 lettres."""
    if len(normaliser_nom(requete).replace(" ", "")) < LETTRES_MIN:
        return []
    trouvees = [f for f in fiches if correspond(f.nom_normalise, requete)]
    return sorted(trouvees, key=lambda f: (f.nom_normalise, f.rollee_user_id))[:limite]


class AnnuaireRollee(Protocol):
    def fiches(self, tenant_id: TenantId) -> list[FicheAnnuaire]: ...

    def fiche(self, tenant_id: TenantId, rollee_user_id: str) -> FicheAnnuaire | None: ...

    def remplacer(
        self,
        tenant_id: TenantId,
        branchement_id: str,
        fiches: Sequence[FicheAnnuaire],
        partiel: bool = False,
    ) -> None:
        """Les fiches d'un compte Rollee, remplacées à chaque passage. Un
        passage partiel (webhook, users illisibles) ajoute sans retirer."""
        ...


@dataclass
class AnnuaireRolleeMemoire:
    lignes: dict[str, FicheAnnuaire] = field(default_factory=dict)

    def fiches(self, tenant_id: TenantId) -> list[FicheAnnuaire]:
        return [f for f in self.lignes.values() if f.tenant_id == tenant_id]

    def fiche(self, tenant_id: TenantId, rollee_user_id: str) -> FicheAnnuaire | None:
        trouvee = self.lignes.get(rollee_user_id)
        return trouvee if trouvee is not None and trouvee.tenant_id == tenant_id else None

    def remplacer(
        self,
        tenant_id: TenantId,
        branchement_id: str,
        fiches: Sequence[FicheAnnuaire],
        partiel: bool = False,
    ) -> None:
        if not partiel:
            self.lignes = {
                u: f
                for u, f in self.lignes.items()
                if not (f.tenant_id == tenant_id and f.branchement_id == branchement_id)
            }
        self.lignes.update({f.rollee_user_id: f for f in fiches})
