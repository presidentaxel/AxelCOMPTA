"""Une décision humaine s'écrit au grand livre : une OD de reclassement (AXE-420).

Avant, une décision n'écrivait rien : chaque lecture réappliquait les
décisions par-dessus l'écriture bancaire (471). Le FEC et la liasse ne
sortaient donc pas de la base. Modèle retenu le 6 nov. :

* l'opération bancaire S reste telle quelle (trace bancaire, identifiant
  stable pour l'interface et les décisions) ;
* la décision n° k écrit `{S}:decision-{k}`, une OD qui déplace le montant
  du compte en vigueur vers le nouveau (ex. 606 au débit, 471 au crédit).
  Le 512 ne bouge jamais. Une nouvelle décision déplace de l'ancien compte
  vers le nouveau ; une annulation ramène en 471 ;
* une contre-passation de S (opération modifiée, imputation de l'expert)
  contre-passe aussi les reclassements en vigueur ;
* les écrans lisent une **projection** : les reclassements repliés dans S,
  comme si S avait été passée directement sur le bon compte. FEC, liasse et
  exports lisent le grand livre brut : les soldes sont les mêmes.

Pur : rien n'est lu ni écrit ici.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date

from axelcompta.core.ids import EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser, id_contrepassation, origine
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import Periode, date_de_report
from axelcompta.packs.tva_deductible import RegleTva, regle_tva

from .decisions import CATEGORIE_ANNULATION, DecisionHumaine
from .revue import COMPTE_ATTENTE, appliquer_decisions, compte_cible
from .tva_imputation import lignes_imputees

MARQUE = ":decision-"
# AXE-831 : OD qui sépare la TVA déductible d'une opération imputée TTC
# avant la règle (reprise). Elle complète S, sans la contre-passer.
MARQUE_TVA = ":tva-"


def id_reclassement(source_id: EcritureId, rang: int) -> EcritureId:
    return EcritureId(f"{source_id}{MARQUE}{rang}")


def source_du_reclassement(ecriture_id: EcritureId) -> EcritureId | None:
    """`S:decision-2` → `S` ; `None` pour toute autre écriture (y compris la
    contre-passation d'un reclassement)."""
    if MARQUE not in ecriture_id or origine(ecriture_id) is not None:
        return None
    source, rang = ecriture_id.rsplit(MARQUE, 1)
    return EcritureId(source) if rang.isdigit() else None


def id_complement_tva(source_id: EcritureId, rang: int) -> EcritureId:
    return EcritureId(f"{source_id}{MARQUE_TVA}{rang}")


def source_du_complement(ecriture_id: EcritureId) -> EcritureId | None:
    """`S:tva-1` → `S` ; `None` pour toute autre écriture."""
    if MARQUE_TVA not in ecriture_id or origine(ecriture_id) is not None:
        return None
    source, rang = ecriture_id.rsplit(MARQUE_TVA, 1)
    return EcritureId(source) if rang.isdigit() else None


def est_od_repliee(ecriture_id: EcritureId) -> bool:
    """Reclassement ou complément de TVA, et leurs contre-passations : des OD
    que les écrans replient dans l'opération bancaire."""
    base = origine(ecriture_id) or ecriture_id
    return source_du_reclassement(base) is not None or source_du_complement(base) is not None


def complements_tva_actifs(source_id: EcritureId, ecritures: Sequence[Ecriture]) -> list[Ecriture]:
    ids = {e.id for e in ecritures}
    return [
        e
        for e in ecritures
        if source_du_complement(e.id) == source_id and id_contrepassation(e.id) not in ids
    ]


def complement_tva(
    source: Ecriture,
    compte: str,
    regle: RegleTva,
    periodes_closes: Sequence[Periode] = (),
) -> Ecriture | None:
    """L'OD qui déplace la TVA récupérable de `compte` vers le compte de TVA
    déductible, pour une opération S imputée TTC avant AXE-831. Le 512 ne
    bouge pas. `None` si rien ne se récupère."""
    ligne = next((x for x in source.lignes if x.compte == compte), None)
    if ligne is None:
        return None
    imputees = lignes_imputees(compte, ligne.sens, ligne.montant, regle)
    if len(imputees) == 1:
        return None
    tva = imputees[1]
    return Ecriture(
        id=id_complement_tva(source.id, 1),
        dossier_id=source.dossier_id,
        journal=Journal.OD,
        date=date_de_report(source.date, periodes_closes),
        libelle=f"TVA déductible {source.libelle}",
        reference_piece=str(source.id),
        lignes=(tva, dataclasses.replace(tva, compte=compte, sens=_sens_oppose(tva.sens))),
    )


def reclassements_de(source_id: EcritureId, ecritures: Iterable[Ecriture]) -> list[Ecriture]:
    """Tous les reclassements de S, dans l'ordre des décisions."""
    trouves = [e for e in ecritures if source_du_reclassement(e.id) == source_id]
    return sorted(trouves, key=lambda e: int(e.id.rsplit(MARQUE, 1)[1]))


def _actifs(source_id: EcritureId, ecritures: Sequence[Ecriture]) -> list[Ecriture]:
    ids = {e.id for e in ecritures}
    return [
        r for r in reclassements_de(source_id, ecritures) if id_contrepassation(r.id) not in ids
    ]


def compte_en_vigueur(source_id: EcritureId, ecritures: Sequence[Ecriture]) -> str:
    """Le compte où se trouve aujourd'hui le montant de S : celui du dernier
    reclassement non contre-passé, sinon le compte d'attente."""
    actifs = _actifs(source_id, ecritures)
    return actifs[-1].lignes[0].compte if actifs else COMPTE_ATTENTE


def _sens_oppose(sens: Sens) -> Sens:
    return Sens.CREDIT if sens is Sens.DEBIT else Sens.DEBIT


def _lignes_attente(source: Ecriture) -> list[LigneEcriture]:
    return [ligne for ligne in source.lignes if ligne.compte == COMPTE_ATTENTE]


def _imputation(reclassement: Ecriture, sens: Sens) -> tuple[LigneEcriture, ...]:
    """Les lignes où un reclassement a posé le montant : celles du sens de la
    ligne d'attente (compte de la catégorie, puis TVA déductible, AXE-831)."""
    return tuple(ligne for ligne in reclassement.lignes if ligne.sens is sens)


def imputation_en_vigueur(
    source: Ecriture, ecritures: Sequence[Ecriture]
) -> tuple[LigneEcriture, ...] | None:
    """Les lignes du dernier reclassement non contre-passé de S, ou `None` si
    le montant est encore au compte d'attente."""
    attente = _lignes_attente(source)
    actifs = _actifs(source.id, ecritures)
    if not attente or not actifs:
        return None
    return _imputation(actifs[-1], attente[0].sens)


def _lignes_vers(
    ligne: LigneEcriture, vers: str, regle: RegleTva | None
) -> tuple[LigneEcriture, ...]:
    if regle is None:
        return (dataclasses.replace(ligne, compte=vers),)
    return lignes_imputees(vers, ligne.sens, ligne.montant, regle)


def ecriture_de_reclassement(
    source: Ecriture,
    rang: int,
    de: str,
    vers: str,
    periodes_closes: Sequence[Periode] = (),
    regle: RegleTva | None = None,
    en_vigueur: Sequence[LigneEcriture] | None = None,
) -> Ecriture:
    """Pour chaque ligne de S au compte d'attente : `vers` dans le sens de la
    ligne (TVA déductible séparée si `regle`, AXE-831), puis l'imputation en
    vigueur en sens inverse (`en_vigueur`, ou `de` sur le même montant).
    Équilibrée par construction. Datée comme S, ou au premier jour de
    l'exercice ouvert si S est dans un exercice clos."""
    lignes: list[LigneEcriture] = []
    for ligne in _lignes_attente(source):
        lignes.extend(_lignes_vers(ligne, vers, regle))
        if en_vigueur is None:
            lignes.append(dataclasses.replace(ligne, compte=de, sens=_sens_oppose(ligne.sens)))
    if en_vigueur is not None:
        lignes.extend(dataclasses.replace(x, sens=_sens_oppose(x.sens)) for x in en_vigueur)
    return Ecriture(
        id=id_reclassement(source.id, rang),
        dossier_id=source.dossier_id,
        journal=Journal.OD,
        date=date_de_report(source.date, periodes_closes),
        libelle=f"Reclassement {source.libelle}",
        reference_piece=str(source.id),
        lignes=tuple(lignes),
    )


def reclasser(
    source: Ecriture,
    categorie: str,
    ecritures: Sequence[Ecriture],
    comptes: tuple[dict[str, str | None], dict[str, str]],
    periodes_closes: Sequence[Periode] = (),
    regime_tva: str | None = None,
) -> Ecriture | None:
    """L'OD qui traduit la décision `categorie` sur S, ou `None` si le montant
    est déjà sur le bon compte. `comptes` : (comptes de statut, comptes du
    pack). `regime_tva` : celui du dossier ; sans lui, pas de TVA séparée.
    Lève `CategorieInconnueError` si la catégorie n'a pas de compte."""
    comptes_statut, comptes_par_categorie = comptes
    vers = (
        COMPTE_ATTENTE
        if categorie == CATEGORIE_ANNULATION
        else compte_cible(categorie, comptes_statut, comptes_par_categorie)
    )
    regle = None
    if regime_tva is not None and vers != COMPTE_ATTENTE:
        regle = regle_tva(categorie, source.date, regime_tva)
    return reclasser_vers(source, vers, ecritures, periodes_closes, regle)


def _empreinte(lignes: Iterable[LigneEcriture]) -> Counter[tuple[str, Sens, int]]:
    return Counter((x.compte, x.sens, x.montant.centimes) for x in lignes)


def reclasser_vers(
    source: Ecriture,
    vers: str,
    ecritures: Sequence[Ecriture],
    periodes_closes: Sequence[Periode] = (),
    regle: RegleTva | None = None,
) -> Ecriture | None:
    """Le reclassement qui amène le montant de S sur `vers` (TVA séparée selon
    `regle`), ou `None` s'il y est déjà, à l'identique, ou si S n'a pas de
    ligne d'attente. Une imputation sur le bon compte mais sans la TVA est
    réécrite : c'est la reprise d'AXE-831."""
    attente = _lignes_attente(source)
    if not attente:
        return None
    en_vigueur = imputation_en_vigueur(source, ecritures)
    if en_vigueur is None and vers == COMPTE_ATTENTE:
        return None
    cible = [x for ligne in attente for x in _lignes_vers(ligne, vers, regle)]
    if en_vigueur is not None and _empreinte(en_vigueur) == _empreinte(cible):
        return None
    de = en_vigueur[0].compte if en_vigueur else COMPTE_ATTENTE
    rang = len(reclassements_de(source.id, ecritures)) + 1
    return ecriture_de_reclassement(source, rang, de, vers, periodes_closes, regle, en_vigueur)


def dernier_compte_choisi(source_id: EcritureId, ecritures: Sequence[Ecriture]) -> str | None:
    """Le compte de la dernière décision sur S, même contre-passée (AXE-424 :
    l'opération corrigée garde la catégorie choisie). `None` sans décision."""
    reclassements = reclassements_de(source_id, ecritures)
    if not reclassements:
        return None
    compte = reclassements[-1].lignes[0].compte
    return None if compte == COMPTE_ATTENTE else compte


def annuler_reclassements(
    source_id: EcritureId,
    ecritures: Sequence[Ecriture],
    periodes_closes: Sequence[Periode] = (),
    debut_ouvert: date | None = None,
) -> list[Ecriture]:
    """Les contre-passations des reclassements encore en vigueur de S, à
    écrire avec celle de S : sinon le compte final resterait chargé.
    `debut_ouvert` date ces OD comme la contre-passation de S (AXE-838).
    Le complément de TVA de S (AXE-831) est annulé avec elle."""
    a_annuler = _actifs(source_id, ecritures) + complements_tva_actifs(source_id, ecritures)
    return [contrepasser(r, periodes_closes, debut_ouvert) for r in a_annuler]


def _remplacer_attente(ecriture: Ecriture, imputation: tuple[LigneEcriture, ...]) -> Ecriture:
    """Chaque ligne d'attente prend les lignes de l'imputation : dans leur
    sens, ou en sens inverse sur une contre-passation."""
    lignes: list[LigneEcriture] = []
    for ligne in ecriture.lignes:
        if ligne.compte != COMPTE_ATTENTE:
            lignes.append(ligne)
        elif ligne.sens is imputation[0].sens:
            lignes.extend(imputation)
        else:
            lignes.extend(dataclasses.replace(x, sens=_sens_oppose(x.sens)) for x in imputation)
    return dataclasses.replace(ecriture, lignes=tuple(lignes))


def projeter(ecritures: Sequence[Ecriture]) -> tuple[Ecriture, ...]:
    """Le grand livre vu par les écrans : chaque S reclassée prend l'imputation
    en vigueur (compte, et TVA déductible s'il y en a) sur ses lignes
    d'attente, sa contre-passation aussi ; les reclassements disparaissent.
    Les soldes par compte ne changent pas."""
    par_id = {e.id: e for e in ecritures}
    finaux: dict[EcritureId, tuple[LigneEcriture, ...] | None] = {}
    for e in ecritures:
        source_id = source_du_reclassement(e.id)
        if source_id is not None and source_id in par_id and source_id not in finaux:
            finaux[source_id] = imputation_en_vigueur(par_id[source_id], ecritures)
    complements: dict[EcritureId, list[Ecriture]] = {}
    for e in ecritures:
        source_id = source_du_complement(e.id)
        if source_id is not None and source_id not in complements:
            complements[source_id] = complements_tva_actifs(source_id, ecritures)
    resultat = []
    for ecriture in ecritures:
        if est_od_repliee(ecriture.id):
            continue
        final = finaux.get(origine(ecriture.id) or ecriture.id)
        if final and final[0].compte != COMPTE_ATTENTE:
            ecriture = _remplacer_attente(ecriture, final)
        for complement in complements.get(ecriture.id, ()):
            ecriture = _ajouter_complement(ecriture, complement)
        resultat.append(ecriture)
    return tuple(resultat)


def _ajouter_complement(ecriture: Ecriture, complement: Ecriture) -> Ecriture:
    """S telle qu'elle aurait été écrite avec sa TVA : la ligne du compte
    diminue de la TVA, la ligne de TVA s'ajoute."""
    lignes = list(ecriture.lignes)
    for ajout in complement.lignes:
        rang = next(
            (
                i
                for i, x in enumerate(lignes)
                if x.compte == ajout.compte and x.sens is not ajout.sens
            ),
            None,
        )
        if rang is None:
            lignes.append(ajout)
            continue
        reste = lignes[rang].montant.centimes - ajout.montant.centimes
        lignes[rang] = dataclasses.replace(
            lignes[rang], montant=Money(reste, ajout.montant.devise), code_tva=ajout.code_tva
        )
    return dataclasses.replace(ecriture, lignes=tuple(lignes))


def sources_reclassees(ecritures: Iterable[Ecriture]) -> frozenset[EcritureId]:
    return frozenset(
        source for e in ecritures if (source := source_du_reclassement(e.id)) is not None
    )


def grand_livre_tranche(
    ecritures: Sequence[Ecriture],
    decisions: Sequence[DecisionHumaine],
    comptes: tuple[dict[str, str | None], dict[str, str]],
) -> tuple[Ecriture, ...]:
    """Ce que lisent les écrans et la clôture : la projection des
    reclassements écrits, plus, **le temps de la reprise**, les décisions
    d'avant AXE-420 pas encore écrites (une opération sans aucun
    reclassement). Une fois `scripts/materialiser_decisions.py` passé, la
    seconde couche ne trouve plus rien à appliquer."""
    deja = sources_reclassees(ecritures)
    restantes = tuple(d for d in decisions if d.ecriture_id not in deja)
    comptes_statut, comptes_par_categorie = comptes
    return appliquer_decisions(
        projeter(ecritures), restantes, comptes_statut, comptes_par_categorie
    )


def grand_livre_comptable(
    ecritures: Sequence[Ecriture],
    decisions: Sequence[DecisionHumaine],
    comptes: tuple[dict[str, str | None], dict[str, str]],
) -> tuple[Ecriture, ...]:
    """Ce que lisent le FEC, le grand livre et la balance : les écritures
    telles qu'en base, reclassements compris. Seules les décisions d'avant
    AXE-420 pas encore écrites sont appliquées par-dessus, le temps de la
    reprise."""
    deja = sources_reclassees(ecritures)
    restantes = tuple(d for d in decisions if d.ecriture_id not in deja)
    comptes_statut, comptes_par_categorie = comptes
    return appliquer_decisions(tuple(ecritures), restantes, comptes_statut, comptes_par_categorie)


def reclassements_a_reprendre(
    ecritures: Sequence[Ecriture],
    decisions: Sequence[DecisionHumaine],
    comptes: tuple[dict[str, str | None], dict[str, str]],
    periodes_closes: Sequence[Periode] = (),
    regime_tva: str | None = None,
) -> list[Ecriture]:
    """Reprise des décisions d'avant AXE-420 : pour chaque opération qui n'a
    encore aucun reclassement, rejoue ses décisions dans l'ordre et rend les
    OD à écrire. Idempotent : une opération déjà reprise est sautée."""
    deja = sources_reclassees(ecritures)
    par_id = {e.id: e for e in ecritures}
    vues = list(ecritures)
    a_ecrire: list[Ecriture] = []
    for decision in sorted(decisions, key=lambda d: d.decide_le):
        source = par_id.get(decision.ecriture_id)
        if source is None or source.id in deja:
            continue
        reclassement = reclasser(
            source, decision.categorie, vues, comptes, periodes_closes, regime_tva
        )
        if reclassement is not None:
            vues.append(reclassement)
            a_ecrire.append(reclassement)
    return a_ecrire
