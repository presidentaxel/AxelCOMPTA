"""Déclaration 2031-SD (bénéfices industriels et commerciaux, impôt sur le
revenu) et son annexe 2031-bis-SD, sur le **vrai formulaire officiel**
(`cerfa/2031-sd_2026.pdf`, millésime 2026, n° 11085*28, sans champs
AcroForm : overlay, ADR-006). Cellules relevées sur les bordures réelles du
PDF (pdfplumber), pas devinées.

Pendant de la 2065 pour la colonne à l'IR de la matrice (doc 06 §7) :
société à l'IR (EURL, SARL de famille, option 239 bis AB) ou entreprise
individuelle au réel. Rempli depuis une `LiassePivot` de clôture fiscale
avec `soumis_is` faux :
- en-tête : exercice ouvert/clos, régime simplifié (liasse 2033 jointe) ;
- cadre A : dénomination, adresse, courriel, SIREN ;
- cadre B : activité exercée ;
- cadre C, lignes 1, 3 et 4 : bénéfice (370) ou déficit (372) de la 2033-B,
  puis bénéfice imposable ou déficit déductible ;
- cadre C.9 : comptabilité informatisée (OUI, logiciel AxelCompta) ;
- bloc déclarant : identité, lieu, date, qualité ;
- 2031-bis cadre E (sociétés seulement) : chaque associé, sa qualité de
  gérant, « B » (BIC professionnels) et sa quote-part du résultat au
  prorata de ses titres ;
- 2031-bis cadre H : salaires et rétrocessions, écrits même nuls.

Cadres sans objet pour un chauffeur, laissés blancs : revenus de capitaux
mobiliers, plus-values, exonérations, BIC non professionnels, régime des
sociétés de personnes, contribution temporaire de solidarité.

Comme la 2065, ce PDF sert à la relecture et à la signature ; le dépôt
légal est dématérialisé (EDI/EFI, doc 02).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from axelcompta.closing.models import LiassePivot
from axelcompta.core.identite import IdentiteEntreprise

from .overlay_cerfa import OverlayCerfa, formater_euros
from .renderer import FilingRenderer

CHEMIN_FORMULAIRE_OFFICIEL = Path(__file__).resolve().parent / "cerfa" / "2031-sd_2026.pdf"
LOGICIEL = "AxelCompta"
PAGES_REMPLIES = 2  # 2031-SD + 2031-bis-SD ; les 2 suivantes sont la notice

# Page 1, points PDF (origine bas-gauche), millésime 2026. La case OUI de la
# comptabilité informatisée est la cellule vide qui suit le libellé.
X_DATES = 123.0
Y_EXERCICE_OUVERT, Y_EXERCICE_CLOS = 718.3, 708.0
X_CASE_SIMPLIFIE, Y_CASE_SIMPLIFIE = 454.7, 718.0
SIREN_2031 = (163.8, 177.8, 194.5, 209.6, 224.7, 239.3, 253.8, 268.5, 283.5, 299.2)
Y_SIREN = 624.8
# Cadre C : colonne 1 (bénéfice) 432,3-504,6, colonne 2 (déficit) 504,6-571,5.
X_COL_1, X_COL_2 = 504.6, 571.5
Y_LIGNE_1, Y_LIGNE_3, Y_LIGNE_4 = 567.5, 505.0, 494.6
X_COMPTA_OUI, X_LOGICIEL, Y_COMPTA = 261.1, 423.0, 128.3

# Page 2 (2031-bis). Cadre E : 5 lignes d'associés.
Y_LIGNES_CADRE_E = (646.0, 631.3, 616.6, 601.9, 587.1)
X_NOM_ASSOCIE, LARGEUR_NOM = 15.0, 191.0
X_GERANT, X_BIC, X_QUOTE_PART = 224.7, 277.2, 470.9
# Cadre H : colonne des montants 493,3-567,7.
X_CADRE_H = 567.7
Y_SALAIRES, Y_RETROCESSIONS = 344.0, 329.5


def _euros(liasse: LiassePivot, cle: str) -> int:
    return liasse.cases.get(cle, 0) // 100


def _dessiner_entete(overlay: OverlayCerfa, liasse: LiassePivot) -> None:
    debut = liasse.exercice_debut or date(int(liasse.exercice), 1, 1)
    fin = liasse.exercice_fin or date(int(liasse.exercice), 12, 31)
    overlay.texte(1, X_DATES, Y_EXERCICE_OUVERT, debut.strftime("%d/%m/%Y"), 9)
    overlay.texte(1, X_DATES, Y_EXERCICE_CLOS, fin.strftime("%d/%m/%Y"), 9)
    overlay.croix(1, X_CASE_SIMPLIFIE, Y_CASE_SIMPLIFIE)
    overlay.croix(1, X_COMPTA_OUI, Y_COMPTA)
    overlay.texte(1, X_LOGICIEL, Y_COMPTA, LOGICIEL)


def _dessiner_resultat(overlay: OverlayCerfa, liasse: LiassePivot) -> None:
    benefice = _euros(liasse, "2031.BENEFICE")
    deficit = _euros(liasse, "2031.DEFICIT")
    for y in (Y_LIGNE_1, Y_LIGNE_3):
        if benefice:
            overlay.montant(1, (0.0, X_COL_1, y), benefice, gras=y == Y_LIGNE_1)
        if deficit:
            overlay.montant(1, (0.0, X_COL_2, y), deficit, gras=y == Y_LIGNE_1)
    net = benefice - deficit
    if net >= 0:
        overlay.montant(1, (0.0, X_COL_1, Y_LIGNE_4), net, gras=True)
    else:
        overlay.montant(1, (0.0, X_COL_2, Y_LIGNE_4), -net, gras=True)


def _dessiner_identification(overlay: OverlayCerfa, identite: IdentiteEntreprise) -> None:
    siege = identite.adresse_siege.sur_une_ligne()
    overlay.texte_ajuste(1, 123.0, 669.0, identite.denomination, 175.0, 9)
    overlay.texte_ajuste(1, 105.0, 656.5, siege, 193.0)
    overlay.texte_ajuste(1, 44.0, 645.0, identite.email, 254.0)
    overlay.cases(1, SIREN_2031, Y_SIREN, identite.siren)
    overlay.texte_ajuste(1, 459.5, 602.3, f"{identite.activite} (APE {identite.code_ape})", 110.0)


def _dessiner_declarant(
    overlay: OverlayCerfa, identite: IdentiteEntreprise, date_etablissement: date
) -> None:
    dirigeant = identite.dirigeant
    nom = f"{dirigeant.prenoms} {dirigeant.nom}"
    overlay.texte_ajuste(1, 369.0, 67.0, nom, 200.0)
    overlay.texte_ajuste(1, 318.0, 56.5, identite.adresse_siege.commune, 97.0)
    overlay.texte(1, 437.0, 56.5, date_etablissement.strftime("%d/%m/%Y"))
    overlay.texte_ajuste(1, 392.0, 46.0, f"{dirigeant.qualite}, {nom}", 177.0)


def _dessiner_associes(overlay: OverlayCerfa, liasse: LiassePivot) -> None:
    """Quote-part au prorata des titres, arrondie à l'euro ; le dernier
    associé prend l'écart d'arrondi pour que la somme retombe juste."""
    identite = liasse.identite
    if identite is None or not liasse.associes or not identite.associes:
        return
    resultat = _euros(liasse, "2031.BENEFICE") - _euros(liasse, "2031.DEFICIT")
    total_titres = sum(a.nb_titres for a in identite.associes) or 1
    reparti = 0
    associes = identite.associes[: len(Y_LIGNES_CADRE_E)]
    for rang, (associe, y) in enumerate(zip(associes, Y_LIGNES_CADRE_E, strict=False)):
        dernier = rang == len(associes) - 1
        part = resultat - reparti if dernier else round(resultat * associe.nb_titres / total_titres)
        reparti += part
        nom = f"{associe.prenoms} {associe.nom}, {associe.adresse.sur_une_ligne()}"
        overlay.texte_ajuste(2, X_NOM_ASSOCIE, y, nom, LARGEUR_NOM, 6.5)
        if "gérant" in associe.qualite.lower():
            overlay.croix(2, X_GERANT, y)
        overlay.texte(2, X_BIC, y, "B")
        texte = "" if part == 0 else ("-" if part < 0 else "") + formater_euros(abs(part))
        overlay.texte_droite(2, X_QUOTE_PART - 3, y, texte)


def _dessiner_cadre_h(overlay: OverlayCerfa, liasse: LiassePivot) -> None:
    overlay.montant(2, (0.0, X_CADRE_H, Y_SALAIRES), _euros(liasse, "2031H.SALAIRES"))
    overlay.montant(2, (0.0, X_CADRE_H, Y_RETROCESSIONS), _euros(liasse, "2031H.RETROCESSIONS"))


class PdfCerfa2031Renderer(FilingRenderer):
    """`date_etablissement` : date portée dans le bloc déclarant (par défaut
    aujourd'hui) — paramètre pour des tests reproductibles."""

    def __init__(self, date_etablissement: date | None = None) -> None:
        self._date = date_etablissement

    def rendre(self, liasse: LiassePivot) -> bytes:
        if liasse.soumis_is:
            raise ValueError("la 2031 est la déclaration de l'IR ; à l'IS, c'est la 2065")
        overlay = OverlayCerfa(CHEMIN_FORMULAIRE_OFFICIEL)
        _dessiner_entete(overlay, liasse)
        _dessiner_resultat(overlay, liasse)
        _dessiner_cadre_h(overlay, liasse)
        if liasse.identite is not None:
            _dessiner_identification(overlay, liasse.identite)
            _dessiner_declarant(overlay, liasse.identite, self._date or date.today())
            _dessiner_associes(overlay, liasse)
        return overlay.rendre()
