"""AXE-911 : relier un user Rollee au bon dossier, seulement quand c'est sûr."""

from __future__ import annotations

from axelcompta.ingestion.rapprochement_rollee import (
    INDICE_IBAN,
    INDICE_METADATA,
    INDICE_NOM_EMAIL,
    RAISON_DEJA_RELIE,
    RAISON_NOM,
    RAISON_RETIRE,
    DossierIndices,
    Empreintes,
    UserRollee,
    apercu,
    bilan,
    empreinte,
    empreintes,
    normaliser_iban,
    normaliser_nom,
    normaliser_telephone,
    rapprocher,
)

CLE = b"cle-de-test"
IBAN = "FR76 3000 6000 0112 3456 7890 189"


def _user(ident: str, metadata: str | None = None, **valeurs: list[str]) -> UserRollee:
    return UserRollee(ident, metadata, empreintes(CLE, **valeurs))


def _dossier(ident: str, **valeurs: list[str]) -> DossierIndices:
    return DossierIndices(ident, empreintes(CLE, **valeurs))


MARTIN = normaliser_nom("Élodie", "Martin-Dupont")


def test_les_normalisations_rendent_comparables_des_ecritures_differentes() -> None:
    assert MARTIN == normaliser_nom("MARTIN DUPONT", "elodie")
    assert normaliser_iban(IBAN) == normaliser_iban(IBAN.replace(" ", "").lower())
    assert normaliser_telephone("+33 6 12 34 56 78") == normaliser_telephone("06.12.34.56.78")
    assert empreinte(CLE, "") == ""
    assert empreinte(CLE, "X") != empreinte(b"autre-cle", "X")


def test_le_dossier_inscrit_a_la_creation_suffit() -> None:
    (issue,) = rapprocher([_user("u1", metadata="d1")], [_dossier("d1"), _dossier("d2")], {})
    assert (issue.etat, issue.dossier_id, issue.indice) == ("relie_auto", "d1", INDICE_METADATA)


def test_le_meme_iban_relie_seul() -> None:
    (issue,) = rapprocher(
        [_user("u1", ibans=[IBAN])], [_dossier("d1", ibans=[IBAN.replace(" ", "")])], {}
    )
    assert (issue.etat, issue.dossier_id, issue.indice) == ("relie_auto", "d1", INDICE_IBAN)


def test_le_nom_avec_l_email_relie_seul_mais_le_nom_seul_va_au_gestionnaire() -> None:
    avec_email = _user("u1", noms=[MARTIN], emails=["E.Martin@exemple.fr "])
    dossier = _dossier("d1", noms=[MARTIN], emails=["e.martin@exemple.fr"])
    (sur,) = rapprocher([avec_email], [dossier], {})
    assert (sur.etat, sur.indice) == ("relie_auto", INDICE_NOM_EMAIL)
    (faible,) = rapprocher([_user("u2", noms=[MARTIN])], [dossier], {})
    assert faible.etat == "a_choisir" and faible.dossier_id is None
    assert faible.candidats[0].raisons == (RAISON_NOM,)


def test_deux_dossiers_au_meme_iban_vont_au_gestionnaire() -> None:
    (issue,) = rapprocher(
        [_user("u1", ibans=[IBAN])],
        [_dossier("d1", ibans=[IBAN]), _dossier("d2", ibans=[IBAN])],
        {},
    )
    assert issue.etat == "a_choisir" and [c.dossier_id for c in issue.candidats] == ["d1", "d2"]


def test_rien_en_commun_non_trouve() -> None:
    (issue,) = rapprocher([_user("u1", ibans=[IBAN])], [_dossier("d1", noms=[MARTIN])], {})
    assert issue.etat == "non_trouve" and issue.candidats == ()


def test_un_user_deja_relie_n_est_jamais_touche() -> None:
    assert rapprocher([_user("u1", metadata="d1")], [_dossier("d1")], {"u1": "d9"}) == []


def test_un_dossier_deja_relie_n_est_pas_relie_une_seconde_fois_seul() -> None:
    (issue,) = rapprocher([_user("u2", ibans=[IBAN])], [_dossier("d1", ibans=[IBAN])], {"u1": "d1"})
    assert issue.etat == "a_choisir"
    assert RAISON_DEJA_RELIE in issue.candidats[0].raisons


def test_un_lien_retire_par_le_gestionnaire_n_est_pas_repose_seul() -> None:
    (issue,) = rapprocher(
        [_user("u1", ibans=[IBAN])], [_dossier("d1", ibans=[IBAN])], {}, frozenset({("u1", "d1")})
    )
    assert issue.etat == "a_choisir" and RAISON_RETIRE in issue.candidats[0].raisons


def test_deux_users_qui_visent_le_meme_dossier_vont_tous_deux_au_gestionnaire() -> None:
    issues = rapprocher(
        [_user("u1", ibans=[IBAN]), _user("u2", ibans=[IBAN])], [_dossier("d1", ibans=[IBAN])], {}
    )
    assert [i.etat for i in issues] == ["a_choisir", "a_choisir"]
    assert bilan(issues) == {"relie_auto": 0, "a_choisir": 2, "non_trouve": 0}


def test_l_apercu_ne_montre_que_des_initiales_et_la_fin_de_l_iban() -> None:
    vu = apercu("Élodie", "Martin", ["Uber", "Bolt", "Uber"], IBAN)
    assert (vu.initiales, vu.plateformes, vu.iban_fin) == ("É.M.", ("Bolt", "Uber"), "0189")
    assert apercu(None, None, [], None).iban_fin is None


def test_les_empreintes_ne_contiennent_rien_en_clair() -> None:
    traces = empreintes(CLE, [IBAN], [MARTIN], ["a@b.fr"], ["0612345678"])
    texte = repr(traces)
    assert "MARTIN" not in texte and "3000" not in texte and "a@b.fr" not in texte
    assert traces != Empreintes()
