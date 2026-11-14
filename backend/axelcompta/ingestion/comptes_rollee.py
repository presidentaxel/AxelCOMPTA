"""Les plateformes qu'un chauffeur relie dans Rollee Connect (AXE-819).

Doc 19 : c'est le dirigeant qui détient ses données et les relie, depuis son
espace. Le gestionnaire ne voit qu'une synthèse (« 2/2 reliées »), jamais un
montant. Ce module ne fait aucun appel : il traduit la liste des comptes
renvoyée par Rollee (`GET /users/{id}/accounts`) et la résume.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

from axelcompta.core.ids import DossierId
from axelcompta.packs.vtc_demo import Plateforme, plateforme_de

from .providers.rollee import CompteRollee

Etat = Literal["connecte", "en_cours", "a_reconnecter"]


@dataclass(frozen=True, slots=True)
class UtilisateurRollee:
    dossier_id: DossierId
    rollee_user_id: str
    branchement_id: str


@dataclass(frozen=True, slots=True)
class CompteRelie:
    account_id: str
    dossier_id: DossierId
    nom: str
    connecte: bool
    reconnexion: bool
    relie_le: datetime | None  # première fois vu connecté
    maj_le: datetime
    rollee_user_id: str | None = None  # le compte Rollee qui a fourni cette plateforme

    @property
    def etat(self) -> Etat:
        if self.connecte:
            return "connecte"
        return "en_cours" if self.reconnexion else "a_reconnecter"

    def pour_releve(self) -> CompteRollee:
        return CompteRollee(self.account_id, self.nom, self.connecte)


def depuis_rollee(
    dossier_id: DossierId,
    brut: dict[str, Any],
    connu: CompteRelie | None,
    maintenant: datetime,
    rollee_user_id: str | None = None,
) -> CompteRelie:
    connecte = bool(brut.get("connected"))
    relie_le = connu.relie_le if connu and connu.relie_le else (maintenant if connecte else None)
    return CompteRelie(
        account_id=str(brut["id"]),
        dossier_id=dossier_id,
        nom=str(brut.get("name") or brut.get("type") or "Plateforme"),
        connecte=connecte,
        reconnexion=bool(brut.get("reconnecting")),
        relie_le=relie_le,
        maj_le=maintenant,
        rollee_user_id=rollee_user_id or (connu.rollee_user_id if connu else None),
    )


@dataclass(frozen=True, slots=True)
class Synthese:
    """Ce que le gestionnaire voit : des nombres, jamais un montant."""

    reliees: int
    attendues: int
    a_reconnecter: int
    manquantes: tuple[str, ...] = field(default=())  # déclarées, pas encore reliées
    non_declarees: tuple[str, ...] = field(default=())  # reliées, pas déclarées


def noms_plateformes(*groupes: Sequence[str]) -> tuple[str, ...]:
    """Noms tels que Rollee les écrit (Uber, Bolt, Heetch), sans doublon."""
    vus: dict[str, str] = {}
    for groupe in groupes:
        for nom in groupe:
            propre = nom.strip()
            cle = propre.casefold()
            if not propre:
                continue
            if cle not in vus or (vus[cle].islower() and propre != propre.lower()):
                vus[cle] = propre
    return tuple(vus[cle] for cle in sorted(vus))


def synthese(
    comptes: Sequence[CompteRelie], declarees: Sequence[str], plateformes: tuple[Plateforme, ...]
) -> Synthese:
    """`declarees` : `dossiers.plateformes`, ce que le gestionnaire attend."""
    reliees = {
        p.nom
        for c in comptes
        if c.connecte and (p := plateforme_de(c.nom, plateformes)) is not None
    }
    attendues = {d.strip().lower() for d in declarees if d.strip()}
    return Synthese(
        reliees=sum(1 for c in comptes if c.connecte),
        attendues=len(attendues),
        a_reconnecter=sum(1 for c in comptes if c.etat == "a_reconnecter"),
        manquantes=tuple(sorted(attendues - reliees)),
        non_declarees=tuple(sorted(reliees - attendues)) if attendues else (),
    )


class ComptesRolleeRepository(Protocol):
    def utilisateur(self, dossier_id: DossierId) -> UtilisateurRollee | None: ...

    def utilisateurs(self, dossier_id: DossierId) -> list[UtilisateurRollee]:
        """Tous les comptes Rollee de cette entreprise."""
        ...

    def dossier_du_user(self, rollee_user_id: str) -> DossierId | None:
        """AXE-820 : un webhook ne connaît que le user Rollee."""
        ...

    def dossiers_relies(self) -> list[DossierId]:
        """Les dossiers qui ont un user Rollee (rattrapage quotidien)."""
        ...

    def enregistrer_utilisateur(self, utilisateur: UtilisateurRollee, le: datetime) -> None: ...

    def comptes(self, dossier_id: DossierId) -> list[CompteRelie]: ...

    def remplacer_comptes(
        self,
        dossier_id: DossierId,
        comptes: Sequence[CompteRelie],
        rollee_user_id: str | None = None,
    ) -> None:
        """La liste relue chez Rollee remplace celle du dossier. Avec un user,
        seuls les comptes de ce user sont remplacés."""
        ...

    def retirer_comptes_sans_user(self, dossier_id: DossierId) -> None:
        """Après une relecture complète : les comptes non rattachés à un user sont périmés."""
        ...


@dataclass
class ComptesRolleeMemoire:
    par_user: dict[str, UtilisateurRollee] = field(default_factory=dict)
    lus: dict[str, list[CompteRelie]] = field(default_factory=dict)

    def utilisateurs(self, dossier_id: DossierId) -> list[UtilisateurRollee]:
        return [u for u in self.par_user.values() if u.dossier_id == dossier_id]

    def utilisateur(self, dossier_id: DossierId) -> UtilisateurRollee | None:
        trouves = self.utilisateurs(dossier_id)
        return trouves[0] if trouves else None

    def dossier_du_user(self, rollee_user_id: str) -> DossierId | None:
        return next(
            (u.dossier_id for u in self.par_user.values() if u.rollee_user_id == rollee_user_id),
            None,
        )

    def dossiers_relies(self) -> list[DossierId]:
        return sorted({u.dossier_id for u in self.par_user.values()})

    def enregistrer_utilisateur(self, utilisateur: UtilisateurRollee, le: datetime) -> None:
        self.par_user[utilisateur.rollee_user_id] = utilisateur

    def comptes(self, dossier_id: DossierId) -> list[CompteRelie]:
        return list(self.lus.get(dossier_id, []))

    def remplacer_comptes(
        self,
        dossier_id: DossierId,
        comptes: Sequence[CompteRelie],
        rollee_user_id: str | None = None,
    ) -> None:
        if rollee_user_id is None:
            self.lus[dossier_id] = list(comptes)
            return
        ids = {c.account_id for c in comptes}
        gardes = [
            c
            for c in self.lus.get(dossier_id, [])
            if c.rollee_user_id != rollee_user_id and c.account_id not in ids
        ]
        self.lus[dossier_id] = gardes + list(comptes)

    def retirer_comptes_sans_user(self, dossier_id: DossierId) -> None:
        self.lus[dossier_id] = [c for c in self.lus.get(dossier_id, []) if c.rollee_user_id]
