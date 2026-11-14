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
    passer_tenant,
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
        return [{"id": f"{user_id}-uber", "name": "Bolt"}]

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


def test_un_user_est_lu_en_empreintes_et_en_apercu_masque() -> None:
    brut = {"id": "u-iban", "metadata": {"dossier_id": "d1"}}
    user = asyncio.run(lire_user(FauxRollee(), brut, CLE))  # type: ignore[arg-type]
    assert user.dossier_metadata == "d1"
    assert user.apercu == Apercu("É.M.", ("Bolt",), "0189")
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
        "t : 2 relié(s) automatiquement, 0 à choisir, 1 non trouvé(s) "
        "(simulation : rien n'est écrit)",
        "  Rollee prod : 2 relié(s) automatiquement, 0 à choisir, 1 non trouvé(s)",
    ]
    assert depots.liens.liens(T) == [] and depots.liens.a_choisir(T) == []
    assert rollee.appels[-1] == "fermé"


def test_l_application_relie_par_l_iban_et_par_le_nom_unique() -> None:
    depots = _depots(FauxRollee())
    lignes = asyncio.run(passer_tenant(depots, T, True, LE))
    assert {
        (x.dossier_id, x.rollee_user_id, x.origine, x.indice) for x in depots.liens.liens(T)
    } == {("d-iban", "u-iban", "auto", "iban"), ("d-nom", "u-nom", "auto", "nom_unique")}
    # AXE-918 : un user sans candidat n'encombre pas la file du gestionnaire.
    assert depots.liens.a_choisir(T) == []
    assert len(lignes) == 2
    encore = asyncio.run(passer_tenant(depots, T, True, LE))
    assert "0 relié(s)" in encore[0]


def test_un_nom_porte_sur_deux_comptes_rollee_va_au_gestionnaire_et_le_previent() -> None:
    """AXE-918 : le nom n'est unique que sur l'ensemble des comptes Rollee."""
    depots = _depots(FauxRollee())
    second = nouveau(
        [], T, "rollee", "rollee", "Rollee flotte", {"jeton": "j", "environnement": "production"}
    )
    depots.services.branchements.enregistrer([second], "admin", LE)
    lignes = asyncio.run(passer_tenant(depots, T, True, LE))
    # Chaque compte rend les mêmes users : tout nom est porté deux fois.
    assert {x.indice for x in depots.liens.liens(T)} == set()
    assert {a.rollee_user_id for a in depots.liens.a_choisir(T)} == {"u-iban", "u-nom"}
    assert lignes[-1] == "t : 4 à signaler"


def _attente(user: str, etat: str = "a_choisir") -> AChoisir:
    return AChoisir(user, T, "b1", etat, (), Apercu(), LE)  # type: ignore[arg-type]


def test_un_user_ecarte_le_reste_et_un_passage_partiel_garde_la_file() -> None:
    liens = LiensRolleeMemoire(tenants={"d1": T})
    liens.remplacer_a_choisir(T, "b1", [_attente("u-ecarte", "ecarte"), _attente("u-autre")])
    users = [UserRollee("u-ecarte", None, Empreintes()), UserRollee("u-neuf", None, Empreintes())]
    issues = [Issue("u-ecarte", "a_choisir"), Issue("u-neuf", "non_trouve")]
    nouveaux = appliquer(liens, issues, users, Passage(T, "b1", LE, partiel=True))
    assert nouveaux == []  # un non trouvé n'est pas mis dans la file (AXE-918)
    assert {(a.rollee_user_id, a.etat) for a in liens.a_choisir(T)} == {
        ("u-ecarte", "ecarte"),
        ("u-autre", "a_choisir"),
    }


def test_un_lien_pose_entre_temps_renvoie_le_user_au_gestionnaire() -> None:
    liens = LiensRolleeMemoire(tenants={"d1": T})
    liens.lier(Lien(DossierId("d1"), "u-avant", "b1", "manuel", LE, None, "marie"))
    users = [UserRollee("u1", None, Empreintes())]
    appliquer(liens, [Issue("u1", "relie_auto", "d1", "iban")], users, Passage(T, "b1", LE))
    assert [(a.rollee_user_id, a.etat) for a in liens.a_choisir(T)] == [("u1", "a_choisir")]


def test_un_user_illisible_empeche_tout_lien_par_le_nom_seul() -> None:
    """AXE-918 : Rollee débordé (429) sur un user. Il pourrait porter le même
    nom qu'un autre : le nom seul ne relie personne à ce passage."""

    class RolleeDeborde(FauxRollee):
        async def utilisateurs(self) -> list[dict[str, Any]]:
            return [*await super().utilisateurs(), {"id": "u-429"}]

        async def comptes(self, user_id: str) -> list[dict[str, Any]]:
            if user_id == "u-429":
                raise RolleeIndisponible("429 après 5 essais")
            return await super().comptes(user_id)

    depots = _depots(RolleeDeborde())
    lignes = asyncio.run(passer_tenant(depots, T, True, LE))
    # L'IBAN relie toujours ; le nom seul, plus.
    assert {(x.rollee_user_id, x.indice) for x in depots.liens.liens(T)} == {("u-iban", "iban")}
    assert [a.rollee_user_id for a in depots.liens.a_choisir(T)] == ["u-nom"]
    assert "1 user(s) Rollee illisible(s)" in lignes[1]
    assert lignes[2] == "    429 après 5 essais"


def test_un_user_deborde_est_relu_a_la_fin_et_uber_n_est_pas_interroge_sur_l_iban() -> None:
    """AXE-918 : un 429 passager ne prive pas du lien par le nom."""

    class DebordeUneFois(FauxRollee):
        def __init__(self) -> None:
            super().__init__()
            self.essais: dict[str, int] = {}
            self.ibans: list[str] = []

        async def comptes(self, user_id: str) -> list[dict[str, Any]]:
            self.essais[user_id] = self.essais.get(user_id, 0) + 1
            if user_id == "u-nom" and self.essais[user_id] == 1:
                raise RolleeIndisponible("429")
            return [{"id": f"{user_id}-uber", "name": "uber.com-rev"}]

        async def coordonnees_bancaires(self, compte_id: str) -> dict[str, Any]:
            self.ibans.append(compte_id)
            return await super().coordonnees_bancaires(compte_id)

    rollee = DebordeUneFois()
    depots = _depots(rollee)
    asyncio.run(passer_tenant(depots, T, True, LE))
    assert ("u-nom", "nom_unique") in {(x.rollee_user_id, x.indice) for x in depots.liens.liens(T)}
    assert rollee.essais["u-nom"] == 2
    assert rollee.ibans == []  # Uber répond toujours 400 : jamais demandé


def test_un_user_sans_plateforme_n_est_pas_interroge() -> None:
    """AXE-918 : `accounts_number` à 0, aucun nom à lire chez Rollee."""

    class AvecVides(FauxRollee):
        async def utilisateurs(self) -> list[dict[str, Any]]:
            return [*await super().utilisateurs(), {"id": "u-vide", "accounts_number": 0}]

        async def comptes(self, user_id: str) -> list[dict[str, Any]]:
            assert user_id != "u-vide", "un user sans plateforme ne doit pas être interrogé"
            return await super().comptes(user_id)

    depots = _depots(AvecVides())
    lignes = asyncio.run(passer_tenant(depots, T, False, LE))
    assert "2 non trouvé(s)" in lignes[0] and "illisible" not in " ".join(lignes)


def test_un_profil_toujours_en_500_ne_bloque_pas_le_lien_par_le_nom() -> None:
    """AXE-918 : 3 profils toujours en 500 chez Rollee (14/11). Comptés sans
    nom et signalés ; un 429, lui, reste bloquant (test plus haut)."""

    class ProfilCasse(FauxRollee):
        async def utilisateurs(self) -> list[dict[str, Any]]:
            return [*await super().utilisateurs(), {"id": "u-500"}]

        async def profil(self, compte_id: str) -> dict[str, Any]:
            if compte_id == "u-500-uber":
                raise RolleeIndisponible("GET /accounts/u-500-uber/profile : 500", 500)
            return await super().profil(compte_id)

    depots = _depots(ProfilCasse())
    lignes = asyncio.run(passer_tenant(depots, T, True, LE))
    assert ("u-nom", "nom_unique") in {(x.rollee_user_id, x.indice) for x in depots.liens.liens(T)}
    assert "1 profil(s) toujours en erreur chez Rollee" in " ".join(lignes)
    assert "illisible" not in " ".join(lignes)
