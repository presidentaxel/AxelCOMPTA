"""AXE-849 : lecture des registres officiels et écarts avec la déclaration."""

from __future__ import annotations

import copy
import dataclasses
from datetime import date
from typing import Any

import pytest

from axelcompta.core.errors import Introuvable
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.demo_identites import IDENTITE_KARIM
from axelcompta.tenants.confirmation import raison_ambiguite
from axelcompta.tenants.models import Dossier, EcartRegistre
from axelcompta.tenants.registres import (
    CHAMP_CAPITAL,
    CHAMP_DIRIGEANT,
    CHAMP_ETAT,
    CHAMP_FORME,
    TranchageRefuse,
    combiner,
    ecarts,
    fiche_insee,
    fiche_rne,
    phrase,
    phrase_gestionnaire,
    restants,
    trancher,
)
from axelcompta.tenants.registres_json import fiche_depuis_json, fiche_vers_json
from tests.tenants.registres_fixtures import (
    INSEE_SIREN,
    INSEE_SIRET,
    RNE_SAS_PLURIPERSONNELLE,
    SIREN,
)

LE = date(2026, 11, 10)


def _dossier(**valeurs: object) -> Dossier:
    base = Dossier(
        id=DossierId("DIGI_1"),
        tenant_id=TenantId("T"),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="reel_normal",
        nom="AMRANI VTC",
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(2026, 1, 1),
        identite=IDENTITE_KARIM,
        siren=SIREN,
    )
    return dataclasses.replace(base, **valeurs)  # type: ignore[arg-type]


def _rne(**description: object) -> dict[str, Any]:
    reponse = copy.deepcopy(RNE_SAS_PLURIPERSONNELLE)
    reponse["formality"]["content"]["personneMorale"]["identite"]["description"].update(description)
    return reponse


def test_insee_lu_avec_le_siege() -> None:
    fiche = fiche_insee(INSEE_SIREN, INSEE_SIRET, SIREN, LE)
    assert fiche is not None
    assert (fiche.denomination, fiche.categorie_juridique, fiche.cessee) == (
        "AMRANI VTC",
        "5710",
        False,
    )
    assert fiche.siege is not None and fiche.siege.code_postal == "75011"
    assert (fiche.date_creation, fiche.code_naf) == (date(2024, 3, 13), "49.32Z")


def test_insee_d_un_autre_siren_n_est_pas_lu() -> None:
    assert fiche_insee(INSEE_SIREN, INSEE_SIRET, "111111111", LE) is None


def test_rne_leve_l_ambiguite_sas_sasu_et_lit_capital_et_dirigeants() -> None:
    plusieurs = fiche_rne(RNE_SAS_PLURIPERSONNELLE, SIREN, LE)
    unique = fiche_rne(_rne(indicateurAssocieUnique=True), SIREN, LE)
    assert plusieurs is not None and unique is not None
    assert (plusieurs.forme_juridique, unique.forme_juridique) == ("SAS", "SASU")
    assert plusieurs.capital_cts == 100000
    assert plusieurs.dirigeants == ("Karim AMRANI",)


def test_sans_indicateur_d_associe_unique_la_forme_reste_inconnue() -> None:
    reponse = _rne()
    del reponse["formality"]["content"]["personneMorale"]["identite"]["description"][
        "indicateurAssocieUnique"
    ]
    fiche = fiche_rne(reponse, SIREN, LE)
    assert fiche is not None and fiche.forme_juridique is None


@pytest.mark.parametrize("capital", ["mille", -5, True, None, 10.005])
def test_un_capital_illisible_reste_inconnu(capital: object) -> None:
    fiche = fiche_rne(_rne(montantCapital=capital), SIREN, LE)
    assert fiche is not None and fiche.capital_cts is None


def test_combiner_prend_le_rne_pour_la_forme_et_l_insee_pour_l_etat() -> None:
    fiche = combiner(
        fiche_insee(INSEE_SIREN, INSEE_SIRET, SIREN, LE),
        fiche_rne(RNE_SAS_PLURIPERSONNELLE, SIREN, LE),
    )
    assert fiche is not None
    assert (fiche.sources, fiche.forme_juridique, fiche.cessee) == (("insee", "rne"), "SAS", False)
    assert fiche_depuis_json(fiche_vers_json(fiche)) == fiche


def test_l_insee_seul_ne_tranche_pas_sas_contre_sasu() -> None:
    fiche = combiner(fiche_insee(INSEE_SIREN, INSEE_SIRET, SIREN, LE), None)
    assert fiche is not None and fiche.forme_juridique == "SAS"
    assert ecarts(_dossier(), dataclasses.replace(fiche, forme_juridique=None)) == ()


def test_critere_declare_sasu_registre_sas_un_ecart_en_clair() -> None:
    fiche = fiche_rne(RNE_SAS_PLURIPERSONNELLE, SIREN, LE)
    assert fiche is not None
    trouves = ecarts(_dossier(), fiche)
    assert trouves == (EcartRegistre(CHAMP_FORME, "SASU", "SAS"),)
    assert phrase(trouves[0]) == "Forme déclarée SASU, forme au registre SAS."


def test_sans_ecart_rien_de_plus() -> None:
    fiche = fiche_rne(_rne(indicateurAssocieUnique=True), SIREN, LE)
    assert fiche is not None
    assert ecarts(_dossier(), fiche) == ()
    assert raison_ambiguite(_dossier()) is None


def test_capital_et_dirigeant_differents() -> None:
    fiche = fiche_rne(_rne(indicateurAssocieUnique=True, montantCapital="5000"), SIREN, LE)
    assert fiche is not None
    fiche = dataclasses.replace(fiche, dirigeants=("Paul MARTIN",))
    champs = [e.champ for e in ecarts(_dossier(), fiche)]
    assert champs == [CHAMP_CAPITAL, CHAMP_DIRIGEANT]
    capital = ecarts(_dossier(), fiche)[0]
    assert (capital.declare, capital.officiel) == ("1 000 €", "5 000 €")
    assert (
        phrase_gestionnaire(ecarts(_dossier(), fiche)[1])
        == "Dirigeant différent de celui du registre."
    )


def test_une_societe_cessee_passe_en_premier_et_bloque() -> None:
    fiche = fiche_rne(RNE_SAS_PLURIPERSONNELLE, SIREN, LE)
    assert fiche is not None
    trouves = ecarts(_dossier(), dataclasses.replace(fiche, cessee=True))
    assert trouves[0].champ == CHAMP_ETAT
    raison = raison_ambiguite(_dossier(ecarts_registre=trouves, a_confirmer=("forme_juridique",)))
    assert raison is not None and raison.startswith("La société est cessée au registre")


def test_un_ecart_bloque_la_cloture_et_la_liasse() -> None:
    ecart = EcartRegistre(CHAMP_FORME, "SASU", "SAS")
    raison = raison_ambiguite(_dossier(ecarts_registre=(ecart,)))
    assert (
        raison
        == "Le registre ne dit pas la même chose. Forme déclarée SASU, forme au registre SAS."
    )


def test_un_ecart_tranche_ne_revient_que_si_le_registre_change() -> None:
    ecart = EcartRegistre(CHAMP_FORME, "SASU", "SAS")
    assert restants((ecart,), {CHAMP_FORME: "SAS"}) == ()
    assert restants((ecart,), {CHAMP_FORME: "SARL"}) == (ecart,)


def test_retenir_la_forme_du_registre_la_pose() -> None:
    ecart = EcartRegistre(CHAMP_FORME, "SASU", "SAS")
    tranche, reste, forme = trancher(_dossier(ecarts_registre=(ecart,)), CHAMP_FORME, "officielle")
    assert (tranche, reste, forme) == (ecart, (), "SAS")
    assert trancher(_dossier(ecarts_registre=(ecart,)), CHAMP_FORME, "declaree")[2] is None


def test_trancher_un_ecart_absent_ou_cessee_officielle_est_refuse() -> None:
    with pytest.raises(Introuvable):
        trancher(_dossier(), CHAMP_FORME, "officielle")
    cessee = EcartRegistre(CHAMP_ETAT, "active", "cessée")
    with pytest.raises(TranchageRefuse):
        trancher(_dossier(ecarts_registre=(cessee,)), CHAMP_ETAT, "officielle")
