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
from collections.abc import Iterable, Sequence

from axelcompta.core.ids import EcritureId
from axelcompta.ledger.contrepassation import contrepasser, id_contrepassation, origine
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import Periode, date_de_report

from .decisions import CATEGORIE_ANNULATION, DecisionHumaine
from .revue import COMPTE_ATTENTE, appliquer_decisions, compte_cible

MARQUE = ":decision-"


def id_reclassement(source_id: EcritureId, rang: int) -> EcritureId:
    return EcritureId(f"{source_id}{MARQUE}{rang}")


def source_du_reclassement(ecriture_id: EcritureId) -> EcritureId | None:
    """`S:decision-2` → `S` ; `None` pour toute autre écriture (y compris la
    contre-passation d'un reclassement)."""
    if MARQUE not in ecriture_id or origine(ecriture_id) is not None:
        return None
    source, rang = ecriture_id.rsplit(MARQUE, 1)
    return EcritureId(source) if rang.isdigit() else None


def _est_reclassement(ecriture_id: EcritureId) -> bool:
    return source_du_reclassement(origine(ecriture_id) or ecriture_id) is not None


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


def ecriture_de_reclassement(
    source: Ecriture,
    rang: int,
    de: str,
    vers: str,
    periodes_closes: Sequence[Periode] = (),
) -> Ecriture:
    """Pour chaque ligne de S au compte d'attente : `vers` dans le sens de la
    ligne, `de` en sens inverse. Équilibrée par construction. Datée comme S,
    ou au premier jour de l'exercice ouvert si S est dans un exercice clos."""
    lignes: list[LigneEcriture] = []
    for ligne in source.lignes:
        if ligne.compte != COMPTE_ATTENTE:
            continue
        lignes.append(dataclasses.replace(ligne, compte=vers))
        lignes.append(dataclasses.replace(ligne, compte=de, sens=_sens_oppose(ligne.sens)))
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
) -> Ecriture | None:
    """L'OD qui traduit la décision `categorie` sur S, ou `None` si le montant
    est déjà sur le bon compte. `comptes` : (comptes de statut, comptes du
    pack). Lève `CategorieInconnueError` si la catégorie n'a pas de compte."""
    comptes_statut, comptes_par_categorie = comptes
    vers = (
        COMPTE_ATTENTE
        if categorie == CATEGORIE_ANNULATION
        else compte_cible(categorie, comptes_statut, comptes_par_categorie)
    )
    de = compte_en_vigueur(source.id, ecritures)
    if vers == de or not any(ligne.compte == COMPTE_ATTENTE for ligne in source.lignes):
        return None
    rang = len(reclassements_de(source.id, ecritures)) + 1
    return ecriture_de_reclassement(source, rang, de, vers, periodes_closes)


def annuler_reclassements(
    source_id: EcritureId,
    ecritures: Sequence[Ecriture],
    periodes_closes: Sequence[Periode] = (),
) -> list[Ecriture]:
    """Les contre-passations des reclassements encore en vigueur de S, à
    écrire avec celle de S : sinon le compte final resterait chargé."""
    return [contrepasser(r, periodes_closes) for r in _actifs(source_id, ecritures)]


def projeter(ecritures: Sequence[Ecriture]) -> tuple[Ecriture, ...]:
    """Le grand livre vu par les écrans : chaque S reclassée prend le compte
    en vigueur sur ses lignes d'attente (sa contre-passation aussi), les
    reclassements disparaissent. Les soldes par compte ne changent pas."""
    sources = {source for e in ecritures if (source := source_du_reclassement(e.id)) is not None}
    finaux = {s: compte_en_vigueur(s, ecritures) for s in sources}
    resultat = []
    for ecriture in ecritures:
        if _est_reclassement(ecriture.id):
            continue
        final = finaux.get(origine(ecriture.id) or ecriture.id)
        if final is not None and final != COMPTE_ATTENTE:
            ecriture = dataclasses.replace(
                ecriture,
                lignes=tuple(
                    dataclasses.replace(ligne, compte=final)
                    if ligne.compte == COMPTE_ATTENTE
                    else ligne
                    for ligne in ecriture.lignes
                ),
            )
        resultat.append(ecriture)
    return tuple(resultat)


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
        reclassement = reclasser(source, decision.categorie, vues, comptes, periodes_closes)
        if reclassement is not None:
            vues.append(reclassement)
            a_ecrire.append(reclassement)
    return a_ecrire
