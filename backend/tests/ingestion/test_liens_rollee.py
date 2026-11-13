"""AXE-911 : le lien dossier ↔ user Rollee, son origine et son historique."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.liens_rollee import (
    AChoisir,
    Lien,
    LienDejaPris,
    LiensRolleeMemoire,
    lien_manuel,
)
from axelcompta.ingestion.rapprochement_rollee import Apercu, Candidat

LE = datetime(2026, 11, 13, 9, tzinfo=UTC)
T = TenantId("t")


def _lien(dossier: str = "d1", user: str = "u1", origine: str = "auto") -> Lien:
    return Lien(DossierId(dossier), user, "b1", origine, LE, "iban")  # type: ignore[arg-type]


def _memoire() -> LiensRolleeMemoire:
    return LiensRolleeMemoire(tenants={"d1": T, "d2": T})


def test_le_comment_dit_comment_le_lien_a_ete_pose() -> None:
    assert _lien().comment == "relié automatiquement par l'IBAN"
    manuel = Lien(DossierId("d1"), "u1", "b1", "manuel", LE, None, "marie@cabinet.fr")
    assert manuel.comment == "choisi par marie@cabinet.fr"
    assert _lien(origine="cree").comment == "relié depuis l'espace du chauffeur"


def test_un_dossier_ou_un_user_ne_se_relie_qu_une_fois() -> None:
    liens = _memoire()
    liens.lier(_lien())
    with pytest.raises(LienDejaPris):
        liens.lier(_lien(user="u2"))
    with pytest.raises(LienDejaPris):
        liens.lier(_lien(dossier="d2"))


def test_un_lien_retire_va_a_l_historique_avec_qui_et_pourquoi() -> None:
    liens = _memoire()
    liens.lier(_lien())
    retire = liens.delier(DossierId("d1"), "marie@cabinet.fr", "homonyme", LE + timedelta(days=1))
    assert retire == _lien() and liens.lien(DossierId("d1")) is None
    (trace,) = liens.historique(DossierId("d1"))
    assert (trace.retire_par, trace.motif) == ("marie@cabinet.fr", "homonyme")
    assert liens.paires_retirees(T) == frozenset({("u1", "d1")})
    assert liens.delier(DossierId("d1"), "x", "y", LE) is None


def test_ecarter_un_user_le_sort_des_candidats() -> None:
    liens = _memoire()
    attente = AChoisir(
        "u9", T, "b1", "a_choisir", (Candidat("d1", ("même nom",), False),), Apercu("É.M."), LE
    )
    liens.remplacer_a_choisir(T, "b1", [attente])
    assert liens.ecarter("u9", LE) and not liens.ecarter("inconnu", LE)
    (ecarte,) = liens.a_choisir(T)
    assert ecarte.etat == "ecarte" and ecarte.candidats == ()
    choisi = lien_manuel(DossierId("d1"), attente, "marie@cabinet.fr", LE)
    assert (choisi.origine, choisi.relie_par, choisi.rollee_user_id) == (
        "manuel",
        "marie@cabinet.fr",
        "u9",
    )
