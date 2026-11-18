"""La couverture bancaire d'une fiche d'import, de toutes ses sources (AXE-973).

Composition root (doc 18) : réunit ce que la fiche sait des comptes de
banque et laisse `tenants/couverture_bancaire.py` dire, compte par compte,
ce qui est prouvé par le solde, ce qui manque et de combien.

Sources d'opérations et soldes connus :

- **FEC déposés** : chaque compte 512… (`fec:5120010`), ses mouvements de
  l'exercice, son solde d'ouverture (à-nouveaux) et de clôture ;
- **relevés QIF déposés** : leurs mouvements. Un QIF ne dit pas de quel
  compte il vient : il se rattache seul au compte d'un FEC qu'il recoupe
  (80 % de ses opérations retrouvées, même jour et même montant), sinon il
  reste un compte à part (`doc:<id>`) ;
- **Digifactory** (dossier créé) : chaque compte retenu (`digi:<id>`), ses
  opérations au grand livre et son dernier solde connu ;
- **la création de la société** : tout compte vaut 0 € la veille.

Seuls des agrégats sortent d'ici (périodes, soldes, écarts) : jamais une
opération ni un libellé (doc 03 §7).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.ledger.models import Ecriture, Sens
from axelcompta.tenants.couverture_bancaire import (
    Couverture,
    Solde,
    SourceOperations,
    correspondance,
    couverture,
)
from axelcompta.tenants.fiches_import import DocumentImport, FicheImport
from axelcompta.tenants.fiches_import_calculs import bornes_de
from axelcompta.tenants.fiches_import_etat import debut_a_couvrir

SEUIL_RATTACHEMENT = 0.8
UN_JOUR = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class CompteCouvert:
    cle: str  # « digi:67499359 », « fec:5120020 », « doc:<id> »
    libelle: str
    origine: str  # digifactory | fec | releve
    suivi: bool  # compte de l'activité à tenir jusqu'à aujourd'hui
    couverture: Couverture
    reunit: tuple[str, ...] = ()  # les autres sources rattachées à ce compte
    a_completer_depuis: date | None = None


@dataclass(slots=True)
class _Registre:
    libelles: dict[str, tuple[str, str]] = field(default_factory=dict)  # cle -> (libelle, origine)
    sources: list[SourceOperations] = field(default_factory=list)
    soldes: list[Solde] = field(default_factory=list)
    suivis: set[str] = field(default_factory=set)


def _operations(liste: object) -> tuple[tuple[date, int], ...]:
    if not isinstance(liste, list):
        return ()
    return tuple((date.fromisoformat(str(j)), int(m)) for j, m in liste)


def _depuis_fec(registre: _Registre, document: DocumentImport, champs: Mapping[str, str]) -> None:
    donnees = document.donnees or {}
    banque = donnees.get("banque")
    if not isinstance(banque, dict) or document.exercice is None:
        return
    debut, fin = bornes_de(champs, document.exercice)
    cloture = donnees.get("cloture")
    fin = date.fromisoformat(str(cloture)) if cloture else fin
    source = f"FEC {document.exercice}"
    for compte, detail in banque.items():
        cle = f"fec:{compte}"
        registre.libelles.setdefault(cle, (str(detail.get("libelle") or compte), "fec"))
        operations = _operations(detail.get("operations"))
        ouverture = detail.get("ouverture_cts")
        ouverture_le = detail.get("ouverture_le")
        if ouverture_le:
            debut = date.fromisoformat(str(ouverture_le)) + UN_JOUR
        registre.sources.append(SourceOperations(cle, source, debut, fin, operations))
        depart = int(ouverture) if ouverture is not None else 0
        if ouverture is not None and ouverture_le:
            registre.soldes.append(
                Solde(cle, date.fromisoformat(str(ouverture_le)), depart, f"{source} (à-nouveaux)")
            )
        registre.soldes.append(
            Solde(cle, fin, depart + sum(m for _, m in operations), f"{source} (clôture)")
        )


def _depuis_qif(registre: _Registre, document: DocumentImport) -> None:
    donnees = document.donnees or {}
    operations = _operations(donnees.get("mouvements"))
    if not operations:
        return
    debut, fin = min(j for j, _ in operations), max(j for j, _ in operations)
    # Le compte d'un FEC qu'il recoupe, sinon un compte à part.
    candidats = {
        s.compte: correspondance(operations, s.operations)
        for s in registre.sources
        if s.compte.startswith("fec:")
    }
    meilleur = max(candidats, key=lambda c: candidats[c], default=None)
    if meilleur is not None and candidats[meilleur] >= SEUIL_RATTACHEMENT:
        cle = meilleur
    else:
        cle = f"doc:{document.id}"
        nom = document.nom_fichier.rsplit("/", 1)[-1]
        registre.libelles[cle] = (f"Relevé {nom}", "releve")
    registre.sources.append(
        SourceOperations(
            cle, f"Relevé {document.nom_fichier.rsplit('/', 1)[-1]}", debut, fin, operations
        )
    )


def _depuis_digifactory(
    registre: _Registre,
    comptes: Sequence[CompteBancaire],
    ecritures: Sequence[Ecriture],
    champs: Mapping[str, str],
    aujourd_hui: date,
) -> None:
    for compte in comptes:
        if compte.retenu is not True:
            continue  # personnel ou à décider : pas un compte de l'activité
        cle = f"digi:{compte.identifiant}"
        registre.libelles[cle] = (compte.nom or compte.compte_comptable, "digifactory")
        registre.suivis.add(cle)
        operations = tuple(
            (e.date, ligne.montant.centimes * (1 if ligne.sens == Sens.DEBIT else -1))
            for e in ecritures
            for ligne in e.lignes
            if ligne.compte == compte.compte_comptable
        )
        historique = champs.get("debut_historique")
        debut = min(
            [j for j, _ in operations]
            + ([date.fromisoformat(historique)] if historique else [])
            + [aujourd_hui]
        )
        fin = compte.solde_releve_le.date() if compte.solde_releve_le else aujourd_hui
        registre.sources.append(SourceOperations(cle, "Digifactory", debut, fin, operations))
        if compte.solde_banque_cts is not None and compte.solde_releve_le is not None:
            registre.soldes.append(
                Solde(cle, compte.solde_releve_le.date(), compte.solde_banque_cts, "Digifactory")
            )


def couverture_de_la_fiche(
    fiche: FicheImport,
    documents: Sequence[DocumentImport],
    comptes: Sequence[CompteBancaire],
    ecritures: Sequence[Ecriture],
    aujourd_hui: date,
) -> list[CompteCouvert]:
    """Chaque compte de banque de la fiche et sa couverture, du jour de la
    création (ou de la première donnée) à aujourd'hui pour un compte de
    l'activité, à sa dernière donnée pour un compte d'archive."""
    champs = fiche.champs
    registre = _Registre()
    for document in documents:
        if document.categorie == "fec":
            _depuis_fec(registre, document, champs)
    for document in documents:
        if (document.donnees or {}).get("type") == "qif":
            _depuis_qif(registre, document)
    _depuis_digifactory(registre, comptes, ecritures, champs, aujourd_hui)
    creation = champs.get("date_creation")
    if creation:
        veille = date.fromisoformat(creation) - UN_JOUR
        registre.soldes += [
            Solde(cle, veille, 0, "Création de la société") for cle in registre.libelles
        ]
    a_couvrir = debut_a_couvrir(champs, aujourd_hui)
    resultat = []
    for cle, (libelle, origine) in registre.libelles.items():
        siennes = [s for s in registre.sources if s.compte == cle]
        if not siennes:
            continue
        debut = date.fromisoformat(creation) if creation else min(s.debut for s in siennes)
        suivi = cle in registre.suivis
        fin = aujourd_hui if suivi else max(s.fin for s in siennes)
        resultat.append(
            CompteCouvert(
                cle,
                libelle,
                origine,
                suivi,
                couverture(cle, siennes, registre.soldes, min(debut, fin), fin),
                a_completer_depuis=a_couvrir if suivi else None,
            )
        )
    # Les comptes de l'activité d'abord, puis les archives, les plus récentes d'abord.
    return sorted(resultat, key=lambda c: (not c.suivi, -c.couverture.periodes[-1].fin.toordinal()))


def a_completer(compte: CompteCouvert) -> list[tuple[date, date, str]]:
    """Ce qu'il faut demander pour un compte de l'activité, depuis le début
    de l'exercice le plus ancien que nous tenons."""
    if not compte.suivi:
        return []
    depuis = compte.a_completer_depuis or date.min
    return [
        (max(p.debut, depuis), p.fin, p.etat)
        for p in compte.couverture.a_completer
        if p.fin >= depuis
    ]
