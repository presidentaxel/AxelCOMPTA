"""Écrire en comptabilité les relevés déposés sur une fiche d'import (AXE-833).

Digifactory ne remonte la banque d'un chauffeur qu'à partir du jour où il
l'a connectée : les mois d'avant, dans l'exercice que nous tenons, manquent
au grand livre. Ils sont sur les relevés QIF déposés sur sa fiche d'import.

Pour chaque compte Digifactory retenu du dossier (`digi:<id>`), les relevés
QIF que le gestionnaire y a rattachés (AXE-973) donnent les opérations :

* **de l'exercice** : à partir du début de l'exercice ouvert du dossier ;
* **d'avant Digifactory** : strictement avant la première opération que
  Digifactory a remontée pour ce compte (ou le début de l'historique noté
  sur la fiche). Rien n'est donc écrit deux fois ;
* **prouvées par le solde** : la couverture bancaire (AXE-973) doit dire
  « prouvé » sur toute cette période, c'est-à-dire que solde de départ +
  opérations = solde au début de Digifactory, au centime. Sinon le compte
  n'est pas écrit, et la phrase dit l'écart ;
* **une seule fois** : deux relevés qui se recouvrent comptent une
  opération une fois (même jour, même montant, même libellé), au plus grand
  nombre d'occurrences vu dans un même relevé.

Les opérations passent ensuite par la synchro ordinaire (source `releve`) :
catégorisation, sous-compte 512x, 471 pour ce qui n'est pas reconnu. Leur
identifiant dérive du compte, du jour, du montant et du libellé : rejouer
n'écrit rien de plus.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date

from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.couverture_bancaire_fiche import CompteCouvert, couverture_de_la_fiche
from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.models import Ecriture
from axelcompta.tenants.couverture_bancaire import phrase
from axelcompta.tenants.fiches_import import DocumentImport, FicheImport
from axelcompta.tenants.fiches_import_banque import racine, rattachements
from axelcompta.traitement_documents_import import OperationQif, QifIllisible, lire_qif

SOURCE_RELEVE = "releve"
SOURCE_DIGIFACTORY = "digifactory"


@dataclass(frozen=True, slots=True)
class CompteAEcrire:
    compte: CompteBancaire
    depuis: date
    avant: date
    documents: tuple[str, ...]  # identifiants des relevés rattachés


@dataclass(frozen=True, slots=True)
class Plan:
    comptes: tuple[CompteAEcrire, ...]
    refus: tuple[str, ...]  # une phrase par compte non écrit


def premiere_operation_digifactory(
    ecritures: Sequence[Ecriture], dossier_id: DossierId, compte: CompteBancaire
) -> date | None:
    prefixe = f"{dossier_id}:{SOURCE_DIGIFACTORY}-"
    jours = [
        e.date
        for e in ecritures
        if str(e.id).startswith(prefixe)
        and any(ligne.compte == compte.compte_comptable for ligne in e.lignes)
    ]
    return min(jours) if jours else None


def _releves_rattaches(
    fiche: FicheImport, documents: Sequence[DocumentImport], cle: str
) -> tuple[str, ...]:
    liens = rattachements(fiche.champs)
    return tuple(
        d.id
        for d in documents
        if (d.donnees or {}).get("type") in ("qif", "releve")
        and racine(f"doc:{d.id}", liens) == cle
    )


def _refus_couverture(couvert: CompteCouvert | None, depuis: date, avant: date) -> str | None:
    if couvert is None:
        return "aucune couverture calculée"
    for periode in couvert.couverture.periodes:
        if periode.fin < depuis or periode.debut >= avant:
            continue
        if periode.etat != "complet":
            return phrase(periode)
    return None


def planifier(
    fiche: FicheImport,
    documents: Sequence[DocumentImport],
    comptes: Sequence[CompteBancaire],
    ecritures: Sequence[Ecriture],
    exercice_debut: date,
    aujourd_hui: date,
) -> Plan:
    """Les comptes dont les relevés peuvent être écrits, et pourquoi les
    autres ne le peuvent pas. Pur : `documents` porte déjà les mouvements."""
    if fiche.dossier_id is None:
        return Plan((), ("La fiche n'a pas encore de dossier.",))
    couverts = {
        c.cle: c for c in couverture_de_la_fiche(fiche, documents, comptes, ecritures, aujourd_hui)
    }
    historique = fiche.champs.get("debut_historique")
    a_ecrire, refus = [], []
    for compte in comptes:
        if compte.retenu is not True:
            continue
        cle = f"digi:{compte.identifiant}"
        releves = _releves_rattaches(fiche, documents, cle)
        if not releves:
            continue
        nom = compte.nom or compte.compte_comptable
        avant = premiere_operation_digifactory(ecritures, fiche.dossier_id, compte) or (
            date.fromisoformat(historique) if historique else None
        )
        if avant is None or avant <= exercice_debut:
            refus.append(f"{nom} : Digifactory couvre déjà tout l'exercice, rien à écrire.")
            continue
        raison = _refus_couverture(couverts.get(cle), exercice_debut, avant)
        if raison is not None:
            refus.append(
                f"{nom} : non écrit, la période du {exercice_debut:%d/%m/%Y} au "
                f"{avant:%d/%m/%Y} n'est pas prouvée par le solde ({raison})"
            )
            continue
        a_ecrire.append(CompteAEcrire(compte, exercice_debut, avant, releves))
    return Plan(tuple(a_ecrire), tuple(refus))


def _cle(operation: OperationQif) -> tuple[date, int, str]:
    return (operation.jour, operation.montant_cts, " ".join(operation.libelle.split()).upper())


def transactions(
    dossier_id: DossierId,
    a_ecrire: CompteAEcrire,
    releves: Sequence[tuple[str, Sequence[OperationQif]]],
) -> tuple[NormalizedTransaction, ...]:
    """Les opérations de la période, une fois chacune, prêtes pour la synchro."""
    retenues: dict[tuple[date, int, str], tuple[int, str, OperationQif]] = {}
    for document_id, operations in releves:
        dans = [o for o in operations if a_ecrire.depuis <= o.jour < a_ecrire.avant]
        comptes = Counter(_cle(o) for o in dans)
        exemples = {_cle(o): o for o in dans}
        for cle, nombre in comptes.items():
            if nombre > retenues.get(cle, (0, "", exemples[cle]))[0]:
                retenues[cle] = (nombre, document_id, exemples[cle])
    sortie = []
    compte = a_ecrire.compte.identifiant
    for cle, (nombre, document_id, operation) in sorted(retenues.items()):
        for rang in range(nombre):
            empreinte = hashlib.sha256(
                f"{compte}|{cle[0].isoformat()}|{cle[1]}|{cle[2]}|{rang}".encode()
            ).hexdigest()[:24]
            sortie.append(
                NormalizedTransaction(
                    id=TransactionId(f"{SOURCE_RELEVE}-{empreinte}"),
                    dossier_id=dossier_id,
                    date=operation.jour,
                    montant_cts=operation.montant_cts,
                    libelle=operation.libelle.strip() or "Opération du relevé",
                    source_provider=SOURCE_RELEVE,
                    raw_payload={"document_id": document_id},
                    compte_bancaire=compte,
                )
            )
    return tuple(sortie)


def lire_releves(
    ids: Sequence[str], contenu: Callable[[str], bytes]
) -> list[tuple[str, list[OperationQif]]]:
    """Relit chaque relevé (les libellés ne sont pas gardés sur la fiche,
    doc 03 §7). Un relevé illisible est ignoré : il l'était déjà au dépôt."""
    lus = []
    for document_id in ids:
        try:
            lus.append((document_id, lire_qif(contenu(document_id))))
        except (QifIllisible, UnicodeDecodeError):
            continue
    return lus


def operations_lues(document: DocumentImport) -> list[OperationQif]:
    """Les opérations d'un relevé PDF lu par l'OCR (AXE-943), libellés
    compris, gardés sur le document."""
    lu = (document.donnees or {}).get("lu")
    operations = lu.get("operations") if isinstance(lu, dict) else None
    lues = []
    for o in operations if isinstance(operations, list) else []:
        try:
            jour = date.fromisoformat(str(o.get("date")))
        except (ValueError, AttributeError):
            continue
        montant = o.get("montant_cts")
        if isinstance(montant, int):
            lues.append(OperationQif(jour, montant, str(o.get("libelle") or "")))
    return lues


def avec_mouvements(document: DocumentImport, operations: Sequence[OperationQif]) -> DocumentImport:
    """Un QIF déposé avant AXE-973 n'a pas gardé ses mouvements : ceux du
    fichier relu, en mémoire seulement."""
    donnees = dict(document.donnees or {})
    donnees["mouvements"] = [[o.jour.isoformat(), o.montant_cts] for o in operations]
    return replace(document, donnees=donnees)
