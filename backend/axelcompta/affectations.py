"""Affectation du résultat du dernier exercice clos, versement des
dividendes et paie du président, décidés par le chauffeur seul
(Louis, 2026-09-26 : c'est lui qui gère ce qu'il fait de son résultat, sur
un écran à lui).

Composition root, comme `exercices.py` : lit la situation dans le grand
livre, propose les scénarios de `closing/affectation.py`, puis écrit la
décision du chauffeur (trace append-only et journal d'audit) et l'écriture
qui solde le résultat.

Seules les sociétés à l'IS sont concernées : leurs dividendes sont imposés
à part. À l'IR, le résultat est déjà imposé chez l'associé ou l'exploitant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from axelcompta.closing.affectation import (
    Scenario,
    SituationAffectation,
    dotation_reserve_legale,
    ecriture_affectation,
    id_affectation,
    scenarios,
)
from axelcompta.closing.cloture_fiscale import soldes
from axelcompta.closing.dividendes import (
    RetenuesDividendes,
    ecriture_retenues,
    id_retenues,
    retenues,
)
from axelcompta.closing.paie import Bulletin, ecriture_bulletin, id_bulletin
from axelcompta.core.pcg import COMPTE_BANQUE
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.service import LedgerService
from axelcompta.tenants.affectations import (
    AffectationDejaDecidee,
    AffectationRepository,
    DecisionAffectation,
)
from axelcompta.tenants.exercices import ExerciceClos, ExerciceRepository
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.statuts import configuration_de

# Charges courantes pour le coussin de trésorerie : sans l'IS (695) ni les
# dotations (68), qui ne sortent pas chaque mois de la banque.
_HORS_CHARGES_COURANTES = ("695", "68")
COMPTE_REMUNERATION_NON_SALARIE = "644"


class AffectationImpossible(ValueError):
    """Pas d'affectation à décider maintenant ; le message dit pourquoi."""


@dataclass(frozen=True, slots=True)
class PropositionAffectation:
    annee_exercice: int
    situation: SituationAffectation
    reserve_legale: int
    scenarios: tuple[Scenario, ...]


def _solde(balance: dict[str, int], *prefixes: str) -> int:
    return sum(s for compte, s in balance.items() if compte.startswith(prefixes))


def _dernier_clos(dossier: Dossier, exercices: ExerciceRepository) -> ExerciceClos:
    clos = exercices.lister(dossier.id)
    if not clos:
        raise AffectationImpossible(
            "Aucun exercice n'est encore clos. Clôturez d'abord l'exercice."
        )
    return clos[-1]


def proposer(
    dossier: Dossier,
    ledger: LedgerService,
    exercices: ExerciceRepository,
    affectations: AffectationRepository,
    aujourd_hui: date,
) -> PropositionAffectation:
    configuration = configuration_de(dossier)
    if not configuration.colonne.soumis_is:
        raise AffectationImpossible(
            "À l'impôt sur le revenu, le résultat est déjà imposé chez vous. "
            "Il n'y a pas de dividendes à décider."
        )
    clos = _dernier_clos(dossier, exercices)
    annee = clos.fin.year
    grand_livre = ledger.grand_livre(dossier.id)
    # L'écriture fait foi : une décision tracée mais interrompue avant
    # l'écriture se termine en la rejouant à l'identique (`decider`).
    if any(e.id == id_affectation(dossier.id, annee) for e in grand_livre):
        raise AffectationImpossible(f"Le résultat {annee} est déjà affecté.")
    depuis_ouverture = soldes(tuple(e for e in grand_livre if e.date >= dossier.exercice_debut))
    de_l_exercice_clos = soldes(tuple(e for e in grand_livre if clos.debut <= e.date <= clos.fin))
    charges = _solde(de_l_exercice_clos, "6") - _solde(de_l_exercice_clos, *_HORS_CHARGES_COURANTES)
    situation = SituationAffectation(
        resultat=-_solde(depuis_ouverture, "120", "129"),
        capital=-_solde(depuis_ouverture, "101"),
        reserve_legale=-_solde(depuis_ouverture, "1061"),
        report_a_nouveau=-_solde(depuis_ouverture, "110", "119"),
        tresorerie=_solde(depuis_ouverture, COMPTE_BANQUE),
        dettes=sum(max(0, -_solde(depuis_ouverture, c)) for c in ("444", "44551", "457")),
        charges_mensuelles=max(0, charges) // 12,
        gerant_non_salarie=(
            configuration.compte_remuneration_dirigeant == COMPTE_REMUNERATION_NON_SALARIE
        ),
        annee_versement=aujourd_hui.year,
    )
    return PropositionAffectation(
        annee_exercice=annee,
        situation=situation,
        reserve_legale=dotation_reserve_legale(situation),
        scenarios=tuple(scenarios(situation)),
    )


def decider(
    proposition: PropositionAffectation,
    dossier: Dossier,
    scenario: str,
    dividendes: int,
    ledger: LedgerService,
    affectations: AffectationRepository,
    maintenant: datetime,
    auteur: str,
) -> Ecriture:
    """Le chauffeur retient un scénario (ou un montant à lui, `scenario` =
    « libre ») : l'écriture solde le résultat, la décision est tracée."""
    ecriture = ecriture_affectation(
        dossier.id, proposition.annee_exercice, maintenant.date(), proposition.situation, dividendes
    )
    try:
        affectations.enregistrer(
            DecisionAffectation(
                dossier_id=dossier.id,
                annee_exercice=proposition.annee_exercice,
                scenario=scenario,
                dividendes_cts=dividendes,
                reserve_legale_cts=proposition.reserve_legale,
                decide_le=maintenant,
                decide_par=auteur,
            )
        )
    except AffectationDejaDecidee:
        deja = affectations.obtenir(dossier.id, proposition.annee_exercice)
        if deja is None or deja.dividendes_cts != dividendes:
            raise
    ledger.enregistrer(ecriture)
    return ecriture


# --- Versement des dividendes décidés -----------------------------------------


@dataclass(frozen=True, slots=True)
class DividendesDecides:
    annee_exercice: int
    brut: int
    decide_le: date
    declare: RetenuesDividendes | None  # None tant que le versement n'est pas déclaré


def dividendes_decides(
    dossier: Dossier,
    ledger: LedgerService,
    exercices: ExerciceRepository,
    affectations: AffectationRepository,
) -> DividendesDecides:
    clos = _dernier_clos(dossier, exercices)
    decision = affectations.obtenir(dossier.id, clos.fin.year)
    if decision is None or decision.dividendes_cts <= 0:
        raise AffectationImpossible("Aucun dividende n'a été décidé sur le dernier exercice clos.")
    cible = id_retenues(dossier.id, decision.annee_exercice)
    declare = next((e for e in ledger.grand_livre(dossier.id) if e.id == cible), None)
    detail = None
    if declare is not None:
        # L'écriture ne garde que le total : la dispense se lit dans l'écart
        # avec le total sans dispense.
        total = sum(ligne.montant.centimes for ligne in declare.lignes if ligne.compte == "4423")
        sans_dispense = retenues(decision.dividendes_cts, declare.date, dispense_prelevement=False)
        dispense = total != sans_dispense.total_retenu
        detail = retenues(decision.dividendes_cts, declare.date, dispense_prelevement=dispense)
    return DividendesDecides(
        annee_exercice=decision.annee_exercice,
        brut=decision.dividendes_cts,
        decide_le=decision.decide_le.date(),
        declare=detail,
    )


def declarer_versement(
    decides: DividendesDecides,
    dossier: Dossier,
    ledger: LedgerService,
    verse_le: date,
    dispense_prelevement: bool,
    aujourd_hui: date,
) -> RetenuesDividendes:
    """Le chauffeur déclare avoir versé ses dividendes : les retenues à la
    source passent en 4423, la 2777 est à déposer avant le 15 du mois suivant."""
    if decides.declare is not None:
        raise AffectationImpossible("Ce versement est déjà déclaré.")
    if not decides.decide_le <= verse_le <= aujourd_hui:
        raise AffectationImpossible(
            "La date de versement doit suivre la décision, et elle ne peut pas être dans le futur."
        )
    detail = retenues(decides.brut, verse_le, dispense_prelevement)
    ledger.enregistrer(ecriture_retenues(dossier.id, decides.annee_exercice, detail))
    return detail


# --- Paie du président assimilé salarié ----------------------------------------


def enregistrer_bulletin(dossier: Dossier, ledger: LedgerService, bulletin: Bulletin) -> Ecriture:
    if not configuration_de(dossier).paie_par_bulletin:
        raise AffectationImpossible("Seul un président assimilé salarié a un bulletin de paie.")
    if any(e.id == id_bulletin(dossier.id, bulletin.mois) for e in ledger.grand_livre(dossier.id)):
        raise AffectationImpossible(f"Le bulletin de {bulletin.mois} est déjà enregistré.")
    ecriture = ecriture_bulletin(dossier.id, bulletin)
    ledger.enregistrer(ecriture)
    return ecriture


def bulletins_enregistres(dossier: Dossier, ledger: LedgerService) -> tuple[Ecriture, ...]:
    grand_livre = ledger.grand_livre(dossier.id)
    return tuple(e for e in grand_livre if (e.reference_piece or "").startswith("BULLETIN-"))
