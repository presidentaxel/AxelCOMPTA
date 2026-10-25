"""Déclaration 2065-SD (impôt sur les sociétés) et son annexe 2065-bis-SD,
sur le **vrai formulaire officiel** (`cerfa/2065-sd_2026.pdf`, millésime
2026, sans champs AcroForm : overlay, ADR-006). Cellules repérées sur les
bordures réelles du PDF (pdfplumber), pas devinées.

Rempli depuis une `LiassePivot` de clôture fiscale (`cloturer(...,
parametres)`) :
- en-tête : exercice ouvert/clos, **régime simplifié d'imposition** (celui
  de la liasse 2033 jointe ; « réel normal » impliquerait la liasse 2050) ;
- cadre A : dénomination, siège, SIRET, courriel, principal établissement ;
- cadre B : activité exercée ;
- cadre C.1 : bénéfice ventilé entre taux réduit 15 % et taux normal, ou
  déficit ;
- cadre F : comptabilité informatisée (OUI, logiciel AxelCompta) ;
- bloc signataire : identité, date, lieu, qualité (la signature elle-même
  reste celle du dirigeant, doc 02 §2.3) ;
- 2065-bis cadre J (régime simplifié) : salaires et rétrocessions.

Cadres sans objet pour une SASU/EURL de chauffeur, laissés blancs comme sur
une vraie déclaration : groupe fiscal, plus-values, régimes d'exonération,
CES/CTM, crédits d'impôt, revenus locatifs, distributions (aucune).

Une `LiassePivot` historique (sans `ParametresCloture`) reste acceptée :
seuls l'exercice et le résultat sont alors remplis, comme avant.

Le dépôt légal du 2065 est dématérialisé (EDI/EFI, doc 02) : ce PDF sert
à la relecture et à la signature, pas à la télédéclaration.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from axelcompta.closing.models import LiassePivot
from axelcompta.core.identite import IdentiteEntreprise

from .overlay_cerfa import OverlayCerfa, formater_euros
from .renderer import FilingRenderer

CHEMIN_FORMULAIRE_OFFICIEL = Path(__file__).resolve().parent / "cerfa" / "2065-sd_2026.pdf"
LOGICIEL = "AxelCompta"

# Page 1, points PDF (origine bas-gauche), millésime 2026.
X_BENEFICE_TAUX_NORMAL = 484.0
X_DEFICIT = 577.0
Y_LIGNE_RESULTAT_FISCAL = 502.5
X_BENEFICE_15, Y_BENEFICE_15 = 188.0, 484.0
X_EXERCICE_OUVERT, X_EXERCICE_CLOS = 138.0, 253.0
Y_LIGNE_EXERCICE = 726.29
X_CASE_REGIME = 563.5
Y_REGIME_SIMPLIFIE, Y_REGIME_REEL_NORMAL = 726.5, 707.6
# Case à cocher OUI (263,7-278,2), pas le libellé « OUI » juste avant.
X_COMPTA_INFORMATISEE_OUI, X_COMPTA_INFORMATISEE_LOGICIEL = 271.0, 476.0
Y_LIGNE_COMPTA_INFORMATISEE = 150.0
SIRET_2065 = (
    103.4,
    117.8,
    132.2,
    146.6,
    161.0,
    175.4,
    190.2,
    204.6,
    219.0,
    233.4,
    247.8,
    263.7,
    278.2,
    292.6,
    307.4,
)
# Page 2 (2065-bis), cadre J : colonne des montants (250,7-312,1).
X_CADRE_J = 309.0
Y_SALAIRES, Y_RETROCESSIONS = 189.0, 166.0


def _euros(liasse: LiassePivot, cle: str) -> int:
    return liasse.cases.get(cle, 0) // 100


def _dessiner_resultat(overlay: OverlayCerfa, liasse: LiassePivot) -> None:
    if "2065.IMPOT" not in liasse.cases:
        # Liasse historique : un seul chiffre, bénéfice au taux normal ou déficit.
        resultat = liasse.cases.get("2065", 0)
        if resultat == 0:
            return
        x = X_BENEFICE_TAUX_NORMAL if resultat >= 0 else X_DEFICIT
        texte = formater_euros(abs(resultat) // 100) + f",{abs(resultat) % 100:02d}"
        overlay.texte_droite(1, x, Y_LIGNE_RESULTAT_FISCAL, texte, taille=9, gras=True)
        return
    y = Y_LIGNE_RESULTAT_FISCAL
    for cle, cellule in (
        ("2065.BENEFICE_TAUX_NORMAL", (0.0, X_BENEFICE_TAUX_NORMAL + 3, y)),
        ("2065.DEFICIT", (0.0, X_DEFICIT + 3, y)),
        ("2065.BENEFICE_TAUX_REDUIT", (0.0, X_BENEFICE_15 + 3, Y_BENEFICE_15)),
    ):
        if _euros(liasse, cle):
            overlay.montant(1, cellule, _euros(liasse, cle), gras=True)


def _dessiner_exercice(overlay: OverlayCerfa, liasse: LiassePivot) -> None:
    debut = (
        liasse.exercice_debut.strftime("%d/%m/%Y")
        if liasse.exercice_debut
        else f"01/01/{liasse.exercice}"
    )
    fin = (
        liasse.exercice_fin.strftime("%d/%m/%Y")
        if liasse.exercice_fin
        else f"31/12/{liasse.exercice}"
    )
    overlay.texte(1, X_EXERCICE_OUVERT, Y_LIGNE_EXERCICE, debut, 9)
    overlay.texte(1, X_EXERCICE_CLOS, Y_LIGNE_EXERCICE, fin, 9)
    # Avec la liasse 2033 (clôture fiscale) : régime simplifié. Sans :
    # comportement historique, régime réel normal.
    y_regime = Y_REGIME_SIMPLIFIE if "2033B.310" in liasse.cases else Y_REGIME_REEL_NORMAL
    overlay.croix(1, X_CASE_REGIME, y_regime)
    overlay.croix(1, X_COMPTA_INFORMATISEE_OUI, Y_LIGNE_COMPTA_INFORMATISEE)
    overlay.texte(1, X_COMPTA_INFORMATISEE_LOGICIEL, Y_LIGNE_COMPTA_INFORMATISEE, LOGICIEL)


def _dessiner_identification(overlay: OverlayCerfa, identite: IdentiteEntreprise) -> None:
    siege = identite.adresse_siege.sur_une_ligne()
    overlay.texte_ajuste(1, 27.0, 645.5, identite.denomination, 278.0, 9)
    overlay.texte_ajuste(1, 310.0, 645.5, siege, 268.0)
    overlay.cases(1, SIRET_2065, 633.0, identite.siret)
    overlay.texte_ajuste(1, 330.0, 633.0, identite.email, 248.0)
    overlay.texte_ajuste(1, 27.0, 608.5, siege, 278.0)
    overlay.texte_ajuste(1, 135.0, 528.5, f"{identite.activite} (APE {identite.code_ape})", 240.0)


def _dessiner_signataire(
    overlay: OverlayCerfa, identite: IdentiteEntreprise, date_etablissement: date
) -> None:
    dirigeant = identite.dirigeant
    nom = f"{dirigeant.prenoms} {dirigeant.nom}"
    overlay.texte_ajuste(1, 385.0, 80.5, nom, 192.0)
    overlay.texte(1, 330.0, 67.0, date_etablissement.strftime("%d/%m/%Y"))
    overlay.texte_ajuste(1, 455.0, 67.0, identite.adresse_siege.commune, 122.0)
    overlay.texte_ajuste(1, 415.0, 55.0, f"{dirigeant.qualite}, {nom}", 162.0)


def _dessiner_cadre_j(overlay: OverlayCerfa, liasse: LiassePivot) -> None:
    """Cadre J (régime simplifié) : deux montants. Une valeur à 0 reste
    vide — `OverlayCerfa.montant` n'écrit pas la case."""
    salaires = (0.0, X_CADRE_J + 3, Y_SALAIRES)
    overlay.montant(2, salaires, _euros(liasse, "2065J.SALAIRES"))
    overlay.montant(2, (0.0, X_CADRE_J + 3, Y_RETROCESSIONS), _euros(liasse, "2065J.RETROCESSIONS"))


class PdfCerfa2065Renderer(FilingRenderer):
    """`date_etablissement` : date portée dans le bloc signataire (par
    défaut aujourd'hui) — paramètre pour des tests reproductibles."""

    def __init__(self, date_etablissement: date | None = None) -> None:
        self._date = date_etablissement

    def rendre(self, liasse: LiassePivot) -> bytes:
        overlay = OverlayCerfa(CHEMIN_FORMULAIRE_OFFICIEL)
        self.dessiner(overlay, liasse)
        return overlay.rendre()

    def dessiner(self, overlay: OverlayCerfa, liasse: LiassePivot) -> None:
        _dessiner_exercice(overlay, liasse)
        _dessiner_resultat(overlay, liasse)
        if "2033B.310" in liasse.cases:
            _dessiner_cadre_j(overlay, liasse)
        if liasse.identite is not None:
            _dessiner_identification(overlay, liasse.identite)
            _dessiner_signataire(overlay, liasse.identite, self._date or date.today())
