"""Repère les cases numérotées d'un formulaire CERFA sans AcroForm (ADR-006)
et écrit leurs coordonnées dans un JSON versionné à côté du PDF.

Principe : chaque code de case (« 084 », « 310 »...) est imprimé dans une
petite cellule bordée ; la zone de saisie est la cellule suivante à droite.
On lit les bordures réelles du PDF (pdfplumber), rien n'est deviné. Un
nombre à trois chiffres qui n'est pas encadré serré (« art. 302 septies »)
n'est pas un code de case et est écarté.

À relancer à chaque nouveau millésime, puis vérifier le rendu à l'œil :
un overlay mal aligné ne lève aucune erreur (ADR-006).

Les formulaires du réel normal (2050-LIASSE) ont des codes à deux
caractères (« AB », « 1A », « ØG » lu « 0G », « K4bis ») : option
`--alphanumerique`. Elle relève aussi, par page, la place de la
désignation de l'entreprise (clé `_designation`).

Usage, depuis backend/ (pdfplumber : `pip install -e ".[dev]"`) :

    python scripts/extraire_cases_cerfa.py \\
        axelcompta/filings/cerfa/2033-sd_2026.pdf \\
        axelcompta/filings/cerfa/cases_2033-sd_2026.json
    python scripts/extraire_cases_cerfa.py --alphanumerique \\
        axelcompta/filings/cerfa/2050-liasse_2026.pdf \\
        axelcompta/filings/cerfa/cases_2050-liasse_2026.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pdfplumber

# Codes imprimés en dessin vectoriel (pas en texte) sur le millésime 2026 :
# page → code → (code de la même colonne, code de la même ligne).
DEDUITS = {"3": {"460": ("450", "462")}}
# 2050-LIASSE 2026 : code collé au libellé (« EXERCICEWS ») ; page → code →
# code de la même colonne. La ligne est celle du mot qui finit par le code.
COLLES = {"10": {"WS": "WR"}}
CODE_NUMERIQUE = r"\d{3}"
CODE_ALPHANUMERIQUE = r"[A-Z0-9Ø]{2}(?:bis)?"
MARGE_CADRE = 10.5  # écart max (pt) entre le code et les bords de sa cellule
LARGEUR_MIN_CELLULE = 2.0


def _bords_verticaux(page: Any, y_milieu: float) -> list[float]:
    return sorted(
        {
            round(float(e["x0"]), 1)
            for e in page.edges
            if e["orientation"] == "v" and e["top"] - 1 <= y_milieu <= e["bottom"] + 1
        }
    )


def _case(page: Any, mot: dict[str, Any]) -> list[float] | None:
    """[x_gauche, x_droite, y_ligne_de_base] de la zone de saisie, ou None."""
    bords = _bords_verticaux(page, (mot["top"] + mot["bottom"]) / 2)
    gauche = [x for x in bords if x <= mot["x0"] + 0.5]
    droite = [x for x in bords if x >= mot["x1"] - 0.5]
    if not gauche or not droite:
        return None
    if mot["x0"] - gauche[-1] > MARGE_CADRE or droite[0] - mot["x1"] > MARGE_CADRE:
        return None
    suivants = [x for x in droite[1:] if x - droite[0] > LARGEUR_MIN_CELLULE]
    if not suivants:
        return None
    hauteur = float(page.height)
    return [droite[0], suivants[0], round(hauteur - float(mot["bottom"]), 1)]


def _designation(page: Any) -> list[float] | None:
    """[x, y] juste après « Désignation de l'entreprise », et après le trait
    vertical qui ferme le libellé s'il y en a un tout près."""
    mots = page.extract_words()
    for avant, mot in zip(mots, mots[1:], strict=False):
        if avant["text"] == "de" and mot["text"].startswith("l'entreprise"):
            fin = float(mot["x1"])
            traits = [
                x for x in _bords_verticaux(page, (mot["top"] + mot["bottom"]) / 2) if x > fin
            ]
            x = traits[0] + 4 if traits and traits[0] - fin < 60 else fin + 6
            return [round(x, 1), round(float(page.height - mot["bottom"]), 1)]
    return None


def _colles(page: Any, numero: str, cases: dict[str, list[float]]) -> None:
    for code, meme_colonne in COLLES.get(numero, {}).items():
        for mot in page.extract_words():
            if len(mot["text"]) > len(code) and mot["text"].endswith(code):
                x_gauche, x_droite, _ = cases[meme_colonne]
                y = round(float(page.height - mot["bottom"]), 1)
                cases[code] = [x_gauche, x_droite, y]
                break


def _cases_page(page: Any, motif: str) -> dict[str, list[float]]:
    cases: dict[str, list[float]] = {}
    for mot in page.extract_words():
        texte = mot["text"].rstrip("–-")
        code = texte.replace("Ø", "0")
        if not re.fullmatch(motif, texte) or code in cases:
            continue
        case = _case(page, {**mot, "text": texte})
        if case is not None:
            cases[code] = case
    return cases


def extraire(chemin_pdf: Path, alphanumerique: bool = False) -> dict[str, dict[str, list[float]]]:
    motif = CODE_ALPHANUMERIQUE if alphanumerique else CODE_NUMERIQUE
    resultat: dict[str, dict[str, list[float]]] = {}
    with pdfplumber.open(chemin_pdf) as pdf:
        for numero, page in enumerate(pdf.pages, start=1):
            cases = _cases_page(page, motif)
            if alphanumerique:
                _colles(page, str(numero), cases)
                designation = _designation(page)
                if designation is not None:
                    cases["_designation"] = designation
            resultat[str(numero)] = cases
    if alphanumerique:
        return resultat
    for numero_page, deduits in DEDUITS.items():
        for code, (meme_colonne, meme_ligne) in deduits.items():
            x_gauche, x_droite, _ = resultat[numero_page][meme_colonne]
            resultat[numero_page][code] = [x_gauche, x_droite, resultat[numero_page][meme_ligne][2]]
    return resultat


def main() -> int:
    arguments = sys.argv[1:]
    alphanumerique = "--alphanumerique" in arguments
    source, cible = (Path(a) for a in arguments if a != "--alphanumerique")
    cases = extraire(source, alphanumerique)
    cible.write_text(json.dumps(cases, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for page, codes in cases.items():
        print(f"page {page} : {len(codes)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
