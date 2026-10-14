"""Composition root : plusieurs vrais dossiers en même temps (doc 17
semaine 4 — « faire tourner sur 2-3 dossiers pour montrer que ce n'est pas
câblé en dur sur un seul cas ») + un rapport HTML qui montre les étapes du
pipeline (doc 17 §6 : « plutôt qu'une vraie UI — juste pour le récit
visuel »).

Réutilise `construire_ledger()` de `demo_dossier_reel.py` — pas un
troisième pipeline, le même, appliqué à plusieurs dossiers. Pour chaque
dossier : liasse PDF + CERFA 2065 + FEC + grand livre + balance (doc 06 §6,
doc 17 §7bis) dans un sous-dossier dédié, plus une ligne dans le rapport.

Usage : `python -m axelcompta.demo_multi_dossiers` depuis backend/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.models import LiassePivot
from axelcompta.core.ids import DossierId
from axelcompta.demo_dossier_reel import construire_ledger
from axelcompta.filings.cerfa_2065 import PdfCerfa2065Renderer
from axelcompta.filings.export_comptable import exporter_balance, exporter_grand_livre
from axelcompta.filings.fec import exporter_fec
from axelcompta.filings.liasse_simplifiee import PdfLiasseSimplifieeRenderer

DOSSIER_SORTIE_DEFAUT = Path(__file__).resolve().parent.parent / "_demo_output" / "multi_dossiers"

# 3 vrais dossiers, choisis pour leur richesse (doc 17 §2 reformulé par
# Louis : « ressembler à un produit »), pas triés sur le volet. Les deux
# derniers ont un exercice **partiel** (création en cours d'année) — bon
# test de la dérivation exercice_debut/fin (doc 06 §7).
DOSSIERS_DEMO: tuple[tuple[DossierId, int], ...] = (
    (DossierId("DOS_98279ecabf05"), 2024),
    (DossierId("DOS_a0df428fe565"), 2017),
    (DossierId("DOS_53b5e0df63b8"), 2021),
)


@dataclass(frozen=True, slots=True)
class ResultatDossier:
    dossier_id: DossierId
    annee: int
    liasse: LiassePivot
    nb_transactions: int
    dossier_sortie: Path


def _executer_un_dossier(dossier_id: DossierId, annee: int, racine_sortie: Path) -> ResultatDossier:
    dossier_sortie = racine_sortie / dossier_id
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    ledger = construire_ledger(dossier_id, annee)
    ecritures = ledger.grand_livre(dossier_id)
    liasse = ClotureSimplifieeService(ledger).cloturer(dossier_id, exercice=str(annee))

    (dossier_sortie / "liasse.pdf").write_bytes(PdfLiasseSimplifieeRenderer().rendre(liasse))
    (dossier_sortie / "cerfa_2065.pdf").write_bytes(PdfCerfa2065Renderer().rendre(liasse))
    (dossier_sortie / "journal.fec.txt").write_text(exporter_fec(ecritures), encoding="utf-8")
    (dossier_sortie / "grand_livre.csv").write_text(
        exporter_grand_livre(ecritures), encoding="utf-8"
    )
    (dossier_sortie / "balance.csv").write_text(exporter_balance(ecritures), encoding="utf-8")

    return ResultatDossier(dossier_id, annee, liasse, len(ecritures), dossier_sortie)


def _ligne_rapport(resultat: ResultatDossier) -> str:
    liasse = resultat.liasse
    debut = liasse.exercice_debut.isoformat() if liasse.exercice_debut else "?"
    fin = liasse.exercice_fin.isoformat() if liasse.exercice_fin else "?"
    dossier_relatif = resultat.dossier_sortie.name
    resultat_euros = liasse.cases.get("RESULTAT", 0) / 100
    return f"""
    <tr>
      <td>{resultat.dossier_id}</td>
      <td>{debut} → {fin}</td>
      <td>{resultat.nb_transactions}</td>
      <td>{liasse.cases.get("CA_HT", 0) / 100:.2f} €</td>
      <td>{liasse.cases.get("CHARGES", 0) / 100:.2f} €</td>
      <td class="{"perte" if resultat_euros < 0 else "profit"}">{resultat_euros:.2f} €</td>
      <td>
        <a href="{dossier_relatif}/liasse.pdf">liasse</a> ·
        <a href="{dossier_relatif}/cerfa_2065.pdf">CERFA 2065</a> ·
        <a href="{dossier_relatif}/journal.fec.txt">fichier des écritures (.txt)</a> ·
        <a href="{dossier_relatif}/grand_livre.csv">grand livre</a> ·
        <a href="{dossier_relatif}/balance.csv">balance</a>
      </td>
    </tr>"""


def generer_rapport_html(resultats: tuple[ResultatDossier, ...]) -> str:
    """doc 17 §6 : montre les étapes du pipeline, pas une vraie UI."""
    lignes = "".join(_ligne_rapport(r) for r in resultats)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>AxeLCompta — démo multi-dossiers</title>
<style>
  body {{ font-family: sans-serif; margin: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
  .perte {{ color: #b00020; }}
  .profit {{ color: #1b5e20; }}
</style></head>
<body>
<h1>AxeLCompta — démo sur {len(resultats)} vrais dossiers (doc 17 semaine 4)</h1>
<p>Pipeline pour chaque dossier : ingestion (FileImportProvider, chemin C)
→ catégorisation (règles + ML) → écriture (workflow/auto_accept) → clôture
→ liasse. Pas de settlement Rollee ici (aucune donnée historique) : le
chemin réconciliation/ventilation TVA plateforme est couvert séparément
par le golden test (doc 17 §7, <code>demo.py</code>).</p>
<table>
<tr><th>Dossier</th><th>Exercice</th><th>Écritures</th><th>CA HT</th>
<th>Charges</th><th>Résultat</th><th>Détail</th></tr>
{lignes}
</table>
</body></html>
"""


def executer(racine_sortie: Path | None = None) -> Path:
    racine_sortie = racine_sortie or DOSSIER_SORTIE_DEFAUT
    resultats = tuple(
        _executer_un_dossier(dossier_id, annee, racine_sortie)
        for dossier_id, annee in DOSSIERS_DEMO
    )
    chemin_rapport = racine_sortie / "rapport.html"
    chemin_rapport.parent.mkdir(parents=True, exist_ok=True)
    chemin_rapport.write_text(generer_rapport_html(resultats), encoding="utf-8")
    return chemin_rapport


def main() -> None:
    chemin = executer()
    print(f"Rapport multi-dossiers généré : {chemin}")


if __name__ == "__main__":
    main()
