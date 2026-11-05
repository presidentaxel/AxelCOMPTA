"""Avenants de régime (doc 06 §7) : fin de l'option IR, alertes N-1/N,
bascule enregistrée d'avance, jamais rétroactive."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.avenants import (
    AUTEUR_SYSTEME,
    AvenantRegime,
    InMemoryAvenantRegimeRepository,
    MotifAvenant,
    a_venir,
    alerte_option_ir,
    programmer_bascule,
    programmer_bascules,
    rang_option_ir,
    regime_pour_exercice,
)
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.statuts import RegimeImposition, configuration_de

MAINTENANT = datetime(2026, 9, 26, 12, 0)


def _dossier_option_ir(exercice: int, debut_option: int = 2022) -> Dossier:
    return Dossier(
        id=DossierId("d1"),
        tenant_id=TenantId("t"),
        forme_juridique="SASU",
        regime_imposition="option_IR",
        regime_tva="reel_normal",
        nom="d1",
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(exercice, 1, 1),
        option_ir_debut=debut_option,
    )


def test_rang_de_l_exercice_dans_l_option() -> None:
    assert rang_option_ir(_dossier_option_ir(2022)) == 1
    assert rang_option_ir(_dossier_option_ir(2026)) == 5
    is_ = dataclasses.replace(
        _dossier_option_ir(2026), regime_imposition="IS", option_ir_debut=None
    )
    assert rang_option_ir(is_) is None


def test_alerte_seulement_aux_deux_derniers_exercices() -> None:
    assert alerte_option_ir(_dossier_option_ir(2024)) is None
    avant_derniere = alerte_option_ir(_dossier_option_ir(2025))
    derniere = alerte_option_ir(_dossier_option_ir(2026))
    assert avant_derniere is not None and "Avant-dernier" in avant_derniere
    assert derniere is not None and "Dernier exercice" in derniere
    assert "l'impôt sur les sociétés pour l'exercice 2027" in derniere


def test_la_bascule_ne_se_programme_qu_au_dernier_exercice() -> None:
    assert programmer_bascule(_dossier_option_ir(2025), (), MAINTENANT) is None

    avenant = programmer_bascule(_dossier_option_ir(2026), (), MAINTENANT)

    assert avenant is not None
    assert (avenant.exercice_effet, avenant.regime_imposition) == (2027, RegimeImposition.IS)
    assert (avenant.motif, avenant.enregistre_par) == (MotifAvenant.FIN_OPTION_IR, AUTEUR_SYSTEME)


def test_programmer_les_bascules_est_idempotent() -> None:
    depot = InMemoryAvenantRegimeRepository()
    dossiers = (_dossier_option_ir(2026),)

    assert len(programmer_bascules(dossiers, depot, MAINTENANT)) == 1
    assert programmer_bascules(dossiers, depot, MAINTENANT) == []
    assert len(depot.lister(DossierId("d1"))) == 1


def test_une_renonciation_anterieure_rend_la_bascule_inutile() -> None:
    renonciation = AvenantRegime(
        id="r1",
        dossier_id=DossierId("d1"),
        exercice_effet=2026,
        regime_imposition=RegimeImposition.IS,
        option_ir_debut=None,
        motif=MotifAvenant.RENONCIATION_OPTION_IR,
        enregistre_le=MAINTENANT,
        enregistre_par="u1",
    )
    assert programmer_bascule(_dossier_option_ir(2026), (renonciation,), MAINTENANT) is None


def test_le_regime_d_un_exercice_suit_l_avenant_en_vigueur_sans_retroactivite() -> None:
    dossier = _dossier_option_ir(2026)
    avenant = programmer_bascule(dossier, (), MAINTENANT)
    assert avenant is not None
    avenants = (avenant,)

    assert regime_pour_exercice(dossier, avenants, 2026) == ("option_IR", 2022)
    assert regime_pour_exercice(dossier, avenants, 2027) == ("IS", None)
    assert a_venir(dossier, avenants) == avenants
    # L'exercice suivant, configuré avec le régime de l'avenant, est valide.
    suivant = dataclasses.replace(
        dossier, exercice_debut=date(2027, 1, 1), regime_imposition="IS", option_ir_debut=None
    )
    assert configuration_de(suivant).colonne.cle == "societe_is"
