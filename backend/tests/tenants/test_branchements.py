"""AXE-872 : plusieurs intégrations de chaque type, une par défaut."""

from __future__ import annotations

from datetime import datetime

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.branchements import (
    Branchement,
    BranchementEnConflit,
    BranchementIntrouvable,
    BranchementInvalide,
    BranchementsMemoire,
    Modification,
    a_interroger,
    choisir,
    modifier,
    nouveau,
    pour_dossier,
    types_branches,
    verifier_choix,
)

T = TenantId("t")
LE = datetime(2026, 11, 11, 10, 0)
SMTP = {"hote": "h", "port": "587", "utilisateur": "u", "mot_de_passe": "secret", "expediteur": "e"}


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _ajouter(depot: BranchementsMemoire, nom: str, type_: str = "mail") -> Branchement:
    fournisseur, parametres = (
        ("smtp", SMTP)
        if type_ == "mail"
        else ("digifactory", {"jeton": "j" * 64, "url": "https://digi.example"})
    )
    cree = nouveau(depot.lister(T), T, type_, fournisseur, nom, parametres)
    depot.enregistrer([cree], "admin", LE)
    return cree


def test_le_premier_d_un_type_est_par_defaut_et_le_secret_est_chiffre() -> None:
    depot = BranchementsMemoire()
    premier, second = _ajouter(depot, "SMTP principal"), _ajouter(depot, "SMTP Nord")
    banque = _ajouter(depot, "Digifactory 1", "digifactory")
    assert (premier.par_defaut, second.par_defaut, banque.par_defaut) == (True, False, True)
    assert "secret" not in premier.parametres_chiffres
    assert premier.parametres()["mot_de_passe"] == "secret"


def test_un_champ_manquant_un_fournisseur_inconnu_ou_un_nom_pris_sont_refuses() -> None:
    depot = BranchementsMemoire()
    _ajouter(depot, "SMTP principal")
    with pytest.raises(BranchementInvalide):
        nouveau([], T, "mail", "smtp", "X", {"hote": "h"})
    with pytest.raises(BranchementInvalide):
        nouveau([], T, "digifactory", "digifactory", "D", {"jeton": "j" * 64})
    with pytest.raises(BranchementInvalide):
        nouveau([], T, "mail", "http", "X", {})
    with pytest.raises(BranchementInvalide):
        nouveau([], T, "mail", "smtp", "   ", SMTP)
    with pytest.raises(BranchementEnConflit):
        nouveau(depot.lister(T), T, "mail", "smtp", "smtp  PRINCIPAL", SMTP)


def test_changer_le_defaut_retire_l_ancien() -> None:
    depot = BranchementsMemoire()
    premier, second = _ajouter(depot, "A"), _ajouter(depot, "B")
    a_enregistrer = modifier(depot.lister(T), second.id, Modification(par_defaut=True))
    depot.enregistrer(a_enregistrer, "admin", LE)
    defauts = {b.nom for b in depot.lister(T) if b.par_defaut}
    assert defauts == {"B"}
    # L'ancien défaut est enregistré avant le nouveau (index unique en base).
    assert [b.id for b in a_enregistrer] == [premier.id, second.id]


def test_le_defaut_ne_se_desactive_pas_tant_qu_un_autre_peut_le_remplacer() -> None:
    depot = BranchementsMemoire()
    premier = _ajouter(depot, "A")
    _ajouter(depot, "B")
    with pytest.raises(BranchementEnConflit):
        modifier(depot.lister(T), premier.id, Modification(actif=False))


def test_le_seul_d_un_type_se_desactive_puis_redevient_le_defaut() -> None:
    depot = BranchementsMemoire()
    seul = _ajouter(depot, "A")
    depot.enregistrer(modifier(depot.lister(T), seul.id, Modification(actif=False)), "a", LE)
    assert types_branches(depot.lister(T)) == {}
    depot.enregistrer(modifier(depot.lister(T), seul.id, Modification(actif=True)), "a", LE)
    assert list(types_branches(depot.lister(T))) == ["mail"]


def test_un_secret_vide_garde_l_ancien_et_reste_chiffre() -> None:
    depot = BranchementsMemoire()
    cree = _ajouter(depot, "A")
    avant = cree.parametres_chiffres
    (suite,) = modifier(
        depot.lister(T),
        cree.id,
        Modification(parametres={**SMTP, "mot_de_passe": "  ", "hote": "autre.example"}),
    )
    assert suite.parametres()["mot_de_passe"] == "secret"
    assert suite.parametres()["hote"] == "autre.example"
    assert suite.parametres_chiffres != avant
    assert "secret" not in suite.parametres_chiffres
    assert "autre.example" not in suite.parametres_chiffres


def test_renommer_et_changer_les_identifiants() -> None:
    depot = BranchementsMemoire()
    cree = _ajouter(depot, "A")
    nouveaux = {**SMTP, "mot_de_passe": "autre"}
    (suite,) = modifier(
        depot.lister(T), cree.id, Modification(nom="SMTP siège", parametres=nouveaux)
    )
    assert suite.nom == "SMTP siège" and suite.parametres()["mot_de_passe"] == "autre"
    with pytest.raises(BranchementIntrouvable):
        modifier(depot.lister(T), "inconnu", Modification(nom="x"))


def test_le_dossier_utilise_son_choix_actif_sinon_le_defaut() -> None:
    depot = BranchementsMemoire()
    defaut, nord = _ajouter(depot, "A"), _ajouter(depot, "Nord")
    d = DossierId("d1")
    assert pour_dossier(depot, T, d, "mail") == depot.branchements[defaut.id]
    depot.choisir_pour_dossier(T, d, "mail", nord.id)
    assert pour_dossier(depot, T, d, "mail") == depot.branchements[nord.id]
    depot.choisir_pour_dossier(T, d, "mail", None)
    assert pour_dossier(depot, T, d, "mail") == depot.branchements[defaut.id]
    assert choisir(depot.lister(T), "sms", None) is None


def test_un_dossier_ne_choisit_qu_un_branchement_actif_du_bon_type() -> None:
    depot = BranchementsMemoire()
    mail, banque = _ajouter(depot, "A"), _ajouter(depot, "D", "digifactory")
    verifier_choix(depot.lister(T), "mail", mail.id)
    verifier_choix(depot.lister(T), "mail", None)
    with pytest.raises(BranchementInvalide):
        verifier_choix(depot.lister(T), "mail", banque.id)


def test_rollee_n_a_pas_de_defaut_et_on_les_interroge_tous() -> None:
    """Plusieurs comptes Rollee pour une compta. Tant que le dossier n'en
    choisit pas un, un compte pro peut venir de n'importe lequel."""
    params = {"jeton": "j", "environnement": "production"}
    a = nouveau([], T, "rollee", "rollee", "Entrepreneur", params)
    b = nouveau([a], T, "rollee", "rollee", "Serenity", params)
    assert a.par_defaut is False and b.par_defaut is False
    assert [x.nom for x in a_interroger([a, b], "rollee", None)] == ["Entrepreneur", "Serenity"]
    assert [x.nom for x in a_interroger([a, b], "rollee", b.id)] == ["Serenity"]
    with pytest.raises(BranchementInvalide):
        modifier([a, b], a.id, Modification(par_defaut=True))


def test_un_branchement_rollee_exige_un_environnement_connu() -> None:
    """AXE-818 : jetons sandbox et production distincts chez Rollee."""
    nouveau([], T, "rollee", "rollee", "Rollee", {"jeton": "j", "environnement": "sandbox"})
    with pytest.raises(BranchementInvalide):
        nouveau([], T, "rollee", "rollee", "Rollee", {"jeton": "j", "environnement": "prod"})
