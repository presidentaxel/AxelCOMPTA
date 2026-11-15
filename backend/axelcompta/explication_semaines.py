"""Vue du rapprochement Rollee ↔ banque, semaine par semaine.

Pur : rien n'est écrit. Les semaines déjà soldées restent visibles, avec
chaque jour Rollee et chaque virement bancaire.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from axelcompta.core.pcg import est_compte_banque
from axelcompta.ingestion.providers.rollee import especes_cts
from axelcompta.ingestion.semaines_plateforme import (
    Jour,
    Semaine,
    Virement,
    lundi,
    rapprocher_plateforme,
)
from axelcompta.ingestion.settlements_plateforme import (
    MOTIF_DOUBLON,
    MOTIF_ECART,
    SettlementStocke,
    d_un_jour,
)
from axelcompta.ledger.models import Ecriture, Sens
from axelcompta.revenus_semaines import debut_banque, virements_de_plateforme

COPIES = frozenset({MOTIF_DOUBLON, MOTIF_ECART})
MOTIF_SANS_BANQUE = "Aucun relevé bancaire sur cette période."
MOTIF_EN_COURS = "Semaine pas encore terminée."


@dataclass(frozen=True, slots=True)
class JourVu:
    date: date
    brut_cts: int
    commission_cts: int
    net_cts: int
    especes_cts: int
    du_cts: int


@dataclass(frozen=True, slots=True)
class VirementVu:
    date: date
    libelle: str
    montant_cts: int
    nature: str
    compte: str


@dataclass(frozen=True, slots=True)
class SemaineVue:
    plateforme: str
    lundi: date
    dimanche: date
    etat: str
    du_cts: int
    paye_cts: int
    frais_cts: int
    ecart_cts: int
    motif: str | None
    jours: tuple[JourVu, ...]
    virements: tuple[VirementVu, ...]


def expliquer_semaines(
    stockes: Sequence[SettlementStocke],
    grand_livre: Sequence[Ecriture],
    aujourd_hui: date,
) -> list[SemaineVue]:
    """Toutes les semaines : jours Rollee et virements bancaires, y compris
    celles déjà soldées."""
    jours = _jours_retenus(stockes)
    virements = virements_de_plateforme(grand_livre)
    retenus, avant = _separer(jours, _seuil(grand_livre))
    vues = _semaines(retenus, virements, aujourd_hui)
    vues += _avant_la_banque(avant)
    return sorted(vues, key=lambda vue: (vue.lundi, vue.plateforme), reverse=True)


def _jours_retenus(stockes: Sequence[SettlementStocke]) -> dict[str, SettlementStocke]:
    return {
        stocke.id: stocke
        for stocke in stockes
        if d_un_jour(stocke) and stocke.etat != "delie" and stocke.motif not in COPIES
    }


def _seuil(grand_livre: Sequence[Ecriture]) -> date | None:
    debut = debut_banque(grand_livre)
    return lundi(debut) if debut is not None else None


def _separer(
    jours: dict[str, SettlementStocke], seuil: date | None
) -> tuple[dict[str, SettlementStocke], dict[str, SettlementStocke]]:
    if seuil is None:
        return {}, jours
    retenus: dict[str, SettlementStocke] = {}
    avant: dict[str, SettlementStocke] = {}
    for identifiant, stocke in jours.items():
        cible = avant if lundi(stocke.settlement.period_start) < seuil else retenus
        cible[identifiant] = stocke
    return retenus, avant


def _semaines(
    jours: dict[str, SettlementStocke],
    virements: dict[str, tuple[Virement, Ecriture]],
    aujourd_hui: date,
) -> list[SemaineVue]:
    plateformes = sorted(
        {stocke.settlement.platform for stocke in jours.values()}
        | {virement.plateforme for virement, _ecriture in virements.values()}
    )
    vues: list[SemaineVue] = []
    for plateforme in plateformes:
        vues.extend(_semaines_de(plateforme, jours, virements, aujourd_hui))
    return vues


def _semaines_de(
    plateforme: str,
    jours: dict[str, SettlementStocke],
    virements: dict[str, tuple[Virement, Ecriture]],
    aujourd_hui: date,
) -> list[SemaineVue]:
    siens = [_comme_jour(s) for s in jours.values() if s.settlement.platform == plateforme]
    payes = [
        virement for virement, _ecriture in virements.values() if virement.plateforme == plateforme
    ]
    prises: set[date] = set()
    vues: list[SemaineVue] = []
    for semaine in rapprocher_plateforme(plateforme, siens, payes, aujourd_hui):
        prises.add(semaine.lundi)
        vues.append(_habiller(semaine, jours, virements, None))
    vues.extend(_en_cours(plateforme, siens, payes, prises, aujourd_hui, jours, virements))
    return vues


def _en_cours(
    plateforme: str,
    siens: list[Jour],
    payes: list[Virement],
    prises: set[date],
    aujourd_hui: date,
    jours: dict[str, SettlementStocke],
    virements: dict[str, tuple[Virement, Ecriture]],
) -> list[SemaineVue]:
    lundis = {lundi(jour.jour) for jour in siens} | {virement.semaine for virement in payes}
    vues: list[SemaineVue] = []
    for lundi_ in sorted(lundis):
        if lundi_ in prises or lundi_ + timedelta(days=6) < aujourd_hui:
            continue
        vues.append(_semaine_ouverte(plateforme, lundi_, siens, payes, jours, virements))
    return vues


def _semaine_ouverte(
    plateforme: str,
    lundi_: date,
    siens: list[Jour],
    payes: list[Virement],
    jours: dict[str, SettlementStocke],
    virements: dict[str, tuple[Virement, Ecriture]],
) -> SemaineVue:
    du_jour = [jour for jour in siens if lundi(jour.jour) == lundi_]
    verses = [virement for virement in payes if virement.semaine == lundi_]
    du = sum(jour.du_cts for jour in du_jour)
    paye = sum(virement.montant_cts for virement in verses)
    semaine = Semaine(
        plateforme,
        lundi_,
        "en_attente",
        du,
        paye,
        0,
        du - paye,
        tuple(jour.id for jour in du_jour),
        tuple(virement.id for virement in verses),
    )
    return _habiller(semaine, jours, virements, MOTIF_EN_COURS)


def _avant_la_banque(jours: dict[str, SettlementStocke]) -> list[SemaineVue]:
    groupes: dict[tuple[str, date], list[SettlementStocke]] = {}
    for stocke in jours.values():
        cle = (stocke.settlement.platform, lundi(stocke.settlement.period_start))
        groupes.setdefault(cle, []).append(stocke)
    return [_semaine_sans_banque(cle, groupe) for cle, groupe in groupes.items()]


def _semaine_sans_banque(cle: tuple[str, date], groupe: list[SettlementStocke]) -> SemaineVue:
    plateforme, lundi_ = cle
    du = sum(_du(stocke) for stocke in groupe)
    semaine = Semaine(
        plateforme,
        lundi_,
        "en_attente",
        du,
        0,
        0,
        du,
        tuple(stocke.id for stocke in groupe),
        (),
    )
    return _habiller(semaine, {stocke.id: stocke for stocke in groupe}, {}, MOTIF_SANS_BANQUE)


def _habiller(
    semaine: Semaine,
    jours: dict[str, SettlementStocke],
    virements: dict[str, tuple[Virement, Ecriture]],
    motif: str | None,
) -> SemaineVue:
    stockes = [jours[identifiant] for identifiant in semaine.jours if identifiant in jours]
    return SemaineVue(
        plateforme=semaine.plateforme,
        lundi=semaine.lundi,
        dimanche=semaine.dimanche,
        etat=_etat(semaine, stockes),
        du_cts=semaine.du_cts,
        paye_cts=semaine.paye_cts,
        frais_cts=semaine.frais_cts,
        ecart_cts=semaine.ecart_cts,
        motif=_motif(semaine, stockes, motif),
        jours=tuple(sorted((_jour_vu(stocke) for stocke in stockes), key=lambda jour: jour.date)),
        virements=tuple(
            sorted(
                (
                    _virement_vu(virements[identifiant])
                    for identifiant in semaine.virements
                    if identifiant in virements
                ),
                key=lambda vu: (vu.date, vu.libelle),
            )
        ),
    )


def _etat(semaine: Semaine, stockes: list[SettlementStocke]) -> str:
    if any(stocke.etat == "a_verifier" for stocke in stockes):
        return "a_verifier"
    return semaine.etat


def _motif(semaine: Semaine, stockes: list[SettlementStocke], force: str | None) -> str | None:
    garde = next(
        (stocke.motif for stocke in stockes if stocke.etat == "a_verifier" and stocke.motif), None
    )
    if garde is not None:
        return garde
    if force is not None:
        return force
    if semaine.etat == "a_verifier":
        return _texte_ecart(semaine)
    return None


def _texte_ecart(semaine: Semaine) -> str:
    euros, centimes = divmod(abs(semaine.ecart_cts), 100)
    montant = f"{euros},{centimes:02d} €"
    nom = semaine.plateforme.capitalize()
    if semaine.ecart_cts >= 0:
        return f"{montant} encore dus par {nom}"
    return f"{montant} versés en trop par {nom}"


def _du(stocke: SettlementStocke) -> int:
    return stocke.settlement.net_payout_cts - especes_cts(stocke.settlement)


def _comme_jour(stocke: SettlementStocke) -> Jour:
    settlement = stocke.settlement
    return Jour(stocke.id, settlement.platform, settlement.period_start, _du(stocke))


def _jour_vu(stocke: SettlementStocke) -> JourVu:
    settlement = stocke.settlement
    especes = especes_cts(settlement)
    return JourVu(
        settlement.period_start,
        settlement.gross_earnings_cts,
        settlement.commission_cts,
        settlement.net_payout_cts,
        especes,
        settlement.net_payout_cts - especes,
    )


def _virement_vu(couple: tuple[Virement, Ecriture]) -> VirementVu:
    vu, ecriture = couple
    comptes = sorted(
        ligne.compte
        for ligne in ecriture.lignes
        if ligne.sens is Sens.CREDIT and not est_compte_banque(ligne.compte)
    )
    return VirementVu(
        ecriture.date, ecriture.libelle, vu.montant_cts, vu.nature, ", ".join(comptes)
    )
