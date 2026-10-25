"""Écriture par-dessus un formulaire CERFA officiel sans champs AcroForm
(ADR-006) : une couche reportlab par page, fusionnée sur l'original.

Coordonnées en points PDF, origine en bas à gauche, relevées sur les
bordures réelles du formulaire (`scripts/extraire_cases_cerfa.py`).
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

POLICE = "Helvetica"
POLICE_GRAS = "Helvetica-Bold"
TAILLE_MONTANT = 8.0
TAILLE_TEXTE = 8.0
MARGE_DROITE = 3.0

# Cellule de saisie : (x gauche, x droite, y ligne de base du code imprimé).
Cellule = tuple[float, float, float]


def formater_euros(euros: int) -> str:
    """Format de la liasse : euros entiers, espace comme séparateur de
    milliers, signe moins devant un montant négatif (« -1 346 »)."""
    return f"{euros:,}".replace(",", " ")


def texte_case(euros: int) -> str | None:
    """Une case officielle à 0 reste vide. Un montant non nul est inchangé."""
    if euros == 0:
        return None
    return formater_euros(euros)


def formater_date(jour: int, mois: int, annee: int) -> str:
    return f"{jour:02d}{mois:02d}{annee:04d}"


class OverlayCerfa:
    def __init__(self, chemin_formulaire: Path) -> None:
        self._writer = PdfWriter(clone_from=chemin_formulaire)
        self._calques: dict[int, tuple[io.BytesIO, canvas.Canvas]] = {}

    def _calque(self, page: int) -> canvas.Canvas:
        """`page` numérotée à partir de 1, comme sur le formulaire."""
        if page not in self._calques:
            boite = self._writer.pages[page - 1].mediabox
            tampon = io.BytesIO()
            dessin = canvas.Canvas(tampon, pagesize=(float(boite.width), float(boite.height)))
            self._calques[page] = (tampon, dessin)
        return self._calques[page][1]

    def texte(
        self,
        page: int,
        x: float,
        y: float,
        valeur: str,
        taille: float = TAILLE_TEXTE,
        gras: bool = False,
    ) -> None:
        if not valeur:
            return
        dessin = self._calque(page)
        dessin.setFont(POLICE_GRAS if gras else POLICE, taille)
        dessin.drawString(x, y, valeur)

    def texte_ajuste(
        self,
        page: int,
        x: float,
        y: float,
        valeur: str,
        largeur_max: float,
        taille: float = TAILLE_TEXTE,
    ) -> None:
        """Réduit la police jusqu'à ce que le texte tienne dans la cellule
        (une adresse longue ne déborde jamais sur la case voisine)."""
        while taille > 5 and stringWidth(valeur, POLICE, taille) > largeur_max:
            taille -= 0.5
        self.texte(page, x, y, valeur, taille)

    def texte_droite(
        self,
        page: int,
        x_droite: float,
        y: float,
        valeur: str,
        taille: float = TAILLE_MONTANT,
        gras: bool = False,
    ) -> None:
        dessin = self._calque(page)
        dessin.setFont(POLICE_GRAS if gras else POLICE, taille)
        dessin.drawRightString(x_droite, y, valeur)

    def montant(self, page: int, cellule: Cellule, euros: int, gras: bool = False) -> None:
        texte = texte_case(euros)
        if texte is None:
            return
        _, x_droite, y = cellule
        self.texte_droite(page, x_droite - MARGE_DROITE, y + 0.5, texte, gras=gras)

    def cases(self, page: int, bords: Sequence[float], y: float, caracteres: str) -> None:
        """Un caractère centré par case ; `bords` = abscisses des traits
        verticaux (n + 1 bords pour n cases)."""
        dessin = self._calque(page)
        dessin.setFont(POLICE, TAILLE_TEXTE)
        for gauche, droite, caractere in zip(bords, bords[1:], caracteres, strict=False):
            dessin.drawCentredString((gauche + droite) / 2, y, caractere)

    def cases_regulieres(
        self, page: int, x_gauche: float, largeur: float, y: float, caracteres: str
    ) -> None:
        """Cases de même largeur accolées (glyphes ☐ du formulaire)."""
        bords = [x_gauche + i * largeur for i in range(len(caracteres) + 1)]
        self.cases(page, bords, y, caracteres)

    def croix(self, page: int, x_centre: float, y: float, taille: float = 9.0) -> None:
        dessin = self._calque(page)
        dessin.setFont(POLICE_GRAS, taille)
        dessin.drawCentredString(x_centre, y, "X")

    def rendre(self) -> bytes:
        for page, (tampon, dessin) in self._calques.items():
            dessin.save()
            tampon.seek(0)
            self._writer.pages[page - 1].merge_page(PdfReader(tampon).pages[0])
        sortie = io.BytesIO()
        self._writer.write(sortie)
        return sortie.getvalue()
