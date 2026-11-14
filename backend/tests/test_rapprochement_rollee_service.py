"""AXE-911 : lecture, comparaison et application, avec de faux Rollee et Digifactory."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest
from cryptography.fernet import Fernet

from axelcompta.core.identite import Adresse, Associe, IdentiteEntreprise
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.ingestion.liens_rollee import AChoisir, Lien, LiensRolleeMemoire
from axelcompta.ingestion.providers.rollee import RolleeIndisponible
from axelcompta.ingestion.rapprochement_rollee import Apercu, Empreintes, Issue, UserRollee
from axelcompta.plateformes_rollee import ServicesRollee
from axelcompta.rapprochement_rollee_service import (
    DepotsRapprochement,
    Passage,
    SourcesDossiers,
    appliquer,
    ibans_digifactory,
    indices_dossier,
    lire_user,
    lire_users,
    passer_tenant,
    phrase_carte,
    phrase_lecture,
    rapprocher_dossier,
)
from axelcompta.tenants.branchements import BranchementsMemoire, nouveau
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier, Tenant

LE = datetime(2026, 11, 13, 3, tzinfo=UTC)
T = TenantId("t")
IBAN = "FR7630006000011234567890189"
CLE = b"cle"


class FauxRollee:
    def __init__(self) -> None:
        self.appels: list[str] = []

    async def utilisateurs(self) -> list[dict[str, Any]]:
        return [{"id": "u-iban", "metadata": {}}, {"id": "u-nom"}, {"id": "u-rien"}]

    async def comptes(self, user_id: str) -> list[dict[str, Any]]:
        return [{"id": f"{user_id}-uber", "name": "Uber"}]

    async def profil(self, compte_id: str) -> dict[str, Any]:
        self.appels.append(f"profil {compte_id}")
        if compte_id == "u-nom-uber":
            return {"first_name": "Karim", "last_name": "Benali"}
        if compte_id == "u-rien-uber":
            raise RuntimeError("profil indisponible")
        return {"first_name": "Élodie", "last_name": "Martin", "email": "e@m.fr"}

    async def coordonnees_bancaires(self, compte_id: str) -> dict[str, Any]:
        return {"iban": IBAN} if compte_id == "u-iban-uber" else {}

    async def aclose(self) -> None:
        self.appels.append("fermé")


def _dossier(
    ident: str, contact: str | None = None, identite: IdentiteEntreprise | None = None
) -> Dossier:
    return Dossier(
        DossierId(ident),
        T,
        "SASU",
        "IS",
        "reel_normal",
        ident.upper(),
        "assujetti_taux_reduit",
        date(2026, 1, 1),
        contact_nr=contact,
        identite=identite,
    )


def _identite(nom: str, prenoms: str) -> IdentiteEntreprise:
    adresse = Adresse("1", "rue de la Paix", "75001", "Paris")
    return IdentiteEntreprise(
        "SAS X",
        "123456789",
        "00011",
        adresse,
        "4932Z",
        "VTC",
        "contact@x.fr",
        100_00,
        (Associe("M", nom, prenoms, date(1990, 1, 1), "75", "Paris", adresse, 100, "Président"),),
    )


SOURCES = SourcesDossiers(
    contacts={"7": {"firstname": "Elodie", "lastname": "MARTIN"}},
    ibans={"d-iban": [IBAN]},
    emails={},
)


def _depots(rollee: FauxRollee) -> DepotsRapprochement:
    branchements = BranchementsMemoire()
    branchement = nouveau(
        [], T, "rollee", "rollee", "Rollee prod", {"jeton": "j", "environnement": "production"}
    )
    branchements.enregistrer([branchement], "admin", LE)
    dossiers = InMemoryDossierRepository()
    dossiers.enregistrer_tenant(Tenant(id=T, nom="T"))
    dossiers.enregistrer(_dossier("d-iban", contact="7"))
    dossiers.enregistrer(_dossier("d-nom", identite=_identite("Benali", "Karim")))

    async def sources(_t: TenantId, _d: tuple[Dossier, ...]) -> SourcesDossiers:
        return SOURCES

    return DepotsRapprochement(
        services=ServicesRollee(
            branchements,
            ComptesRolleeMemoire(),
            fabrique=lambda _b, _g: rollee,  # type: ignore[arg-type,return-value]
        ),
        liens=LiensRolleeMemoire(tenants={"d-iban": T, "d-nom": T}),
        dossiers=dossiers,
        sources=sources,
        prevenir=lambda _t, nouveaux: f"{len(nouveaux)} à signaler",
    )


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXELCOMPTA_CLE_INTEGRATIONS", Fernet.generate_key().decode())


def test_la_phrase_de_lecture_dit_ou_on_en_est() -> None:
    assert phrase_lecture("Flotte", 0, 400, 0) == "Flotte : 400 comptes Rollee à lire."
    assert phrase_lecture("Flotte", 0, 0, 0) == "Flotte : aucun compte Rollee à lire."
    assert phrase_lecture("Flotte", 100, 400, 10) == (
        "Flotte : 100/400 comptes Rollee lus, environ 30 s."
    )
    assert phrase_lecture("Flotte", 400, 400, 40) == "Flotte : 400 comptes Rollee lus."


def test_un_429_est_relu_une_fois_et_reste_illisible() -> None:
    class Sature(FauxRollee):
        async def profil(self, compte_id: str) -> dict[str, Any]:
            self.appels.append(f"profil {compte_id}")
            raise RolleeIndisponible("GET /profile : 429 après 5 essais", 429)

    rollee = Sature()
    lecture = asyncio.run(lire_users(rollee, CLE, seulement="u-iban"))  # type: ignore[arg-type]
    assert lecture.users == []
    assert len(lecture.erreurs) == 1
    assert rollee.appels == ["profil u-iban-uber", "profil u-iban-uber"]


def test_un_user_sans_plateforme_n_est_pas_interroge_et_un_changement_relit() -> None:
    class Liste(FauxRollee):
        def __init__(self) -> None:
            super().__init__()
            self.nombre = 0

        async def utilisateurs(self) -> list[dict[str, Any]]:
            return [{"id": "u-iban", "accounts_number": self.nombre}]

    rollee = Liste()
    lecture = asyncio.run(lire_users(rollee, CLE))  # type: ignore[arg-type]
    assert lecture.users[0].accounts_number == 0
    assert rollee.appels == []
    rollee.nombre = 1
    connu = lecture.users[0]
    encore = asyncio.run(lire_users(rollee, CLE, connus={"u-iban": connu}))  # type: ignore[arg-type]
    assert encore.users[0].accounts_number == 1
    assert any(appel.startswith("profil") for appel in rollee.appels)


def test_la_carte_evite_de_relire_le_profil_des_comptes_connus() -> None:
    rollee = FauxRollee()
    connu = UserRollee("u-iban", None, Empreintes(), Apercu("É.M.", ("Uber",), "0189"))
    gardes: list[str] = []
    users = asyncio.run(
        lire_users(
            rollee,  # type: ignore[arg-type]
            CLE,
            connus={"u-iban": connu},
            garder=lambda user: gardes.append(user.user_id),
        )
    ).users
    assert [u.user_id for u in users] == ["u-iban", "u-nom", "u-rien"]
    assert users[0] is connu
    assert "profil u-iban-uber" not in rollee.appels
    assert gardes == ["u-nom", "u-rien"]


def test_la_liste_rafraichit_le_dossier_inscrit_sans_relire_le_profil() -> None:
    class AvecDossier(FauxRollee):
        async def utilisateurs(self) -> list[dict[str, Any]]:
            return [{"id": "u-iban", "metadata": {"dossier_id": "d-iban"}}]

    connu = UserRollee("u-iban", None, Empreintes(), Apercu())
    (user,) = asyncio.run(
        lire_users(AvecDossier(), CLE, connus={"u-iban": connu})  # type: ignore[arg-type]
    ).users
    assert user.dossier_metadata == "d-iban"
    assert user.empreintes == connu.empreintes


def test_un_passage_plafonne_ne_lit_que_les_premiers_absents() -> None:
    rollee = FauxRollee()
    laisses: list[int] = []
    users = asyncio.run(
        lire_users(rollee, CLE, plafond=1, laisses=laisses)  # type: ignore[arg-type]
    ).users
    assert [u.user_id for u in users] == ["u-iban"]
    assert laisses == [2]
    profils = [appel for appel in rollee.appels if appel.startswith("profil")]
    assert profils == ["profil u-iban-uber"]


def test_l_entretien_remplit_la_carte_sans_poser_de_lien() -> None:
    rollee = FauxRollee()
    depots = _depots(rollee)
    branchement = depots.services.branchements.lister(T)[0].id
    lignes = asyncio.run(passer_tenant(depots, T, False, LE, entretenir=True, plafond=1))
    assert depots.liens.liens(T) == [] and depots.liens.a_choisir(T) == []
    assert list(depots.cartes.lire(T, branchement)) == ["u-iban"]
    assert "carte mise à jour" in lignes[0] and "2 encore absents" in lignes[0]
    rollee.appels.clear()
    asyncio.run(passer_tenant(depots, T, False, LE, entretenir=True, plafond=1))
    assert "profil u-iban-uber" not in rollee.appels
    assert set(depots.cartes.lire(T, branchement)) == {"u-iban", "u-nom"}


def test_la_phrase_de_carte_separe_le_connu_et_le_nouveau() -> None:
    assert phrase_carte("Flotte", 120, 0, 40, 0) == (
        "Flotte : 120 comptes déjà connus, 40 nouveaux à lire."
    )
    assert phrase_carte("Flotte", 120, 10, 40, 10) == (
        "Flotte : 120 déjà connus, 10/40 nouveaux lus, environ 30 s."
    )
    assert phrase_carte("Flotte", 120, 0, 0, 0) == "Flotte : 120 comptes déjà connus."


def test_le_second_passage_compare_la_carte_sans_relire_les_profils() -> None:
    rollee = FauxRollee()
    depots = _depots(rollee)
    dossier = next(d for d in depots.dossiers.lister_par_tenant(T) if d.id == "d-nom")
    asyncio.run(rapprocher_dossier(depots, dossier, LE))
    rollee.appels.clear()
    bilan = asyncio.run(rapprocher_dossier(depots, dossier, LE))
    assert "correspond" in bilan.phrase
    assert [appel for appel in rollee.appels if appel.startswith("profil")] == []
    assert [lien.rollee_user_id for lien in depots.liens.liens(T)] == ["u-nom"]


def test_la_lecture_annonce_l_avancement_et_saute_les_deja_relies() -> None:
    rollee = FauxRollee()
    phrases: list[str] = []
    users = asyncio.run(
        lire_users(
            rollee,  # type: ignore[arg-type]
            CLE,
            nom="Flotte",
            noter=phrases.append,
            sauf=frozenset({"u-rien"}),
        )
    ).users
    assert [u.user_id for u in users] == ["u-iban", "u-nom"]
    assert "u-rien-uber" not in " ".join(rollee.appels)
    assert phrases[0] == "Flotte : lecture de la liste…"
    assert phrases[-1] == "Flotte : 2 comptes Rollee lus."


def test_un_user_est_lu_en_empreintes_et_en_apercu_masque() -> None:
    brut = {"id": "u-iban", "metadata": {"dossier_id": "d1"}}
    user = asyncio.run(lire_user(FauxRollee(), brut, CLE))  # type: ignore[arg-type]
    assert user.dossier_metadata == "d1"
    assert user.apercu.initiales == "É.M."
    assert user.apercu.plateformes == ("Uber",)
    assert user.apercu.iban_fin is None
    assert user.apercu.nom == "Élodie Martin"
    assert user.apercu.email_masque == "e•••@m.fr"
    assert IBAN not in repr(user)


def test_les_indices_d_un_dossier_viennent_de_digifactory_et_de_l_identite() -> None:
    indices = indices_dossier(_dossier("d-iban", contact="7"), SOURCES, CLE)
    assert len(indices.empreintes.ibans) == 1 and len(indices.empreintes.noms) == 1
    avec_identite = indices_dossier(
        _dossier("d2", identite=_identite("Benali", "Karim")), SOURCES, CLE
    )
    assert len(avec_identite.empreintes.emails) == 1  # e-mail de l'entreprise


def test_ibans_digifactory_lit_un_dict_ou_une_liste() -> None:
    assert ibans_digifactory({"a1": {"id": "a1", "iban": "FR1"}, "a2": {"id": "a2"}}) == ["FR1"]
    assert ibans_digifactory([{"iban": "FR2"}]) == ["FR2"]
    assert ibans_digifactory(None) == []


def test_la_simulation_donne_le_bilan_sans_rien_ecrire() -> None:
    rollee = FauxRollee()
    depots = _depots(rollee)
    lignes = asyncio.run(passer_tenant(depots, T, False, LE))
    assert lignes == [
        "t / Rollee prod : 2 relié(s) automatiquement, 0 à choisir, 1 non trouvé(s) "
        "(simulation : rien n'est écrit)"
    ]
    assert depots.liens.liens(T) == [] and depots.liens.a_choisir(T) == []
    assert rollee.appels[-1] == "fermé"


def test_le_bouton_d_une_fiche_ne_relie_que_cette_entreprise() -> None:
    depots = _depots(FauxRollee())
    dossier = next(d for d in depots.dossiers.lister_par_tenant(T) if d.id == "d-nom")
    bilan = asyncio.run(rapprocher_dossier(depots, dossier, LE))
    assert bilan.phrase == "Un seul compte Rollee correspond : le lien est posé."
    assert [lien.rollee_user_id for lien in depots.liens.liens(T)] == ["u-nom"]
    assert depots.liens.a_choisir(T) == []


def test_l_application_relie_le_sur_et_previent_pour_le_reste() -> None:
    depots = _depots(FauxRollee())
    lignes = asyncio.run(passer_tenant(depots, T, True, LE))
    poses = {
        (str(lien.dossier_id), lien.rollee_user_id, lien.indice) for lien in depots.liens.liens(T)
    }
    assert poses == {("d-iban", "u-iban", "nom_unique"), ("d-nom", "u-nom", "nom_unique")}
    assert depots.liens.a_choisir(T) == []
    assert "à signaler" not in lignes[-1]
    # Second passage : le lien reste, la file aussi, personne n'est re-prévenu.
    encore = asyncio.run(passer_tenant(depots, T, True, LE))
    assert len(encore) == 1 and "0 relié(s)" in encore[0]


def _attente(user: str, etat: str = "a_choisir") -> AChoisir:
    return AChoisir(user, T, "b1", etat, (), Apercu(), LE)  # type: ignore[arg-type]


def test_un_user_ecarte_le_reste_et_un_passage_partiel_garde_la_file() -> None:
    liens = LiensRolleeMemoire(tenants={"d1": T})
    liens.remplacer_a_choisir(T, "b1", [_attente("u-ecarte", "ecarte"), _attente("u-autre")])
    users = [UserRollee("u-ecarte", None, Empreintes()), UserRollee("u-neuf", None, Empreintes())]
    issues = [Issue("u-ecarte", "a_choisir"), Issue("u-neuf", "non_trouve")]
    nouveaux = appliquer(liens, issues, users, Passage(T, "b1", LE, partiel=True))
    assert nouveaux == []
    assert {(a.rollee_user_id, a.etat) for a in liens.a_choisir(T)} == {
        ("u-ecarte", "ecarte"),
        ("u-autre", "a_choisir"),
    }


def test_un_lien_pose_entre_temps_renvoie_le_user_au_gestionnaire() -> None:
    liens = LiensRolleeMemoire(tenants={"d1": T})
    liens.lier(Lien(DossierId("d1"), "u1", "b1", "manuel", LE, None, "marie"))
    users = [UserRollee("u1", None, Empreintes())]
    appliquer(liens, [Issue("u1", "relie_auto", "d1", "iban")], users, Passage(T, "b1", LE))
    assert [(a.rollee_user_id, a.etat) for a in liens.a_choisir(T)] == [("u1", "a_choisir")]
