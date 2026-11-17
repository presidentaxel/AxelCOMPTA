"""Reprendre en virement interne une opération déjà imputée (AXE-930). Pur.

Avant AXE-930, les deux jambes d'un mouvement entre enveloppes montrées sur
le même compte (MK DRIVING : « cotisation URSSAF » −50 € / +50 €) passaient
pour des charges (645). L'opération bancaire S ne change pas : une OD
`{S}:virement-interne` déplace son montant du compte en vigueur vers le 580.
Comme un reclassement, les écrans la replient dans S, qui s'affiche alors
directement en 580 ; FEC et balance lisent les deux, avec les mêmes soldes.

Une opération qui porte de la TVA n'est pas reprise : un virement interne
n'en a pas, et on ne réécrit pas une TVA à l'aveugle.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence

from axelcompta.categorize.virements_internes import Jambe, apparier
from axelcompta.core.ids import EcritureId
from axelcompta.core.libelles import sans_categorie
from axelcompta.core.pcg import COMPTE_BANQUE, est_compte_banque
from axelcompta.ledger.contrepassation import annulees, id_contrepassation, origine
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import Periode, date_de_report

from .ventilation_bancaire import SUFFIXE_VENTILATION as SUFFIXE_VENTILATION_BANQUE

COMPTE_VIREMENT_INTERNE = "580"
COMPTE_ATTENTE = "471"
MARQUE_INTERNE = ":virement-interne"


def id_virement_interne(source_id: EcritureId) -> EcritureId:
    return EcritureId(f"{source_id}{MARQUE_INTERNE}")


def source_du_virement_interne(ecriture_id: EcritureId) -> EcritureId | None:
    """`S:virement-interne` → `S` ; `None` pour toute autre écriture."""
    if not ecriture_id.endswith(MARQUE_INTERNE) or origine(ecriture_id) is not None:
        return None
    return EcritureId(ecriture_id[: -len(MARQUE_INTERNE)])


def _economique(ligne: LigneEcriture) -> bool:
    return not est_compte_banque(ligne.compte) and not ligne.compte.startswith("445")


def porte_de_la_tva(ecriture: Ecriture) -> bool:
    return any(ligne.compte.startswith("445") for ligne in ecriture.lignes)


def ecriture_virement_interne(
    projetee: Ecriture, periodes_closes: Sequence[Periode] = ()
) -> Ecriture | None:
    """L'OD qui amène S (vue projetée, compte en vigueur) sur le 580 ; `None`
    si elle y est déjà ou si elle porte de la TVA."""
    if porte_de_la_tva(projetee):
        return None
    deplacees = [x for x in projetee.lignes if _economique(x)]
    if not deplacees or all(x.compte == COMPTE_VIREMENT_INTERNE for x in deplacees):
        return None
    lignes: list[LigneEcriture] = []
    for ligne in deplacees:
        inverse = Sens.CREDIT if ligne.sens is Sens.DEBIT else Sens.DEBIT
        lignes.append(LigneEcriture(COMPTE_VIREMENT_INTERNE, ligne.sens, ligne.montant))
        lignes.append(LigneEcriture(ligne.compte, inverse, ligne.montant))
    return Ecriture(
        id=id_virement_interne(projetee.id),
        dossier_id=projetee.dossier_id,
        journal=Journal.OD,
        date=date_de_report(projetee.date, periodes_closes),
        libelle=f"Virement interne {projetee.libelle}"[:200],
        reference_piece=str(projetee.id),
        lignes=tuple(lignes),
    )


def sources_en_virement_interne(ecritures: Sequence[Ecriture]) -> frozenset[EcritureId]:
    """Les opérations dont l'OD de virement interne est en vigueur."""
    ids = {e.id for e in ecritures}
    return frozenset(
        source
        for e in ecritures
        if (source := source_du_virement_interne(e.id)) is not None
        and id_contrepassation(e.id) not in ids
    )


def en_virement_interne(ecriture: Ecriture) -> Ecriture:
    """S telle que les écrans la voient une fois reprise : sur le 580."""
    return dataclasses.replace(
        ecriture,
        lignes=tuple(
            dataclasses.replace(x, compte=COMPTE_VIREMENT_INTERNE) if _economique(x) else x
            for x in ecriture.lignes
        ),
    )


def sous_comptes_ventiles(ecritures: Sequence[Ecriture]) -> dict[str, str]:
    """`{id de l'opération: 512x}` d'après les reclassements AXE-832 : une
    opération écrite au 512 avant les sous-comptes garde ainsi la trace du
    compte bancaire d'où elle vient (AXE-968)."""
    trouves: dict[str, str] = {}
    exclues = annulees(ecritures)
    for ecriture in ecritures:
        if not ecriture.id.endswith(SUFFIXE_VENTILATION_BANQUE) or ecriture.id in exclues:
            continue
        source = ecriture.id[: -len(SUFFIXE_VENTILATION_BANQUE)]
        sous_compte = next(
            (
                x.compte
                for x in ecriture.lignes
                if est_compte_banque(x.compte) and x.compte != COMPTE_BANQUE
            ),
            None,
        )
        if sous_compte is not None:
            trouves[source] = sous_compte
    return trouves


def _jambe(ecriture: Ecriture, sous_comptes: Mapping[str, str]) -> Jambe | None:
    banques = [x for x in ecriture.lignes if est_compte_banque(x.compte)]
    if len(banques) != 1:
        return None
    ligne = banques[0]
    signe = 1 if ligne.sens is Sens.DEBIT else -1
    compte = ligne.compte
    if compte == COMPTE_BANQUE:
        compte = sous_comptes.get(str(ecriture.id), compte)
    return Jambe(
        str(ecriture.id),
        ecriture.date,
        signe * ligne.montant.centimes,
        compte,
        sans_categorie(ecriture.libelle),
    )


def _au_compte_d_attente(ecriture: Ecriture) -> bool:
    """Toutes les lignes hors banque sont encore au 471 : personne n'a
    classé l'opération. Le passage automatique ne touche qu'à celles-là."""
    economiques = [x for x in ecriture.lignes if _economique(x)]
    return bool(economiques) and all(x.compte == COMPTE_ATTENTE for x in economiques)


@dataclasses.dataclass(frozen=True, slots=True)
class Reprise:
    ecritures: tuple[Ecriture, ...]
    paires: int  # paires reprises
    avec_tva: int  # paires laissées : une jambe porte de la TVA


def reprises(
    projetees: Sequence[Ecriture],
    periodes_closes: Sequence[Periode] = (),
    *,
    sous_comptes: Mapping[str, str] | None = None,
    seulement_en_attente: bool = False,
) -> Reprise:
    """Les paires de virement interne parmi les opérations bancaires déjà
    écrites (vue projetée), et l'OD de chaque jambe pas encore en 580. Les
    deux jambes d'une paire sont reprises ensemble, ou pas du tout.

    `sous_comptes` : le 512x de chaque opération écrite au 512 (AXE-832),
    pour reconnaître un virement entre deux comptes même quand les libellés
    diffèrent. `seulement_en_attente` : le passage horaire (AXE-968) ne
    regarde que les opérations encore au 471 ; une opération déjà classée
    par un humain n'est jamais déplacée."""
    exclues = annulees(projetees)
    par_id = {
        str(e.id): e
        for e in projetees
        if e.journal is Journal.BQ
        and e.id not in exclues
        and origine(e.id) is None
        and (not seulement_en_attente or _au_compte_d_attente(e))
    }
    connus = sous_comptes or {}
    jambes = [j for e in par_id.values() if (j := _jambe(e, connus)) is not None]
    paires = apparier(jambes)
    ecritures: list[Ecriture] = []
    vues: set[str] = set()
    reprises_, avec_tva = 0, 0
    for a, b in paires.items():
        if a in vues:
            continue
        vues.update((a, b))
        duo = [par_id[a], par_id[b]]
        if any(porte_de_la_tva(e) for e in duo):
            avec_tva += 1
            continue
        ods = [od for e in duo if (od := ecriture_virement_interne(e, periodes_closes))]
        if ods:
            ecritures.extend(ods)
            reprises_ += 1
    return Reprise(tuple(ecritures), reprises_, avec_tva)
