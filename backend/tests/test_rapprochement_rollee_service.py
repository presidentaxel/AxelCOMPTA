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
    )
    assert [u.user_id for u in users] == ["u-iban", "u-nom"]
    assert "u-rien-uber" not in " ".join(rollee.appels)
    assert phrases[0] == "Flotte : lecture de la liste…"
    assert phrases[-1] == "Flotte : 2 comptes Rollee lus."


def test_un_user_est_lu_en_empreintes_et_en_apercu_masque() -> None:
    brut = {"id": "u-iban", "metadata": {"dossier_id": "d1"}}
    user = asyncio.run(lire_user(FauxRollee(), brut, CLE))  # type: ignore[arg-type]
    assert user.dossier_metadata == "d1"
    assert user.apercu == Apercu("É.M.", ("Uber",), "0189")
    assert "Martin" not in repr(user) and IBAN not in repr(user)


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
        "t / Rollee prod : 1 relié(s) automatiquement, 1 à choisir, 1 non trouvé(s) "
        "(simulation : rien n'est écrit)"
    ]
    assert depots.liens.liens(T) == [] and depots.liens.a_choisir(T) == []
    assert rollee.appels[-1] == "fermé"


def test_le_bouton_d_une_fiche_ne_relie_que_cette_entreprise() -> None:
    depots = _depots(FauxRollee())
    dossier = next(d for d in depots.dossiers.lister_par_tenant(T) if d.id == "d-nom")
    phrase = asyncio.run(rapprocher_dossier(depots, dossier, LE))
    assert phrase == "Un compte Rollee correspond. Reliez-le sur cette fiche."
    assert depots.liens.liens(T) == []
    assert [a.rollee_user_id for a in depots.liens.a_choisir(T)] == ["u-nom"]


def test_l_application_relie_le_sur_et_previent_pour_le_reste() -> None:
    depots = _depots(FauxRollee())
    lignes = asyncio.run(passer_tenant(depots, T, True, LE))
    (lien,) = depots.liens.liens(T)
    assert (lien.dossier_id, lien.rollee_user_id, lien.origine, lien.indice) == (
        "d-iban",
        "u-iban",
        "auto",
        "iban",
    )
    assert {(a.rollee_user_id, a.etat) for a in depots.liens.a_choisir(T)} == {
        ("u-nom", "a_choisir"),
        ("u-rien", "non_trouve"),
    }
    assert lignes[-1] == "t : 2 à signaler"
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
    assert [a.rollee_user_id for a in nouveaux] == ["u-neuf"]
    assert {(a.rollee_user_id, a.etat) for a in liens.a_choisir(T)} == {
        ("u-ecarte", "ecarte"),
        ("u-autre", "a_choisir"),
        ("u-neuf", "non_trouve"),
    }


def test_un_lien_pose_entre_temps_renvoie_le_user_au_gestionnaire() -> None:
    liens = LiensRolleeMemoire(tenants={"d1": T})
    liens.lier(Lien(DossierId("d1"), "u-avant", "b1", "manuel", LE, None, "marie"))
    users = [UserRollee("u1", None, Empreintes())]
    appliquer(liens, [Issue("u1", "relie_auto", "d1", "iban")], users, Passage(T, "b1", LE))
    assert [(a.rollee_user_id, a.etat) for a in liens.a_choisir(T)] == [("u1", "a_choisir")]
