"""Implémentation en mémoire de CompteRepository — pour les tests rapides
et pour brancher `api/routes.py` sans dépendre d'un accès réseau à Supabase
(Louis, 2026-09-07 : « je ne veux pas dépendre de Supabase pour tous les
tests »). Comme `workflow/decisions_memory.py` pour les décisions.
"""

from __future__ import annotations

from axelcompta.core.ids import DossierId

from .comptes import (
    CompteDejaInviteError,
    CompteRepository,
    Invitation,
    InvitationAbsente,
    InvitationFermee,
    MembreCompte,
    MembreInconnu,
    StatutInvitation,
)


class InMemoryCompteRepository(CompteRepository):
    def __init__(self) -> None:
        self._invitations: dict[DossierId, Invitation] = {}
        self._membres: dict[str, dict[str, bool]] = {}
        # AXE-812 : facteurs TOTP enrôlés, par (portefeuille, e-mail).
        self.facteurs_mfa: dict[tuple[str, str], int] = {}

    def inviter(
        self, dossier_id: DossierId, email: str, *, verifier_existant: bool = True
    ) -> Invitation:
        if verifier_existant and dossier_id in self._invitations:
            raise CompteDejaInviteError(f"dossier déjà invité : {dossier_id}")
        invitation = Invitation(dossier_id=dossier_id, email=email, statut=StatutInvitation.INVITE)
        self._invitations[dossier_id] = invitation
        return invitation

    def statut(self, dossier_id: DossierId) -> Invitation | None:
        return self._invitations.get(dossier_id)

    def membres(self, tenant_id: str) -> list[MembreCompte]:
        return [
            MembreCompte(email=email, accepte=accepte)
            for email, accepte in sorted(self._membres.get(tenant_id, {}).items())
        ]

    def inviter_membre(self, tenant_id: str, email: str, role: str = "membre") -> None:
        propre = email.strip()
        if any(propre in emails for emails in self._membres.values()):
            raise CompteDejaInviteError(f"un compte existe déjà : {email}")
        self._membres.setdefault(tenant_id, {})[propre] = False

    def renvoyer(self, dossier_id: DossierId) -> Invitation:
        invitation = self._invitations.get(dossier_id)
        if invitation is None:
            raise InvitationAbsente(f"aucune invitation : {dossier_id}")
        if invitation.statut is StatutInvitation.ACTIF:
            raise InvitationFermee("Le compte est déjà ouvert.")
        return invitation

    def reinitialiser_mfa(self, tenant_id: str, email: str) -> int:
        propre = email.strip()
        if propre not in self._membres.get(tenant_id, {}):
            raise MembreInconnu(f"aucun membre {email} dans ce portefeuille")
        retires = self.facteurs_mfa.pop((tenant_id, propre), 0)
        return retires

    def annuler(self, dossier_id: DossierId) -> None:
        invitation = self._invitations.get(dossier_id)
        if invitation is None:
            raise InvitationAbsente(f"aucune invitation : {dossier_id}")
        if invitation.statut is StatutInvitation.ACTIF:
            raise InvitationFermee("Le compte est déjà ouvert.")
        del self._invitations[dossier_id]
