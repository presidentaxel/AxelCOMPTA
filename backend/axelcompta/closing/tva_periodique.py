"""TVA en cours d'année : CA3 de chaque période, échéance, liquidation (AXE-805).

Au réel normal, la CA3 se dépose chaque mois (chaque trimestre si la TVA due
sur l'année est inférieure à 4 000 €, art. 287-1 CGI). La période et le jour
d'échéance sont des paramètres du dossier : le jour dépend du SIREN et de la
forme (calendrier DGFiP), il se règle, il ne se devine pas.

La CA3 d'une période se lit dans les mouvements des comptes de TVA datés de
la période :
* TVA collectée : crédits nets des 4457 (dont l'autoliquidation d'une
  commission Bolt, code `autoliquidation`) ;
* TVA déductible : débits nets des 4456, hors 44567 (le crédit à reporter
  n'est pas une TVA de la période) ;
* crédit reporté : le crédit de la période précédente (ligne 22).

Déclarer la période passe l'écriture de liquidation : les 4457 et 4456 de
la période sont soldés vers 44551 (TVA à décaisser) ou 44567 (crédit à
reporter). La liasse annuelle relit les mouvements **hors** ces
liquidations : elle reprend la somme des périodes.

Pur : aucune I/O.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.tenants.models import Dossier

Periodicite = Literal["mensuelle", "trimestrielle"]
PERIODICITES: tuple[Periodicite, ...] = ("mensuelle", "trimestrielle")
COMPTE_TVA_A_DECAISSER = "44551"
COMPTE_CREDIT_A_REPORTER = "44567"
CODE_AUTOLIQUIDATION = "autoliquidation"
_MARQUE_LIQUIDATION = ":tva-periode-"


class ParametresTvaInvalides(SaisieInvalide):
    """Périodicité inconnue, ou jour d'échéance hors 1-31."""


@dataclass(frozen=True, slots=True)
class PeriodeTva:
    debut: date
    fin: date

    @property
    def cle(self) -> str:
        """« 2026-03 » pour un mois, « 2026-T1 » pour un trimestre."""
        if self.debut.month == self.fin.month:
            return f"{self.debut.year}-{self.debut.month:02d}"
        return f"{self.debut.year}-T{(self.debut.month - 1) // 3 + 1}"

    def contient(self, jour: date) -> bool:
        return self.debut <= jour <= self.fin


@dataclass(frozen=True, slots=True)
class LigneCa3:
    numero: str  # numéro de ligne du formulaire 3310-CA3, ou « » si informatif
    libelle: str
    centimes: int


@dataclass(frozen=True, slots=True)
class Ca3Periode:
    periode: PeriodeTva
    collectee: int
    autoliquidee: int  # comprise dans `collectee`
    deductible: int
    credit_anterieur: int
    due: int  # ligne 28, jamais négative
    credit: int  # ligne 25, jamais négatif

    @property
    def lignes(self) -> tuple[LigneCa3, ...]:
        """Ce que le chauffeur recopie sur impots.gouv, dans l'ordre du formulaire."""
        total_deductible = self.deductible + self.credit_anterieur
        return (
            LigneCa3("16", "Total de la TVA brute due", self.collectee),
            LigneCa3(
                "", "dont TVA autoliquidée (commission d'une plateforme de l'UE)", self.autoliquidee
            ),
            LigneCa3("20", "TVA déductible sur autres biens et services", self.deductible),
            LigneCa3("22", "Report du crédit de la déclaration précédente", self.credit_anterieur),
            LigneCa3("23", "Total de la TVA déductible", total_deductible),
            LigneCa3("25", "Crédit de TVA", self.credit),
            LigneCa3("28", "TVA nette due", self.due),
        )


def verifier_parametres(periodicite: str, jour_echeance: int) -> Periodicite:
    if periodicite not in PERIODICITES:
        raise ParametresTvaInvalides(f"Périodicité inconnue : {periodicite}")
    if not 1 <= jour_echeance <= 31:
        raise ParametresTvaInvalides("Le jour d'échéance est entre 1 et 31.")
    return "mensuelle" if periodicite == "mensuelle" else "trimestrielle"


def periodes(debut: date, fin: date, periodicite: Periodicite) -> tuple[PeriodeTva, ...]:
    """Les périodes civiles qui recouvrent [debut, fin], bornées à l'exercice.
    Un trimestre suit le calendrier (janvier-mars…), comme la DGFiP."""
    pas = 1 if periodicite == "mensuelle" else 3
    mois = debut.month - (debut.month - 1) % pas
    annee = debut.year
    trouvees: list[PeriodeTva] = []
    for _ in range(40):  # borne : un exercice dure au plus 24 mois
        premier = date(annee, mois, 1)
        if premier > fin:
            break
        dernier_mois = mois + pas - 1
        fin_periode = date(annee, dernier_mois, calendar.monthrange(annee, dernier_mois)[1])
        trouvees.append(PeriodeTva(max(premier, debut), min(fin_periode, fin)))
        mois += pas
        if mois > 12:
            mois, annee = mois - 12, annee + 1
    return tuple(trouvees)


def echeance(periode: PeriodeTva, jour: int) -> date:
    """Le `jour` du mois qui suit la fin de la période (borné au dernier jour)."""
    annee, mois = periode.fin.year, periode.fin.month + 1
    if mois > 12:
        annee, mois = annee + 1, 1
    return date(annee, mois, min(jour, calendar.monthrange(annee, mois)[1]))


def id_liquidation(dossier_id: DossierId, periode: PeriodeTva) -> EcritureId:
    return EcritureId(f"{dossier_id}{_MARQUE_LIQUIDATION}{periode.cle}")


def est_liquidation_periodique(ecriture: Ecriture) -> bool:
    return _MARQUE_LIQUIDATION in ecriture.id


def _mouvements(ecritures: Iterable[Ecriture], periode: PeriodeTva) -> dict[tuple[str, bool], int]:
    """Solde débiteur (positif) par (compte de TVA, autoliquidation ?)."""
    soldes: dict[tuple[str, bool], int] = {}
    for ecriture in ecritures:
        if not periode.contient(ecriture.date) or est_liquidation_periodique(ecriture):
            continue
        for ligne in ecriture.lignes:
            if not ligne.compte.startswith(("4456", "4457")):
                continue
            if ligne.compte == COMPTE_CREDIT_A_REPORTER:
                continue
            signe = 1 if ligne.sens is Sens.DEBIT else -1
            cle = (ligne.compte, ligne.code_tva == CODE_AUTOLIQUIDATION)
            soldes[cle] = soldes.get(cle, 0) + signe * ligne.montant.centimes
    return soldes


def ca3_periode(
    ecritures: Sequence[Ecriture], periode: PeriodeTva, credit_anterieur: int = 0
) -> Ca3Periode:
    soldes = _mouvements(ecritures, periode)
    collectee = -sum(s for (c, _a), s in soldes.items() if c.startswith("4457"))
    autoliquidee = -sum(s for (c, a), s in soldes.items() if c.startswith("4457") and a)
    deductible = sum(s for (c, _a), s in soldes.items() if c.startswith("4456"))
    net = collectee - deductible - credit_anterieur
    return Ca3Periode(
        periode=periode,
        collectee=collectee,
        autoliquidee=autoliquidee,
        deductible=deductible,
        credit_anterieur=credit_anterieur,
        due=max(net, 0),
        credit=max(-net, 0),
    )


def ca3_des_periodes(
    ecritures: Sequence[Ecriture], periodes_tva: Sequence[PeriodeTva], credit_initial: int = 0
) -> tuple[Ca3Periode, ...]:
    """Chaque période reprend le crédit de la précédente (ligne 22)."""
    resultats: list[Ca3Periode] = []
    credit = credit_initial
    for periode in periodes_tva:
        ca3 = ca3_periode(ecritures, periode, credit)
        resultats.append(ca3)
        credit = ca3.credit
    return tuple(resultats)


def _ligne(compte: str, solde_debiteur: int) -> LigneEcriture:
    """La ligne qui solde `solde_debiteur` sur `compte`."""
    sens = Sens.CREDIT if solde_debiteur > 0 else Sens.DEBIT
    return LigneEcriture(compte, sens, Money(abs(solde_debiteur)))


def ecriture_liquidation(
    dossier_id: DossierId, ecritures: Sequence[Ecriture], ca3: Ca3Periode
) -> Ecriture | None:
    """Solde la TVA de la période vers 44551 (à décaisser) ou 44567 (crédit
    à reporter) ; consomme le crédit reporté. `None` si rien à liquider."""
    par_compte: dict[str, int] = {}
    for (compte, _auto), solde in _mouvements(ecritures, ca3.periode).items():
        par_compte[compte] = par_compte.get(compte, 0) + solde
    lignes = [_ligne(compte, solde) for compte, solde in sorted(par_compte.items()) if solde]
    if ca3.credit_anterieur:
        lignes.append(
            LigneEcriture(COMPTE_CREDIT_A_REPORTER, Sens.CREDIT, Money(ca3.credit_anterieur))
        )
    if ca3.due:
        lignes.append(LigneEcriture(COMPTE_TVA_A_DECAISSER, Sens.CREDIT, Money(ca3.due)))
    if ca3.credit:
        lignes.append(LigneEcriture(COMPTE_CREDIT_A_REPORTER, Sens.DEBIT, Money(ca3.credit)))
    if not lignes:
        return None
    return Ecriture(
        id=id_liquidation(dossier_id, ca3.periode),
        dossier_id=dossier_id,
        journal=Journal.OD,
        date=ca3.periode.fin,
        libelle=f"Liquidation de la TVA {ca3.periode.cle}",
        reference_piece=f"CA3-{ca3.periode.cle}",
        lignes=tuple(lignes),
    )


PREFIXE_PREUVE = "tva_ca3_"


def type_preuve(periode: PeriodeTva) -> str:
    """Type du document gardé dans `documents_signes` quand le chauffeur
    déclare avoir déposé la CA3 de la période."""
    return f"{PREFIXE_PREUVE}{periode.cle}"


@dataclass(frozen=True, slots=True)
class EtatPeriode:
    ca3: Ca3Periode
    echeance: date | None
    declaree: bool
    a_traiter: int  # opérations de la période encore au compte d'attente


def periodes_du_dossier(dossier: Dossier) -> tuple[PeriodeTva, ...]:
    if dossier.tva_periodicite not in PERIODICITES:
        return ()
    periodicite: Periodicite = (
        "mensuelle" if dossier.tva_periodicite == "mensuelle" else "trimestrielle"
    )
    return periodes(dossier.exercice_debut, dossier.fin_exercice(), periodicite)


def etats_tva(
    dossier: Dossier,
    ecritures: Sequence[Ecriture],
    dates_a_traiter: Iterable[date],
    declarees: Iterable[str],
) -> tuple[EtatPeriode, ...]:
    """Chaque période de l'exercice : sa CA3, son échéance, si elle est
    déclarée, et combien d'opérations attendent encore une décision."""
    a_traiter = list(dates_a_traiter)
    deja = set(declarees)
    jour = dossier.tva_jour_echeance
    return tuple(
        EtatPeriode(
            ca3=ca3,
            echeance=echeance(ca3.periode, jour) if jour else None,
            declaree=type_preuve(ca3.periode) in deja,
            a_traiter=sum(1 for d in a_traiter if ca3.periode.contient(d)),
        )
        for ca3 in ca3_des_periodes(ecritures, periodes_du_dossier(dossier))
    )


def prochaine_a_declarer(
    periodes_tva: Sequence[PeriodeTva], declarees: Iterable[str], aujourd_hui: date
) -> PeriodeTva | None:
    """La plus ancienne période terminée et pas encore déclarée."""
    deja = set(declarees)
    return next(
        (p for p in periodes_tva if p.fin < aujourd_hui and type_preuve(p) not in deja), None
    )
