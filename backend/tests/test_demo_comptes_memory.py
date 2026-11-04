from __future__ import annotations

import pytest

from axelcompta.core.ids import DossierId
from axelcompta.demo_comptes import (
    CompteDejaInviteError,
    InvitationAbsente,
    InvitationFermee,
    StatutInvitation,
)
from axelcompta.demo_comptes_memory import InMemoryCompteRepository

DOSSIER = DossierId("DEMO_sophie")


def test_statut_est_none_tant_que_personne_nest_invite() -> None:
    repo = InMemoryCompteRepository()
    assert repo.statut(DOSSIER) is None


def test_inviter_cree_une_invitation_au_statut_invite() -> None:
    repo = InMemoryCompteRepository()
    invitation = repo.inviter(DOSSIER, "sophie@example.com")
    assert invitation.statut is StatutInvitation.INVITE
    assert repo.statut(DOSSIER) == invitation


def test_inviter_deux_fois_le_meme_dossier_est_refuse() -> None:
    """doc 08 §2.7 : pas de double invitation silencieuse."""
    repo = InMemoryCompteRepository()
    repo.inviter(DOSSIER, "sophie@example.com")
    with pytest.raises(CompteDejaInviteError):
        repo.inviter(DOSSIER, "sophie-bis@example.com")


def test_statut_est_isole_par_dossier() -> None:
    repo = InMemoryCompteRepository()
    autre = DossierId("DEMO_karim")
    repo.inviter(DOSSIER, "sophie@example.com")
    assert repo.statut(autre) is None


def test_un_membre_invite_n_a_pas_encore_accepte() -> None:
    repo = InMemoryCompteRepository()
    repo.inviter_membre("T1", "marie@example.com")

    membres = repo.membres("T1")

    assert [(membre.email, membre.accepte) for membre in membres] == [("marie@example.com", False)]


def test_inviter_un_membre_deja_connu_est_refuse() -> None:
    repo = InMemoryCompteRepository()
    repo.inviter_membre("T1", "marie@example.com")

    with pytest.raises(CompteDejaInviteError):
        repo.inviter_membre("T1", "marie@example.com")


def test_renvoyer_une_invitation_en_attente_la_laisse_en_place() -> None:
    repo = InMemoryCompteRepository()
    repo.inviter(DOSSIER, "sophie@example.com")
    renvoyee = repo.renvoyer(DOSSIER)
    assert renvoyee.statut is StatutInvitation.INVITE
    assert repo.statut(DOSSIER) == renvoyee


def test_annuler_retire_l_invitation_en_attente() -> None:
    repo = InMemoryCompteRepository()
    repo.inviter(DOSSIER, "sophie@example.com")
    repo.annuler(DOSSIER)
    assert repo.statut(DOSSIER) is None


def test_annuler_un_compte_ouvert_est_refuse() -> None:
    repo = InMemoryCompteRepository()
    invitation = repo.inviter(DOSSIER, "sophie@example.com")
    repo._invitations[DOSSIER] = invitation.__class__(
        dossier_id=DOSSIER, email=invitation.email, statut=StatutInvitation.ACTIF
    )
    with pytest.raises(InvitationFermee):
        repo.annuler(DOSSIER)
    assert repo.statut(DOSSIER) is not None


def test_renvoyer_sans_invitation_est_absent() -> None:
    repo = InMemoryCompteRepository()
    with pytest.raises(InvitationAbsente):
        repo.renvoyer(DOSSIER)
