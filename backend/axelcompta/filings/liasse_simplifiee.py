"""Rendu PDF simplifié : compte de résultat + bilan + case-clé 2065
(doc 17 §3, semaine 3). Présentation lisible, **pas conforme CERFA/DGFiP** —
le formulaire réglementaire est V1 (doc 06 §6, doc 12 §Phase 3).
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from axelcompta.closing.models import LiassePivot

from .renderer import FilingRenderer


def _ligne(dessin: canvas.Canvas, x: int, y: int, libelle: str, centimes: int) -> None:
    dessin.drawString(x, y, f"{libelle} : {centimes / 100:.2f} €")


class PdfLiasseSimplifieeRenderer(FilingRenderer):
    def rendre(self, liasse: LiassePivot) -> bytes:
        tampon = io.BytesIO()
        dessin = canvas.Canvas(tampon, pagesize=A4)

        dessin.setFont("Helvetica-Bold", 16)
        dessin.drawString(50, 800, "AxeLCompta — Liasse simplifiée (démo)")
        dessin.setFont("Helvetica", 9)
        dessin.drawString(50, 784, "Pas conforme CERFA/DGFiP — présentation démo (doc 17 §3)")
        dessin.setFont("Helvetica", 11)
        dessin.drawString(50, 760, f"Dossier {liasse.dossier_id} — exercice {liasse.exercice}")

        y = 725
        dessin.setFont("Helvetica-Bold", 13)
        dessin.drawString(50, y, "Compte de résultat simplifié")
        dessin.setFont("Helvetica", 11)
        for libelle, cle in (
            ("Chiffre d'affaires HT", "CA_HT"),
            ("Charges", "CHARGES"),
            ("Résultat de l'exercice", "RESULTAT"),
        ):
            y -= 20
            _ligne(dessin, 60, y, libelle, liasse.cases[cle])

        y -= 35
        dessin.setFont("Helvetica-Bold", 13)
        dessin.drawString(50, y, "Bilan simplifié")
        dessin.setFont("Helvetica", 11)
        for libelle, cle in (
            ("Actif — Trésorerie", "TRESORERIE"),
            ("Actif — Immobilisations", "IMMOBILISATIONS"),
            ("Passif — Capitaux", "CAPITAUX"),
            ("Passif — Résultat", "RESULTAT"),
            ("Passif — TVA à payer", "TVA_A_PAYER"),
            ("Comptes non ventilés", "COMPTES_NON_VENTILES"),
        ):
            y -= 20
            _ligne(dessin, 60, y, libelle, liasse.cases.get(cle, 0))

        y -= 35
        dessin.setFont("Helvetica-Bold", 13)
        dessin.drawString(50, y, "Formulaire 2065 (IS) — case-clé")
        dessin.setFont("Helvetica", 11)
        y -= 20
        _ligne(dessin, 60, y, "Résultat fiscal (case 2065)", liasse.cases["2065"])

        dessin.showPage()
        dessin.save()
        return tampon.getvalue()
