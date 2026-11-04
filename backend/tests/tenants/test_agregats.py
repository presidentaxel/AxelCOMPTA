from __future__ import annotations

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants import agregats
from axelcompta.tenants.agregats import AgregatStocke, InMemoryAgregatsRepository

TENANT = TenantId("t")
KARIM = DossierId("karim")
VALEUR = AgregatStocke(120_000, 45_000, 75_000, "2026-01-01", "2026-12-31", None)


def test_sans_ligne_le_dossier_est_absent_du_resultat() -> None:
    assert InMemoryAgregatsRepository().lire([KARIM]) == {}


def test_une_valeur_enregistree_se_relit() -> None:
    depot = InMemoryAgregatsRepository()
    assert depot.enregistrer(TENANT, KARIM, VALEUR, None)
    assert depot.lire([KARIM])[KARIM].valeur == VALEUR


def test_une_ligne_deja_la_refuse_un_enregistrement_qui_croyait_qu_elle_n_existait_pas() -> None:
    depot = InMemoryAgregatsRepository()
    depot.invalider(KARIM)

    assert not depot.enregistrer(TENANT, KARIM, VALEUR, None)
    assert depot.lire([KARIM])[KARIM].valeur is None


def test_invalider_perime_la_ligne_et_fait_monter_la_version() -> None:
    depot = InMemoryAgregatsRepository()
    depot.enregistrer(TENANT, KARIM, VALEUR, None)
    avant = depot.lire([KARIM])[KARIM].version

    depot.invalider(KARIM)

    apres = depot.lire([KARIM])[KARIM]
    assert apres.valeur is None
    assert apres.version == avant + 1


def test_un_enregistrement_fait_sur_une_version_depassee_est_refuse() -> None:
    depot = InMemoryAgregatsRepository()
    depot.enregistrer(TENANT, KARIM, VALEUR, None)
    version_lue = depot.lire([KARIM])[KARIM].version
    depot.invalider(KARIM)

    assert not depot.enregistrer(TENANT, KARIM, VALEUR, version_lue)
    assert depot.lire([KARIM])[KARIM].valeur is None


def test_recalculer_sur_la_version_courante_remet_la_ligne_a_jour() -> None:
    depot = InMemoryAgregatsRepository()
    depot.enregistrer(TENANT, KARIM, VALEUR, None)
    depot.invalider(KARIM)
    version = depot.lire([KARIM])[KARIM].version

    assert depot.enregistrer(TENANT, KARIM, VALEUR, version)
    assert depot.lire([KARIM])[KARIM].valeur == VALEUR


def test_une_autre_version_de_calcul_ignore_les_lignes(monkeypatch: pytest.MonkeyPatch) -> None:
    depot = InMemoryAgregatsRepository()
    depot.enregistrer(TENANT, KARIM, VALEUR, None)
    monkeypatch.setattr(agregats, "VERSION_CALCUL", agregats.VERSION_CALCUL + 1)

    ligne = depot.lire([KARIM])[KARIM]
    assert ligne.valeur is None
    assert depot.enregistrer(TENANT, KARIM, VALEUR, ligne.version)
    assert depot.lire([KARIM])[KARIM].valeur == VALEUR


def test_les_dossiers_ne_se_perimment_pas_entre_eux() -> None:
    depot = InMemoryAgregatsRepository()
    sophie = DossierId("sophie")
    depot.enregistrer(TENANT, KARIM, VALEUR, None)
    depot.enregistrer(TENANT, sophie, VALEUR, None)

    depot.invalider(KARIM)

    lues = depot.lire([KARIM, sophie])
    assert lues[KARIM].valeur is None
    assert lues[sophie].valeur == VALEUR
