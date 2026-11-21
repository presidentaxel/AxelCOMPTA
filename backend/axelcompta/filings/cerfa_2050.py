"""Liasse du régime réel normal, 2050 à 2059-G, sur le **vrai formulaire
officiel** (`cerfa/2050-liasse_2026.pdf`, impots.gouv.fr, millésime 2026,
sans champs AcroForm : overlay, ADR-006).

Les cases à code (« AB », « 1A », « 0G »…) viennent de
`cerfa/cases_2050-liasse_2026.json`, généré par
`scripts/extraire_cases_cerfa.py --alphanumerique`. Seuls le tableau
2059-A (lignes sans code) et la colonne « à un an au plus » du 2057 sont
positionnés ici.

Règle de remplissage : une case à zéro reste blanche, sauf les totaux du
bilan. Comme le 2033, ce PDF sert à la relecture et à la signature : le
dépôt légal est dématérialisé (doc 02).
"""

from __future__ import annotations

import json
from pathlib import Path

from axelcompta.closing.liasse_2050 import CIRCULANT, IMMOBILISE
from axelcompta.closing.liasse_2057 import CREANCES
from axelcompta.closing.models import LiassePivot

from .overlay_cerfa import Cellule, OverlayCerfa
from .renderer import FilingRenderer

DOSSIER_CERFA = Path(__file__).resolve().parent / "cerfa"
CHEMIN_FORMULAIRE_2050 = DOSSIER_CERFA / "2050-liasse_2026.pdf"
CHEMIN_CASES_2050 = DOSSIER_CERFA / "cases_2050-liasse_2026.json"

# Tableau de la liasse pivot → pages où chercher ses codes. Le bilan
# (`2050`) porte l'actif (page 1) et le passif (2051, page 2).
PAGES: dict[str, tuple[int, ...]] = {
    "2050": (1, 2),
    "2052": (3,),
    "2053": (4,),
    "2054": (5,),
    "2055": (7,),
    "2056": (8,),
    "2057": (9,),
    "2058A": (10,),
    "2058B": (11,),
    "2058C": (12,),
}
# Écrits même à zéro : totaux et résultat du bilan.
TOUJOURS = {"2050": frozenset({"CO", "1A", "DI", "DL", "EC", "EE"})}

# 2050, colonne 3 « Net » (sans code) : brut − amortissements, sur la ligne
# du brut. Le capital souscrit non appelé (AA) n'a pas d'amortissement.
X_NET_2050 = (480.8, 568.8)
PAIRES_NET = (*IMMOBILISE, *CIRCULANT, ("AA", ""), ("BJ", "BK"), ("CJ", "CK"), ("CO", "1A"))

# 2057, colonne « à un an au plus » : (x gauche, x droite) selon le cadre.
UN_AN_CREANCES = (392.7, 472.0)
UN_AN_DETTES = (315.7, 392.7)

# 2059-A (page 13) : colonnes et lignes 1 à 12, relevées sur les bordures.
PAGE_2059A = 13
COLONNES_2059A: dict[int, tuple[float, float]] = {
    2: (177.3, 244.7),
    3: (244.7, 312.1),
    4: (312.1, 378.2),
    5: (378.2, 444.0),
    6: (444.0, 547.0),
    7: (68.0, 146.8),
    8: (146.8, 230.6),
    9: (230.6, 285.3),
    10: (339.5, 391.2),  # long terme, 15 % ou 12,8 %
    11: (444.0, 547.0),
}
LIGNES_HAUT = (693.0, 680.0, 668.0, 655.0, 642.0, 629.0, 616.0, 603.0, 590.0, 577.0, 564.0, 551.0)
LIGNES_BAS = (489.0, 476.0, 463.0, 450.0, 437.0, 424.0, 411.0, 398.0, 385.0, 372.0, 359.0, 346.0)
# Cadres A, B, C : totaux des colonnes 9, 10 et 11.
TOTAUX_2059A: dict[int, Cellule] = {
    9: (230.6, 285.3, 198.0),
    10: (339.5, 391.2, 198.0),
    11: (444.0, 547.0, 198.0),
}


def charger_cases() -> dict[str, dict[str, list[float]]]:
    brut: dict[str, dict[str, list[float]]] = json.loads(
        CHEMIN_CASES_2050.read_text(encoding="utf-8")
    )
    return brut


def _euros(liasse: LiassePivot, tableau: str) -> dict[str, int]:
    """Toutes les clés du tableau, y compris `UX.1AN` ou `L1.C7`."""
    prefixe = f"{tableau}."
    return {
        cle[len(prefixe) :]: centimes // 100
        for cle, centimes in liasse.cases.items()
        if cle.startswith(prefixe)
    }


def cellule_2059a(code: str) -> Cellule | None:
    """`L<n>.C<colonne>` ou `TOTAL.C<colonne>` → cellule, ou None si le
    formulaire n'a pas de place pour elle (colonne 1, totaux 2 à 8)."""
    ligne, _, colonne = code.partition(".C")
    if not colonne.isdigit() or int(colonne) not in COLONNES_2059A:
        return None
    numero = int(colonne)
    if ligne == "TOTAL":
        return TOTAUX_2059A.get(numero)
    if not ligne.startswith("L") or not ligne[1:].isdigit():
        return None
    rang = int(ligne[1:]) - 1
    lignes = LIGNES_HAUT if numero <= 6 else LIGNES_BAS
    if not 0 <= rang < len(lignes):
        return None
    gauche, droite = COLONNES_2059A[numero]
    return (gauche, droite, lignes[rang])


class PdfLiasse2050Renderer(FilingRenderer):
    """Exige une `LiassePivot` clôturée avec `regime_liasse="2050"`."""

    def __init__(self) -> None:
        self._cases = charger_cases()

    def rendre(self, liasse: LiassePivot) -> bytes:
        if "2050.EE" not in liasse.cases:
            raise ValueError("liasse sans cases 2050 : clôturer avec regime_liasse='2050'")
        overlay = OverlayCerfa(CHEMIN_FORMULAIRE_2050)
        for tableau, pages in PAGES.items():
            self._tableau(overlay, liasse, tableau, pages)
        self._net(overlay, liasse)
        self._2059a(overlay, liasse)
        self._designation(overlay, liasse)
        return overlay.rendre()

    def cellule(self, pages: tuple[int, ...], code: str) -> tuple[int, Cellule] | None:
        for page in pages:
            c = self._cases[str(page)].get(code)
            if c is not None and not code.startswith("_"):
                return page, (c[0], c[1], c[2])
        return None

    def _tableau(
        self, overlay: OverlayCerfa, liasse: LiassePivot, tableau: str, pages: tuple[int, ...]
    ) -> None:
        toujours = TOUJOURS.get(tableau, frozenset())
        for code, euros in sorted(_euros(liasse, tableau).items()):
            if not euros and code not in toujours:
                continue
            if code.endswith(".1AN"):
                self._un_an(overlay, code.removesuffix(".1AN"), euros)
                continue
            trouvee = self.cellule(pages, code)
            if trouvee is not None:
                overlay.montant(trouvee[0], trouvee[1], euros, gras=code in toujours)

    def _net(self, overlay: OverlayCerfa, liasse: LiassePivot) -> None:
        euros = _euros(liasse, "2050")
        for brut, amort in PAIRES_NET:
            net = euros.get(brut, 0) - euros.get(amort, 0)
            trouvee = self.cellule((1,), brut)
            if trouvee is None or (not net and brut != "CO"):
                continue
            page, (_, _, y) = trouvee
            overlay.montant(page, (*X_NET_2050, y), net, gras=brut == "CO")

    def _un_an(self, overlay: OverlayCerfa, code: str, euros: int) -> None:
        trouvee = self.cellule(PAGES["2057"], code)
        if trouvee is None:
            return
        page, (_, _, y) = trouvee
        gauche, droite = UN_AN_CREANCES if code in set(CREANCES.values()) else UN_AN_DETTES
        overlay.montant(page, (gauche, droite, y), euros)

    def _2059a(self, overlay: OverlayCerfa, liasse: LiassePivot) -> None:
        for code, euros in _euros(liasse, "2059A").items():
            cellule = cellule_2059a(code)
            if cellule is not None:
                overlay.montant(PAGE_2059A, cellule, euros)

    def _designation(self, overlay: OverlayCerfa, liasse: LiassePivot) -> None:
        if liasse.identite is None:
            return
        for page, cases in self._cases.items():
            position = cases.get("_designation")
            if position is not None:
                overlay.texte(int(page), position[0], position[1], liasse.identite.denomination)
