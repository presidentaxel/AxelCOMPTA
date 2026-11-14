"""Le lien dossier ↔ user Rollee, son origine et son historique (AXE-911).

Un lien est posé de trois façons : à la création du user depuis l'espace
chauffeur (`cree`), par le rapprochement automatique (`auto`, avec son
indice), ou par le gestionnaire (`manuel`, avec son nom). Un lien retiré
n'est jamais effacé : il passe à l'historique, avec qui, quand et pourquoi.

Les users que le rapprochement n'a pas pu relier seuls attendent le
gestionnaire (« à choisir », « non trouvé »), avec leurs candidats et un
aperçu masqué : initiales, plateformes, 4 derniers chiffres de l'IBAN.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal, Protocol

from axelcompta.core.ids import DossierId, TenantId

from .rapprochement_rollee import Apercu, Candidat

Origine = Literal["cree", "auto", "manuel"]
LIBELLES_INDICE = {
    "metadata": "créé depuis l'espace du chauffeur",
    "iban": "par l'IBAN",
    "nom_email": "par l'e-mail",
    "nom_telephone": "par le téléphone",
}


@dataclass(frozen=True, slots=True)
class Lien:
    dossier_id: DossierId
    rollee_user_id: str
    branchement_id: str
    origine: Origine
    relie_le: datetime
    indice: str | None = None
    relie_par: str | None = None  # e-mail du gestionnaire, pour un lien manuel

    @property
    def comment(self) -> str:
        """« relié automatiquement par l'IBAN », « choisi par marie@… »."""
        if self.origine == "manuel":
            return f"choisi par {self.relie_par or 'le gestionnaire'}"
        if self.origine == "auto":
            return f"relié automatiquement {LIBELLES_INDICE.get(self.indice or '', '')}".strip()
        return "relié depuis l'espace du chauffeur"


@dataclass(frozen=True, slots=True)
class LienRetire:
    lien: Lien
    retire_le: datetime
    retire_par: str
    motif: str


@dataclass(frozen=True, slots=True)
class AChoisir:
    rollee_user_id: str
    tenant_id: TenantId
    branchement_id: str
    etat: Literal["a_choisir", "non_trouve", "ecarte"]  # ecarte : « aucun de ces comptes »
    candidats: tuple[Candidat, ...]
    apercu: Apercu
    maj_le: datetime


class LienDejaPris(ValueError):
    """Ce compte Rollee est déjà relié, ou le retrait ne dit pas lequel."""


class LiensRollee(Protocol):
    def liens(self, tenant_id: TenantId) -> list[Lien]: ...

    def lien(self, dossier_id: DossierId) -> Lien | None: ...

    def liens_du(self, dossier_id: DossierId) -> list[Lien]:
        """Tous les comptes Rollee de cette entreprise, du plus ancien au plus récent."""
        ...

    def historique(self, dossier_id: DossierId) -> list[LienRetire]:
        """Les plus récents d'abord."""
        ...

    def lier(self, lien: Lien) -> None:
        """Lève `LienDejaPris` si ce compte Rollee est déjà relié à une entreprise."""
        ...

    def delier(
        self,
        dossier_id: DossierId,
        par: str,
        motif: str,
        le: datetime,
        rollee_user_id: str | None = None,
    ) -> Lien | None:
        """Retire un lien et le garde à l'historique. Sans user, retire le seul
        lien du dossier. Plusieurs liens sans user : `LienDejaPris`."""
        ...

    def paires_retirees(self, tenant_id: TenantId) -> frozenset[tuple[str, str]]:
        """(user Rollee, dossier) de chaque lien retiré du portefeuille."""
        ...

    def a_choisir(self, tenant_id: TenantId) -> list[AChoisir]:
        """Toute la file du portefeuille, users écartés compris."""
        ...

    def ecarter(self, rollee_user_id: str, le: datetime) -> bool:
        """« Aucun de ces comptes » : le user ne revient plus dans la file."""
        ...

    def remplacer_a_choisir(
        self, tenant_id: TenantId, branchement_id: str, attente: Sequence[AChoisir]
    ) -> None:
        """La file d'un branchement est remplacée à chaque passage."""
        ...

    def retirer_a_choisir(self, rollee_user_id: str) -> None: ...


@dataclass
class LiensRolleeMemoire:
    tenants: dict[str, TenantId] = field(default_factory=dict)  # dossier → tenant
    poses: dict[str, Lien] = field(default_factory=dict)
    retires: list[LienRetire] = field(default_factory=list)
    attente: dict[str, AChoisir] = field(default_factory=dict)

    def liens(self, tenant_id: TenantId) -> list[Lien]:
        return [
            lien
            for lien in self.poses.values()
            if self.tenants.get(str(lien.dossier_id)) == tenant_id
        ]

    def liens_du(self, dossier_id: DossierId) -> list[Lien]:
        return sorted(
            (lien for lien in self.poses.values() if lien.dossier_id == dossier_id),
            key=lambda lien: (lien.relie_le, lien.rollee_user_id),
        )

    def lien(self, dossier_id: DossierId) -> Lien | None:
        trouves = self.liens_du(dossier_id)
        return trouves[0] if trouves else None

    def historique(self, dossier_id: DossierId) -> list[LienRetire]:
        return sorted(
            (r for r in self.retires if r.lien.dossier_id == dossier_id),
            key=lambda r: r.retire_le,
            reverse=True,
        )

    def lier(self, lien: Lien) -> None:
        if lien.rollee_user_id in self.poses:
            raise LienDejaPris("Ce compte Rollee est déjà relié.")
        self.poses[lien.rollee_user_id] = lien

    def delier(
        self,
        dossier_id: DossierId,
        par: str,
        motif: str,
        le: datetime,
        rollee_user_id: str | None = None,
    ) -> Lien | None:
        if rollee_user_id is None:
            du_dossier = self.liens_du(dossier_id)
            if len(du_dossier) > 1:
                raise LienDejaPris("Plusieurs comptes Rollee : précisez lequel retirer.")
            rollee_user_id = du_dossier[0].rollee_user_id if du_dossier else None
        lien = self.poses.get(rollee_user_id) if rollee_user_id else None
        if lien is None or lien.dossier_id != dossier_id:
            return None
        self.poses.pop(lien.rollee_user_id)
        self.retires.append(LienRetire(lien, le, par, motif))
        return lien

    def paires_retirees(self, tenant_id: TenantId) -> frozenset[tuple[str, str]]:
        return frozenset(
            (r.lien.rollee_user_id, str(r.lien.dossier_id))
            for r in self.retires
            if self.tenants.get(r.lien.dossier_id) == tenant_id
        )

    def ecarter(self, rollee_user_id: str, le: datetime) -> bool:
        attente = self.attente.get(rollee_user_id)
        if attente is None:
            return False
        self.attente[rollee_user_id] = replace(attente, etat="ecarte", candidats=(), maj_le=le)
        return True

    def a_choisir(self, tenant_id: TenantId) -> list[AChoisir]:
        return sorted(
            (a for a in self.attente.values() if a.tenant_id == tenant_id),
            key=lambda a: a.rollee_user_id,
        )

    def remplacer_a_choisir(
        self, tenant_id: TenantId, branchement_id: str, attente: Sequence[AChoisir]
    ) -> None:
        self.attente = {
            u: a
            for u, a in self.attente.items()
            if not (a.tenant_id == tenant_id and a.branchement_id == branchement_id)
        }
        self.attente.update({a.rollee_user_id: a for a in attente})

    def retirer_a_choisir(self, rollee_user_id: str) -> None:
        self.attente.pop(rollee_user_id, None)


def lien_manuel(dossier_id: DossierId, attente: AChoisir, par: str, le: datetime) -> Lien:
    return Lien(dossier_id, attente.rollee_user_id, attente.branchement_id, "manuel", le, None, par)
