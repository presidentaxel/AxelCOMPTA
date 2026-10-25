"""Exports PDF grand livre + balance (démo, AXE-417 / AXE-418).

Même source que le CSV (`export_comptable.py`) : tuple d'écritures du ledger
(avec décisions humaines quand servi via `demo_api`). Présentation lisible
pour la démo — pas un rendu CERFA / outil expert-comptable V1.
"""

from __future__ import annotations

import io
from itertools import groupby

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from axelcompta.ledger.models import Ecriture, Sens

from .export_comptable import _totaux_par_compte
from .fec import libelle_compte

# A4 portrait, marges et colonnes calées pour tenir débit/crédit alignés.
_LARGEUR, _ = A4
_MARGE_G = 40
_MARGE_D = 40
_MARGE_BAS = 50
_Y_HAUT = 800
# Assez large pour `…settlement-12` / `…categorise-3` sans écraser libellé.
_LARGEUR_ID_ECRITURE = 24


def _euros(centimes: int) -> str:
    """Affichage uniquement — les calculs restent en centimes entiers.
    Un solde nul sort vide, comme une case de liasse."""
    if centimes == 0:
        return ""
    return f"{centimes / 100:.2f} €"


def _id_ecriture_affiche(ecriture_id: object, max_len: int = _LARGEUR_ID_ECRITURE) -> str:
    """Garde la fin de l'id (discriminante) : les ids seedés sont
    `DEMO_karim:settlement-N` — tronquer au début rendait toutes les lignes
    identiques (Bugbot)."""
    texte = str(ecriture_id)
    if len(texte) <= max_len:
        return texte
    return "…" + texte[-(max_len - 1) :]


def _nouvelle_page(dessin: canvas.Canvas, titre: str, sous_titre: str) -> float:
    dessin.setFont("Helvetica-Bold", 14)
    dessin.drawString(_MARGE_G, _Y_HAUT, titre)
    dessin.setFont("Helvetica", 9)
    dessin.drawString(_MARGE_G, _Y_HAUT - 16, sous_titre)
    dessin.setFont("Helvetica", 8)
    dessin.drawString(
        _MARGE_G,
        _Y_HAUT - 30,
        "Démo AxeLCompta — présentation, pas un export réglementaire",
    )
    return float(_Y_HAUT - 50)


def _assurer_espace(
    dessin: canvas.Canvas, y: float, besoin: float, titre: str, sous_titre: str
) -> tuple[float, bool]:
    """Retourne (y, page_nouvelle). `page_nouvelle` permet de redessiner
    les en-têtes de section après un saut (Bugbot)."""
    if y - besoin < _MARGE_BAS:
        dessin.showPage()
        return _nouvelle_page(dessin, titre, sous_titre), True
    return y, False


def _entete_compte(dessin: canvas.Canvas, y: float, compte: str) -> float:
    dessin.setFont("Helvetica-Bold", 11)
    dessin.drawString(_MARGE_G, y, f"Compte {compte} — {libelle_compte(compte)}")
    y -= 14
    dessin.setFont("Helvetica", 8)
    dessin.drawString(_MARGE_G, y, "Date")
    dessin.drawString(_MARGE_G + 55, y, "Écriture")
    dessin.drawString(_MARGE_G + 160, y, "Libellé")
    dessin.drawRightString(_LARGEUR - _MARGE_D - 90, y, "Débit")
    dessin.drawRightString(_LARGEUR - _MARGE_D, y, "Crédit")
    y -= 4
    dessin.line(_MARGE_G, y, _LARGEUR - _MARGE_D, y)
    return y - 12


def _entete_colonnes_balance(dessin: canvas.Canvas, y: float) -> float:
    dessin.setFont("Helvetica-Bold", 8)
    dessin.drawString(_MARGE_G, y, "Compte")
    dessin.drawString(_MARGE_G + 50, y, "Libellé")
    dessin.drawRightString(_LARGEUR - _MARGE_D - 140, y, "Débit")
    dessin.drawRightString(_LARGEUR - _MARGE_D - 70, y, "Crédit")
    dessin.drawRightString(_LARGEUR - _MARGE_D, y, "Solde")
    y -= 4
    dessin.line(_MARGE_G, y, _LARGEUR - _MARGE_D, y)
    return y - 14


def rendre_grand_livre_pdf(ecritures: tuple[Ecriture, ...], *, dossier_id: str) -> bytes:
    """Une section par compte (tri compte puis date), colonnes débit / crédit."""
    titre = "AxeLCompta — Grand livre"
    sous_titre = f"Dossier {dossier_id}"
    paires = sorted(
        ((ecriture, ligne) for ecriture in ecritures for ligne in ecriture.lignes),
        key=lambda paire: (paire[1].compte, paire[0].date, paire[0].id),
    )

    tampon = io.BytesIO()
    dessin = canvas.Canvas(tampon, pagesize=A4)
    y = _nouvelle_page(dessin, titre, sous_titre)

    if not paires:
        dessin.setFont("Helvetica", 10)
        dessin.drawString(_MARGE_G, y, "Aucune écriture.")
        dessin.showPage()
        dessin.save()
        return tampon.getvalue()

    for compte, groupe in groupby(paires, key=lambda paire: paire[1].compte):
        mouvements = list(groupe)
        y, _ = _assurer_espace(dessin, y, 48, titre, sous_titre)
        y = _entete_compte(dessin, y, compte)

        for ecriture, ligne in mouvements:
            y, page_nouvelle = _assurer_espace(dessin, y, 14, titre, sous_titre)
            if page_nouvelle:
                y = _entete_compte(dessin, y, compte)
            dessin.setFont("Helvetica", 8)
            dessin.drawString(_MARGE_G, y, ecriture.date.isoformat())
            dessin.drawString(_MARGE_G + 55, y, _id_ecriture_affiche(ecriture.id))
            libelle = ecriture.libelle[:42] + ("…" if len(ecriture.libelle) > 42 else "")
            dessin.drawString(_MARGE_G + 160, y, libelle)
            montant = _euros(ligne.montant.centimes)
            if ligne.sens is Sens.DEBIT:
                dessin.drawRightString(_LARGEUR - _MARGE_D - 90, y, montant)
            else:
                dessin.drawRightString(_LARGEUR - _MARGE_D, y, montant)
            y -= 12

        y -= 10

    dessin.showPage()
    dessin.save()
    return tampon.getvalue()


def rendre_balance_pdf(ecritures: tuple[Ecriture, ...], *, dossier_id: str) -> bytes:
    """Une ligne par compte : débit, crédit, solde (débit − crédit), + totaux."""
    titre = "AxeLCompta — Balance"
    sous_titre = f"Dossier {dossier_id}"
    totaux = _totaux_par_compte(ecritures)

    tampon = io.BytesIO()
    dessin = canvas.Canvas(tampon, pagesize=A4)
    y = _nouvelle_page(dessin, titre, sous_titre)
    y = _entete_colonnes_balance(dessin, y)

    total_debit = 0
    total_credit = 0
    for compte in sorted(totaux):
        debit_cts, credit_cts = totaux[compte]
        total_debit += debit_cts
        total_credit += credit_cts
        y, page_nouvelle = _assurer_espace(dessin, y, 14, titre, sous_titre)
        if page_nouvelle:
            y = _entete_colonnes_balance(dessin, y)
        dessin.setFont("Helvetica", 8)
        dessin.drawString(_MARGE_G, y, compte)
        dessin.drawString(_MARGE_G + 50, y, libelle_compte(compte)[:36])
        dessin.drawRightString(_LARGEUR - _MARGE_D - 140, y, _euros(debit_cts))
        dessin.drawRightString(_LARGEUR - _MARGE_D - 70, y, _euros(credit_cts))
        dessin.drawRightString(_LARGEUR - _MARGE_D, y, _euros(debit_cts - credit_cts))
        y -= 12

    y, page_nouvelle = _assurer_espace(dessin, y, 28, titre, sous_titre)
    if page_nouvelle:
        y = _entete_colonnes_balance(dessin, y)
    y -= 4
    dessin.line(_MARGE_G, y, _LARGEUR - _MARGE_D, y)
    y -= 14
    dessin.setFont("Helvetica-Bold", 8)
    dessin.drawString(_MARGE_G, y, "TOTAL")
    dessin.drawRightString(_LARGEUR - _MARGE_D - 140, y, _euros(total_debit))
    dessin.drawRightString(_LARGEUR - _MARGE_D - 70, y, _euros(total_credit))
    # Équilibre : Σ soldes = 0 ⇔ total débit = total crédit (partie double).
    dessin.drawRightString(_LARGEUR - _MARGE_D, y, _euros(total_debit - total_credit))

    dessin.showPage()
    dessin.save()
    return tampon.getvalue()
