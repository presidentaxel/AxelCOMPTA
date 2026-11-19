"""N'envoyer à l'OCR que les pages utiles d'un PDF (AXE-999). Pur.

Un grand livre fait des dizaines de pages pour deux nombres : les totaux
généraux, en dernière page. Moins de pages, c'est moins cher, et moins de
données personnelles chez Anthropic (ADR-009).
"""

from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


def dernieres_pages(contenu: bytes, nombre: int) -> bytes:
    """Le PDF réduit à ses `nombre` dernières pages ; le document entier s'il
    est plus court ou qu'il ne se découpe pas (chiffré, abîmé)."""
    try:
        lecteur = PdfReader(io.BytesIO(contenu))
        total = len(lecteur.pages)
        if total <= nombre:
            return contenu
        ecrivain = PdfWriter()
        for page in lecteur.pages[total - nombre :]:
            ecrivain.add_page(page)
        sortie = io.BytesIO()
        ecrivain.write(sortie)
    except (PdfReadError, ValueError, KeyError):
        return contenu
    return sortie.getvalue()
