"""Passage d'un dossier à l'exercice suivant (doc 06 §2, §5, §7).

Composition root, comme `taches.py`. Deux temps :
1. `preparer_passage` ne touche à rien : vérifie que l'exercice est terminé
   et qu'aucune opération n'attend de décision, calcule les écritures
   d'inventaire (TVA, IS), l'écriture d'à-nouveaux et la configuration du
   nouvel exercice (avenant de régime en vigueur, sortie de la franchise de
   TVA si le seuil de base a été dépassé) ;
2. `executer_passage` l'écrit : écritures en base (append-only), exercice
   clos dans l'historique avec l'attestation acceptée, dossier ouvert sur
   le nouvel exercice.

L'exécution est rejouable : si elle s'interrompt, la relancer n'ajoute ni
écriture ni exercice en double (identifiants stables) et termine le travail.
Qui clôt (Louis, 2026-09-26) : **le chauffeur, et lui seul**, légalement
responsable de sa comptabilité. L'automatisation prépare et le relance
(`axelcompta.taches`) ; il valide depuis son écran en acceptant
l'attestation de `attestation(...)`, gardée mot pour mot avec son identité
(`exercices_clos`, journal d'audit). Le gestionnaire n'a aucun droit sur les
comptes. Sans décision du chauffeur, rien ne se passe.

La ligne de commande ne fait donc que simuler, pour vérifier un dossier :

    python -m axelcompta.exercices --dossier <dossier_id>
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from axelcompta.closing.cloture_fiscale import (
    chiffre_affaires_ht,
    ecritures_de_cloture,
    ecritures_exercice,
    hors_inventaire,
)
from axelcompta.closing.models import ParametresCloture, ProvisionCloture
from axelcompta.closing.ouverture import ecriture_a_nouveaux
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie
from axelcompta.tenants.avenants import AvenantRegime, regime_pour_exercice
from axelcompta.tenants.avenants_postgres import PostgresAvenantRegimeRepository
from axelcompta.tenants.exercices import ExerciceClos, ExerciceDejaClos, ExerciceRepository
from axelcompta.tenants.franchise_tva import EtatFranchise, MillesimeInconnu, suivre_franchise
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository
from axelcompta.tenants.statuts import RegimeTva, configuration_de
from axelcompta.workflow.decisions import DecisionRepository
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.notifications import ecritures_a_trancher
from axelcompta.workflow.revue import appliquer_decisions


class PassageRefuse(ValueError):
    """L'exercice ne peut pas être clos maintenant ; le message dit pourquoi."""


@dataclass(frozen=True, slots=True)
class PassageExercice:
    avant: Dossier
    apres: Dossier
    ecritures: tuple[Ecriture, ...]  # inventaire puis à-nouveaux, à ajouter
    changements: tuple[str, ...]


def preparer_passage(
    dossier: Dossier,
    ledger: LedgerService,
    decisions: DecisionRepository,
    avenants: tuple[AvenantRegime, ...],
    aujourd_hui: date,
    provisions: tuple[ProvisionCloture, ...] = (),
) -> PassageExercice:
    fin = dossier.fin_exercice()
    if fin >= aujourd_hui:
        raise PassageRefuse(f"l'exercice se termine le {fin:%d/%m/%Y}, il n'est pas terminé")
    en_attente = ecritures_a_trancher(ledger, decisions, dossier.id)
    if en_attente:
        raise PassageRefuse(f"{len(en_attente)} opération(s) attendent encore une décision")
    configuration = configuration_de(dossier)
    colonne = configuration.colonne
    tranchees = appliquer_decisions(
        ledger.grand_livre(dossier.id),
        decisions.lister_decisions(dossier.id),
        configuration.comptes_categories_statut(),
        charger_compte_par_categorie(),
    )
    parametres = ParametresCloture(
        exercice_debut=dossier.exercice_debut,
        exercice_fin=fin,
        forme_juridique=dossier.forme_juridique,
        identite=dossier.identite,
        soumis_is=colonne.soumis_is,
        associes=colonne.associes,
        provisions=provisions,
    )
    de_l_exercice = hors_inventaire(
        dossier.id, ecritures_exercice(tranchees, parametres), parametres
    )
    inventaire = ecritures_de_cloture(dossier.id, de_l_exercice, parametres)
    ouverture = fin + timedelta(days=1)
    a_nouveaux = ecriture_a_nouveaux(dossier.id, de_l_exercice + inventaire, ouverture)
    apres, changements = _configuration_suivante(dossier, avenants, tranchees, ouverture)
    configuration_de(apres)
    ecritures = inventaire + ((a_nouveaux,) if a_nouveaux else ())
    return PassageExercice(dossier, apres, ecritures, changements)


def _configuration_suivante(
    dossier: Dossier,
    avenants: tuple[AvenantRegime, ...],
    ecritures: tuple[Ecriture, ...],
    ouverture: date,
) -> tuple[Dossier, tuple[str, ...]]:
    changements: list[str] = []
    regime, option = regime_pour_exercice(dossier, avenants, ouverture.year)
    if regime != dossier.regime_imposition:
        changements.append(f"régime d'imposition : {dossier.regime_imposition} → {regime}")
    regime_tva, recettes = dossier.regime_tva, dossier.tva_recettes_regime
    if configuration_de(dossier).regime_tva is RegimeTva.FRANCHISE:
        annee = ouverture.year - 1
        try:
            suivi = suivre_franchise(chiffre_affaires_ht(ecritures, annee), annee)
        except MillesimeInconnu as exc:
            raise PassageRefuse(str(exc)) from exc
        if suivi.etat in (EtatFranchise.SEUIL_BASE_DEPASSE, EtatFranchise.SEUIL_MAJORE_DEPASSE):
            regime_tva, recettes = RegimeTva.REEL_NORMAL.value, "assujetti_taux_reduit"
            changements.append("TVA : sortie de la franchise en base, réel normal")
    apres = dataclasses.replace(
        dossier,
        exercice_debut=ouverture,
        exercice_fin=None,
        regime_imposition=regime,
        option_ir_debut=option,
        regime_tva=regime_tva,
        tva_recettes_regime=recettes,
    )
    return apres, tuple(changements)


def attestation(dossier: Dossier, signataire: str) -> str:
    """Le texte que le chauffeur accepte pour clore. Le serveur le produit,
    le client le renvoie tel quel : on garde la preuve de ce qu'il a lu."""
    fin = dossier.fin_exercice()
    return (
        f"Je soussigné(e) {signataire}, dirigeant(e) de {dossier.nom}, ai relu les comptes "
        f"de l'exercice du {dossier.exercice_debut:%d/%m/%Y} au {fin:%d/%m/%Y} et j'en valide "
        "la clôture. AxeLCompta a préparé les écritures ; je reste seul(e) responsable de "
        "ma comptabilité et de ma décision."
    )


def executer_passage(
    passage: PassageExercice,
    ledger: LedgerService,
    dossiers: DossierRepository,
    exercices: ExerciceRepository,
    maintenant: datetime,
    auteur: str,
    texte_attestation: str | None = None,
) -> None:
    avant = passage.avant
    deja = {e.id for e in ledger.grand_livre(avant.id)}
    for ecriture in passage.ecritures:
        if ecriture.id not in deja:
            ledger.enregistrer(ecriture)
    try:
        exercices.enregistrer(
            ExerciceClos(
                dossier_id=avant.id,
                debut=avant.exercice_debut,
                fin=avant.fin_exercice(),
                clos_le=maintenant,
                clos_par=auteur,
                changements=passage.changements,
                attestation=texte_attestation,
            )
        )
    except ExerciceDejaClos:
        pass  # reprise après une interruption : l'historique est déjà là
    dossiers.ouvrir_exercice(passage.apres)


def _afficher(passage: PassageExercice) -> None:
    avant, apres = passage.avant, passage.apres
    print(f"{avant.id} : exercice {avant.exercice_debut} → {avant.fin_exercice()} à clore")
    for ecriture in passage.ecritures:
        print(f"  écriture {ecriture.reference_piece} ({len(ecriture.lignes)} lignes)")
    print(f"  nouvel exercice à partir du {apres.exercice_debut}")
    for changement in passage.changements or ("configuration inchangée",):
        print(f"  {changement}")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--dossier", required=True)
    args = parseur.parse_args()

    engine = engine_depuis_env()
    dossier = PostgresDossierRepository(engine).obtenir(DossierId(args.dossier))
    if dossier is None:
        print(f"Dossier inconnu : {args.dossier}", file=sys.stderr)
        return 1
    try:
        passage = preparer_passage(
            dossier,
            PostgresLedgerService(engine),
            PostgresDecisionRepository(engine),
            PostgresAvenantRegimeRepository(engine).lister(dossier.id),
            datetime.now(UTC).date(),
        )
    except PassageRefuse as exc:
        print(f"{dossier.id} : passage refusé, {exc}", file=sys.stderr)
        return 1
    _afficher(passage)
    print("Simulation : seule la validation du chauffeur, depuis son écran, clôt l'exercice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
