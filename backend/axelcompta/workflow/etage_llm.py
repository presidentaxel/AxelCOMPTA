"""Étage LLM de la synchro : règles → modèle → **LLM** → humain (AXE-887).

Le LLM ne voit que les opérations restées au compte d'attente après les
règles et le modèle. Il propose une catégorie et n'impute jamais : la
proposition s'affiche, un humain tranche. Une opération que le modèle a
imputée seul n'arrive jamais ici ; un désaccord entre le modèle et le LLM
reste donc toujours à l'humain.

Deux temps, à chaque passage des tâches planifiées :

1. `relever` : les lots finis de l'API Batch deviennent des propositions,
   gardées par libellé normalisé (cache). Une réponse invalide ou
   incomplète devient « à vérifier » : le libellé ne repart pas.
2. `soumettre` : au plus un lot par dossier et par jour, seulement pour les
   libellés inconnus du cache, si le budget le permet et si le coupe-circuit
   est fermé. Le lot est réservé en base avant l'envoi : une synchro
   relancée ne le renvoie pas.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Protocol

from axelcompta.categorize.llm import (
    CATEGORIE_A_VERIFIER,
    VERSION_PROMPT,
    DemandeIa,
    lire_reponse,
    texte_operations,
)
from axelcompta.pseudonymize.detecter import FuiteDetectee
from axelcompta.pseudonymize.fournisseur_anthropic import RequeteLot, ResultatLot
from axelcompta.pseudonymize.service import Correspondance, pseudonymiser
from axelcompta.tenants.models import Dossier

from .budget_llm import (
    LIBELLES_PAR_LOT,
    RESERVATION_PERIMEE,
    Depenses,
    Lot,
    Plafonds,
    abandonnees,
    coupe_circuit,
    cout,
    echecs_par_cle,
    estimation,
    id_lot,
    max_tokens,
    refus_budget,
    soumis_le_jour,
)
from .lots_llm import LotsLlm
from .propositions_ia import PropositionIa, PropositionsIa, demandes_a_envoyer, parties_du_dossier

HISTORIQUE = timedelta(days=90)  # échecs et lots en cours au-delà : oubliés
MESSAGE_COUPE_CIRCUIT = "llm : coupe-circuit ouvert (trop d'échecs sur 24 h), aucun envoi"
JUSTIFICATION_INCOMPLETE = "réponse invalide ou incomplète"


class FournisseurLots(Protocol):
    modele: str

    @property
    def taille_systeme(self) -> int: ...

    def soumettre(self, requetes: list[RequeteLot]) -> str: ...

    def relever(self, batch_id: str) -> list[ResultatLot] | None: ...


@dataclass(frozen=True, slots=True)
class DossierATrancher:
    dossier: Dossier
    # (libellé, montant en centimes, type d'opération) des opérations au compte d'attente
    operations: tuple[tuple[str, int, str | None], ...]


@dataclass(frozen=True, slots=True)
class DepotsLlm:
    lots: LotsLlm
    propositions: PropositionsIa


def appliquer(
    lot: Lot, resultat: ResultatLot, categories: Sequence[str], maintenant: datetime
) -> tuple[Lot, list[PropositionIa]]:
    """Le lot relevé, et une proposition par libellé s'il a abouti."""
    fini = replace(
        lot,
        statut=resultat.statut,  # type: ignore[arg-type]
        termine_le=maintenant,
        cout_usd=cout(lot.modele, resultat.entree, resultat.sortie),
        jetons_entree=resultat.entree,
        jetons_sortie=resultat.sortie,
        jetons_cache=resultat.cache,
    )
    if resultat.statut != "termine":
        return fini, []
    demandes = [DemandeIa(cle, cle, 0) for cle in lot.cles]
    try:
        lues = {r.cle: r for r in lire_reponse(resultat.texte, demandes, categories)}
    except (ValueError, TypeError, AttributeError):
        lues = {}
    propositions = []
    for cle in lot.cles:
        reponse = lues.get(cle)
        propositions.append(
            PropositionIa(
                lot.dossier_id,
                cle,
                lot.version,
                reponse.categorie if reponse else CATEGORIE_A_VERIFIER,
                reponse.confiance if reponse else 0.0,
                reponse.justification if reponse else JUSTIFICATION_INCOMPLETE,
                lot.modele,
                maintenant,
            )
        )
    return fini, propositions


def _perimes(lots: Sequence[Lot], maintenant: datetime) -> list[Lot]:
    """Réservations jamais parties (la soumission a échoué en route)."""
    return [
        replace(lot, statut="echec", termine_le=maintenant)
        for lot in lots
        if lot.statut == "soumis"
        and lot.batch_id is None
        and maintenant - lot.soumis_le > RESERVATION_PERIMEE
    ]


def relever(
    depots: DepotsLlm,
    fournisseur: FournisseurLots,
    categories: Sequence[str],
    maintenant: datetime,
) -> list[str]:
    lots = depots.lots.lister(maintenant - HISTORIQUE)
    depots.lots.enregistrer(_perimes(lots, maintenant))
    par_batch: dict[str, list[Lot]] = defaultdict(list)
    for lot in lots:
        if lot.statut == "soumis" and lot.batch_id is not None:
            par_batch[lot.batch_id].append(lot)
    lignes = []
    for batch_id, du_batch in par_batch.items():
        resultats = fournisseur.relever(batch_id)
        if resultats is None:
            continue
        par_id = {r.custom_id: r for r in resultats}
        finis, propositions = [], []
        for lot in du_batch:
            fini, proposees = appliquer(
                lot, par_id.get(lot.id, ResultatLot(lot.id, "echec")), categories, maintenant
            )
            finis.append(fini)
            propositions += proposees
        depots.propositions.enregistrer(propositions)
        depots.lots.enregistrer(finis)
        lignes.append(f"llm : lot {batch_id} relevé, {len(propositions)} proposition(s)")
    return lignes


def _preparer(
    entree: DossierATrancher,
    lots: Sequence[Lot],
    propositions: PropositionsIa,
    fournisseur: FournisseurLots,
    maintenant: datetime,
) -> tuple[Lot, RequeteLot] | str | None:
    """Le lot du dossier, une raison de ne rien envoyer, ou None (rien à faire)."""
    dossier = entree.dossier
    du_dossier = [lot for lot in lots if lot.dossier_id == dossier.id]
    if soumis_le_jour(du_dossier, dossier.id, maintenant.date()):
        return None
    if any(lot.statut == "soumis" for lot in du_dossier):
        return None
    exclues = set(propositions.lister(dossier.id, VERSION_PROMPT)) | abandonnees(du_dossier)
    demandes = demandes_a_envoyer(entree.operations, exclues)[:LIBELLES_PAR_LOT]
    if not demandes:
        return None
    try:
        prompt = pseudonymiser(
            dossier.id, texte_operations(demandes), parties_du_dossier(dossier), Correspondance()
        )
    except FuiteDetectee:
        return f"llm {dossier.id} : pseudonymisation refusée, rien n'est envoyé"
    cles = tuple(d.cle for d in demandes)
    echecs = echecs_par_cle(du_dossier)
    tentative = 1 + max(echecs[cle] for cle in cles)
    caracteres = len(prompt.texte) + fournisseur.taille_systeme
    lot = Lot(
        id=id_lot(dossier.id, VERSION_PROMPT, cles, tentative),
        tenant_id=dossier.tenant_id,
        dossier_id=dossier.id,
        version=VERSION_PROMPT,
        modele=fournisseur.modele,
        cles=cles,
        statut="soumis",
        estimation_usd=estimation(fournisseur.modele, caracteres, len(cles)),
        soumis_le=maintenant,
    )
    if any(connu.id == lot.id and connu.batch_id is not None for connu in du_dossier):
        return None  # déjà soumis : idempotence
    return lot, RequeteLot(lot.id, prompt, max_tokens(len(cles)))


def soumettre(
    depots: DepotsLlm,
    fournisseur: FournisseurLots,
    a_trancher: Sequence[DossierATrancher],
    plafonds: Plafonds,
    maintenant: datetime,
) -> list[str]:
    lots = depots.lots.lister(maintenant - HISTORIQUE)
    if coupe_circuit(lots, maintenant):
        return [MESSAGE_COUPE_CIRCUIT]
    depenses = Depenses.du_mois(lots, maintenant)
    lignes: list[str] = []
    nouveaux: list[Lot] = []
    requetes: list[RequeteLot] = []
    for entree in a_trancher:
        prepare = _preparer(entree, lots, depots.propositions, fournisseur, maintenant)
        if prepare is None or isinstance(prepare, str):
            lignes += [prepare] if prepare else []
            continue
        lot, requete = prepare
        if refus := refus_budget(depenses, lot.dossier_id, lot.estimation_usd, plafonds):
            lignes.append(f"llm {lot.dossier_id} : {refus}, les opérations restent à l'humain")
            continue
        depenses.ajouter(lot)
        nouveaux.append(lot)
        requetes.append(requete)
    if not requetes:
        return lignes
    return lignes + _envoyer(depots, fournisseur, nouveaux, requetes, maintenant)


def _envoyer(
    depots: DepotsLlm,
    fournisseur: FournisseurLots,
    nouveaux: list[Lot],
    requetes: list[RequeteLot],
    maintenant: datetime,
) -> list[str]:
    """Réserve, envoie, puis note l'identifiant du lot Anthropic."""
    depots.lots.enregistrer(nouveaux)
    try:
        batch_id = fournisseur.soumettre(requetes)
    except Exception as exc:  # noqa: BLE001 — réessayé demain, les libellés n'y sont pour rien
        depots.lots.enregistrer(
            [replace(lot, statut="echec", termine_le=maintenant) for lot in nouveaux]
        )
        return [f"llm : soumission en échec ({type(exc).__name__})"]
    depots.lots.enregistrer([replace(lot, batch_id=batch_id) for lot in nouveaux])
    libelles = sum(len(lot.cles) for lot in nouveaux)
    return [f"llm : {len(nouveaux)} lot(s) soumis ({libelles} libellé(s)), lot {batch_id}"]
