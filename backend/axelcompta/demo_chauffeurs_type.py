"""Composition root : démo produit sur 3 chauffeurs type synthétiques
(pivot 2026-09-06, doc 17 §4, doc 19). Remplace le CSV audit comme source
de la démo (`demo_multi_dossiers.py`, l'ancienne version de ce plan) — même
pipeline (réconciliation → écriture settlement ventilée TVA → catégorisation
règles/ML pour le reste → clôture → liasse), sur des données fabriquées à
la main mais avec de **vrais calculs** (doc 17 §1 : « on veut voir si ça
déconne, pas s'enfermer dans les cas limites »).

Contrairement à `demo_dossier_reel.py`/`demo_multi_dossiers.py`, aucun
fichier externe gitignored n'est requis (ni CSV audit, ni modèle .joblib) —
`chauffeurs_demo.py` génère tout de façon déterministe. Tourne sur
n'importe quel clone du repo, sans setup préalable.

Usage : `python -m axelcompta.demo_chauffeurs_type` depuis backend/.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from axelcompta.categorize.ml_fallback import ModeleMlIndisponible, ModeleSklearn, charger_modele
from axelcompta.categorize.models import ProposedEntry
from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.models import LiassePivot, ParametresCloture
from axelcompta.core.ids import EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.core.pcg import COMPTE_BANQUE
from axelcompta.demo_identites import IDENTITES_DEMO
from axelcompta.filings.cerfa_2065 import PdfCerfa2065Renderer
from axelcompta.filings.export_comptable import exporter_balance, exporter_grand_livre
from axelcompta.filings.fec import exporter_fec
from axelcompta.filings.liasse_fiscale import PdfLiasseFiscaleRenderer
from axelcompta.filings.liasse_simplifiee import PdfLiasseSimplifieeRenderer
from axelcompta.ingestion.ecritures_settlement import construire_ecriture_settlement
from axelcompta.ingestion.providers.base import NormalizedTransaction, PlatformSettlement
from axelcompta.ingestion.providers.chauffeurs_demo import PROFILS_DEMO as PROFILS_DEMO
from axelcompta.ingestion.providers.chauffeurs_demo import (
    ChauffeurTypeProvider,
    ProfilChauffeurType,
)
from axelcompta.ingestion.reconciliation import EtatReconciliation, reconcilier
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.packs.vtc_demo import charger_compte_par_categorie, charger_regles
from axelcompta.workflow.auto_accept import construire_ecriture_categorisee

TENANT_DEMO = TenantId("demo")
DOSSIER_SORTIE_DEFAUT = Path(__file__).resolve().parent.parent / "_demo_output" / "chauffeurs_type"
# Assez large pour couvrir toute la période générée (~230 jours calendaires
# pour 200 jours actifs, doc 17 §4) sans avoir à la recalculer ici.
FENETRE_JOURS = 400


def _charger_modele_ou_rien() -> ModeleSklearn | None:
    """Dégradation explicite si le modèle .joblib est absent (doc 08 §5) —
    n'arrive jamais en pratique ici : toutes les dépenses générées matchent
    une règle du pack (doc 17 §4bis), le ML n'est jamais sollicité."""
    try:
        return charger_modele()
    except ModeleMlIndisponible:
        return None


async def _recuperer_donnees(
    profil: ProfilChauffeurType,
) -> tuple[tuple[NormalizedTransaction, ...], tuple[PlatformSettlement, ...]]:
    provider = ChauffeurTypeProvider(profil)
    depuis = profil.date_debut
    jusqua = profil.date_debut + timedelta(days=FENETRE_JOURS)
    transactions = await provider.fetch_transactions(TENANT_DEMO, profil.dossier_id, depuis, jusqua)
    settlements = await provider.fetch_platform_settlements(
        TENANT_DEMO, profil.dossier_id, depuis, jusqua
    )
    return tuple(transactions), tuple(settlements)


def construire_ledger(
    profil: ProfilChauffeurType,
) -> tuple[InMemoryLedgerService, dict[EcritureId, ProposedEntry]]:
    """Cœur réutilisable, même structure que `demo.py`/`demo_dossier_reel.py` :
    settlement réconcilié → écriture ventilée TVA (régime du **profil**,
    doc 17 §4.3 — plus figé en dur comme dans la première version de ce
    module, doc 13 §5.1) ; le reste des transactions → règles + ML +
    auto-accept (stand-in, doc 17 §5 : remplacé côté UI par la vraie file de
    revue quand elle existera, notamment pour la dépense de Sophie).

    Retourne aussi la `ProposedEntry` d'origine de chaque écriture catégorisée
    (pas les écritures de settlement, qui n'en ont pas) — nécessaire au bloc
    C (doc 17 §9) pour enregistrer `etage_origine`/`confiance_origine` sur
    une `DecisionHumaine` quand la file de revue résout un cas comme celui
    de Sophie. Trouvé en construisant la persistance des décisions
    (2026-09-07) : cette proposition était calculée puis jetée juste après.
    """
    transactions, settlements = asyncio.run(_recuperer_donnees(profil))
    resultats = reconcilier(transactions, settlements)

    ledger = InMemoryLedgerService()
    ledger.enregistrer(ecriture_apport_capital(profil))
    propositions: dict[EcritureId, ProposedEntry] = {}
    id_transactions_reconciliees = {
        r.transaction.id for r in resultats if r.transaction is not None
    }
    for numero, resultat in enumerate(resultats, start=1):
        if resultat.etat is EtatReconciliation.RECONCILIE and resultat.transaction is not None:
            ecriture = construire_ecriture_settlement(
                resultat.transaction,
                resultat.settlement,
                numero,
                tva_recettes_regime=profil.tva_recettes_regime,
            )
            ledger.enregistrer(ecriture)

    pipeline = RulesAndMlPipeline(regles=charger_regles(), modele=_charger_modele_ou_rien())
    comptes = charger_compte_par_categorie()
    for numero, transaction in enumerate(transactions, start=1):
        if transaction.id in id_transactions_reconciliees:
            continue
        proposition = pipeline.categoriser(profil.dossier_id, transaction)
        compte = comptes.get(proposition.categorie, "471")  # 471 : compte d'attente par défaut
        ecriture = construire_ecriture_categorisee(transaction, proposition, compte, numero)
        ledger.enregistrer(ecriture)
        propositions[ecriture.id] = proposition
    return ledger, propositions


def fin_exercice(profil: ProfilChauffeurType) -> date:
    """Société créée le premier jour des données, premier exercice clos au
    31/12 de la même année (doc 06 §7 : un premier exercice peut être court)."""
    return date(profil.date_debut.year, 12, 31)


def parametres_cloture(profil: ProfilChauffeurType) -> ParametresCloture:
    return ParametresCloture(
        exercice_debut=profil.date_debut,
        exercice_fin=fin_exercice(profil),
        forme_juridique=profil.forme_juridique,
        identite=IDENTITES_DEMO[profil.dossier_id],
    )


def ecriture_apport_capital(profil: ProfilChauffeurType) -> Ecriture:
    """Libération du capital à la création de la société, premier jour de
    l'exercice : sans elle, le bilan d'une SASU/EURL afficherait un capital
    nul (2033-A ligne 120), ce qui n'existe pas."""
    capital = Money(IDENTITES_DEMO[profil.dossier_id].capital_social_cts)
    return Ecriture(
        id=EcritureId("apport-capital"),
        dossier_id=profil.dossier_id,
        journal=Journal.BQ,
        date=profil.date_debut,
        libelle="Libération du capital social",
        reference_piece="STATUTS",
        lignes=(
            LigneEcriture(compte=COMPTE_BANQUE, sens=Sens.DEBIT, montant=capital),
            LigneEcriture(compte="1013", sens=Sens.CREDIT, montant=capital),
        ),
    )


@dataclass(frozen=True, slots=True)
class ResultatChauffeur:
    profil: ProfilChauffeurType
    liasse: LiassePivot
    nb_transactions: int
    nb_settlements_reconcilies: int
    nb_settlements_total: int
    dossier_sortie: Path


def _executer_un_chauffeur(profil: ProfilChauffeurType, racine_sortie: Path) -> ResultatChauffeur:
    dossier_sortie = racine_sortie / profil.dossier_id
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    # Reconstruit la réconciliation pour le rapport (mêmes données, seed
    # déterministe : pas de coût réel à regénérer une deuxième fois).
    transactions, settlements = asyncio.run(_recuperer_donnees(profil))
    nb_reconcilies = sum(
        1 for r in reconcilier(transactions, settlements) if r.etat is EtatReconciliation.RECONCILIE
    )

    ledger, _propositions = construire_ledger(profil)
    exercice = str(profil.date_debut.year)
    cloture = ClotureSimplifieeService(ledger)
    parametres = parametres_cloture(profil)
    liasse = cloture.cloturer(profil.dossier_id, exercice=exercice, parametres=parametres)
    ecritures = cloture.ecritures_exercice_completes(profil.dossier_id, parametres)

    (dossier_sortie / "liasse.pdf").write_bytes(PdfLiasseSimplifieeRenderer().rendre(liasse))
    (dossier_sortie / "cerfa_2065.pdf").write_bytes(PdfCerfa2065Renderer().rendre(liasse))
    (dossier_sortie / "liasse_fiscale.pdf").write_bytes(PdfLiasseFiscaleRenderer().rendre(liasse))
    (dossier_sortie / "journal.fec.txt").write_text(exporter_fec(ecritures), encoding="utf-8")
    (dossier_sortie / "grand_livre.csv").write_text(
        exporter_grand_livre(ecritures), encoding="utf-8"
    )
    (dossier_sortie / "balance.csv").write_text(exporter_balance(ecritures), encoding="utf-8")

    return ResultatChauffeur(
        profil=profil,
        liasse=liasse,
        nb_transactions=len(ecritures),
        nb_settlements_reconcilies=nb_reconcilies,
        nb_settlements_total=len(settlements),
        dossier_sortie=dossier_sortie,
    )


def _ligne_rapport(resultat: ResultatChauffeur) -> str:
    liasse = resultat.liasse
    profil = resultat.profil
    debut = liasse.exercice_debut.isoformat() if liasse.exercice_debut else "?"
    fin = liasse.exercice_fin.isoformat() if liasse.exercice_fin else "?"
    dossier_relatif = resultat.dossier_sortie.name
    resultat_euros = liasse.cases.get("RESULTAT", 0) / 100
    plateformes = ", ".join(p.nom for p in profil.plateformes)
    return f"""
    <tr>
      <td>{profil.nom} <span class="dossier">({profil.dossier_id})</span></td>
      <td>{profil.tva_recettes_regime}</td>
      <td>{plateformes}</td>
      <td>{debut} → {fin}</td>
      <td>{resultat.nb_transactions}</td>
      <td>{resultat.nb_settlements_reconcilies}/{resultat.nb_settlements_total}</td>
      <td>{liasse.cases.get("CA_HT", 0) / 100:.2f} €</td>
      <td>{liasse.cases.get("CHARGES", 0) / 100:.2f} €</td>
      <td class="{"perte" if resultat_euros < 0 else "profit"}">{resultat_euros:.2f} €</td>
      <td>
        <a href="{dossier_relatif}/liasse_fiscale.pdf">liasse fiscale 2065 + 2033</a> ·
        <a href="{dossier_relatif}/liasse.pdf">liasse simplifiée</a> ·
        <a href="{dossier_relatif}/cerfa_2065.pdf">CERFA 2065</a> ·
        <a href="{dossier_relatif}/journal.fec.txt">FEC</a> ·
        <a href="{dossier_relatif}/grand_livre.csv">grand livre</a> ·
        <a href="{dossier_relatif}/balance.csv">balance</a>
      </td>
    </tr>"""


def generer_rapport_html(resultats: tuple[ResultatChauffeur, ...]) -> str:
    """Rapport visuel de la démo (doc 17 §6 : « pas une vraie UI » — l'UI
    réelle, gestionnaire et chauffeur, est l'objet des semaines suivantes
    du nouveau plan, doc 19)."""
    lignes = "".join(_ligne_rapport(r) for r in resultats)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>AxeLCompta — démo produit, 3 chauffeurs type</title>
<style>
  body {{ font-family: sans-serif; margin: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
  .dossier {{ color: #888; font-size: 0.85em; }}
  .perte {{ color: #b00020; }}
  .profit {{ color: #1b5e20; }}
</style></head>
<body>
<h1>AxeLCompta — démo produit sur 3 chauffeurs type (doc 17 §4, pivot 2026-09-06)</h1>
<p>Données synthétiques mais réalistes (jusqu'à 5-6 courses/jour, ~200 jours
d'activité, pourboires) — pas le CSV audit historique. Pipeline pour chaque
dossier : ingestion (settlements + transactions générés) → réconciliation
réelle → écriture ventilée TVA selon le régime du dossier → catégorisation
règles/ML pour le reste → clôture → liasse. Le régime TVA change d'un
dossier à l'autre (Yanis est en franchise, doc 17 §4.3) — même moteur,
configuration différente, aucune branche de code par dossier.</p>
<table>
<tr><th>Chauffeur</th><th>Régime TVA</th><th>Plateformes</th><th>Exercice</th>
<th>Écritures</th><th>Settlements réconciliés</th><th>CA HT</th>
<th>Charges</th><th>Résultat</th><th>Détail</th></tr>
{lignes}
</table>
<p><strong>Sophie</strong> a une dépense carte pro à consonance personnelle
(Zara) dans son mois : elle atterrit au compte d'attente 471, pas sur un
compte de résultat — la catégorisation la signale comme « à trancher »
(règle <code>usage_personnel_suspect</code>, confiance moyenne) mais aucune
UI de revue humaine n'existe encore pour la valider en 455/108 (doc 17
§11). C'est le comportement voulu à ce stade, pas un bug.</p>
</body></html>
"""


def executer(racine_sortie: Path | None = None) -> Path:
    racine_sortie = racine_sortie or DOSSIER_SORTIE_DEFAUT
    resultats = tuple(_executer_un_chauffeur(profil, racine_sortie) for profil in PROFILS_DEMO)
    chemin_rapport = racine_sortie / "rapport.html"
    chemin_rapport.parent.mkdir(parents=True, exist_ok=True)
    chemin_rapport.write_text(generer_rapport_html(resultats), encoding="utf-8")
    return chemin_rapport


def main() -> None:
    chemin = executer()
    print(f"Rapport 3 chauffeurs type généré : {chemin}")


if __name__ == "__main__":
    main()
