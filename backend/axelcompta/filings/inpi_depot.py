"""Dossier de dépôt des comptes annuels — Guichet Unique INPI (doc 02 §6,
doc 20). Phase 1 de doc 02 §6 : génère le dossier prêt à déposer (PDF +
données structurées) ; le dépôt réel (appel API + signature qualifiée RGS,
`workflow/signature.py`) reste V1, bloqué sur ADR-004 (doc 20 §4/§5).

`construire_payload_comptes_annuels` a la même forme que le bloc
`content.comptesAnnuels` attendu par `POST /api/annual_accounts` (doc 20
§3, contrat d'interface INPI vérifié le 2026-09-11) — pas un format
inventé, prêt à être posté tel quel le jour où l'appel API réel est câblé
(reste à compléter : `personnePhysique`/`personneMorale`/`declarant`, et
`pagination` une fois le dictionnaire de données INPI dépouillé, doc 20
§6).

`PdfDepotInpiRenderer` tient lieu, pour la démo, du « document de
synthèse » que le Guichet Unique génère lui-même côté serveur après un
vrai dépôt (doc 20 §4) — impossible à appeler sans compte e-procédures,
donc simulé. Marqué FICTIF sans ambiguïté (doc 08 §5).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from axelcompta.closing.models import LiassePivot

from .renderer import FilingRenderer

# Art. D.123-200, exercices ouverts à compter du 1er janvier 2024
# (décret n° 2024-152). On reste dans la catégorie si au plus un des trois
# seuils est dépassé. Les anciens seuils 350 000 / 700 000 € ne s'appliquent
# plus à l'exercice 2025.
_SEUIL_MICRO = (450_000, 900_000, 10)
_SEUIL_PETITE = (7_500_000, 15_000_000, 50)
_SEUIL_MOYENNE = (25_000_000, 50_000_000, 250)

# Formes qui déposent des comptes sociaux (doc 02 §6). EI et micro-entreprise
# n'y figurent pas : pas de dépôt au greffe. La valeur dit qui signe l'acte
# quand le dossier n'a pas la liste de ses associés.
_ACTE_PAR_FORME = {
    "SASU": "associe_unique",
    "EURL": "associe_unique",
    "SAS": "assemblee",
    "SARL": "assemblee",
    "SA": "assemblee",
}

LIEN_PORTAIL_INPI = "https://procedures.inpi.fr/"

MENTION_FICTIVE = "DOCUMENT FICTIF — DÉMO AXELCOMPTA, NE PAS DÉPOSER"


@dataclass(frozen=True, slots=True)
class LignePortail:
    question: str
    reponse: str
    detail: str


@dataclass(frozen=True, slots=True)
class PieceGreffe:
    nom: str
    detail: str
    document: str | None


@dataclass(frozen=True, slots=True)
class GuideGreffe:
    depose: bool
    lien: str
    lignes: tuple[LignePortail, ...]
    pieces: tuple[PieceGreffe, ...]


def _entier(cases: dict[str, int], cle: str) -> int:
    return cases.get(cle, 0) // 100


def _seuils_depasses(bilan: int, ca: int, effectif: int, seuils: tuple[int, int, int]) -> int:
    plafond_bilan, plafond_ca, plafond_effectif = seuils
    return (bilan > plafond_bilan) + (ca > plafond_ca) + (effectif > plafond_effectif)


def _categorie(bilan: int, ca: int, effectif: int) -> str:
    """micro, petite, moyenne ou grande. Un seul exercice connu : les seuils
    se jugent normalement sur deux exercices consécutifs."""
    if _seuils_depasses(bilan, ca, effectif, _SEUIL_MICRO) < 2:
        return "micro"
    if _seuils_depasses(bilan, ca, effectif, _SEUIL_PETITE) < 2:
        return "petite"
    if _seuils_depasses(bilan, ca, effectif, _SEUIL_MOYENNE) < 2:
        return "moyenne"
    return "grande"


def _acte(liasse: LiassePivot) -> tuple[str, str] | None:
    forme = liasse.forme_juridique
    if forme not in _ACTE_PAR_FORME:
        return None
    nb = len(liasse.identite.associes) if liasse.identite is not None else None
    associe_unique = nb == 1 or (nb is None and _ACTE_PAR_FORME[forme] == "associe_unique")
    if associe_unique:
        return (
            "Décision de l'associé unique",
            "À joindre une fois signée. Elle n'est pas produite ici.",
        )
    return (
        "Extrait du procès-verbal d'assemblée générale",
        "À joindre une fois signé. Il n'est pas produit ici.",
    )


def _detail_annexe(dispense: bool) -> str:
    if dispense:
        return "L'annexe explique les chiffres. Une toute petite société peut ne pas la déposer."
    return "L'annexe, qui explique les chiffres, est demandée."


def _detail_confidentialite_comptes(micro: bool) -> str:
    if micro:
        return "Vos chiffres ne sont pas publiés. C'est réservé aux toutes petites sociétés."
    return "Vos chiffres restent publics. Le secret est réservé aux toutes petites sociétés."


def _detail_confidentialite_resultat(petite: bool) -> str:
    effet = "ce que vous avez gagné et dépensé"
    if petite:
        return f"Le compte de résultat, {effet}, peut rester secret."
    return f"Le compte de résultat, {effet}, reste public."


def _detail_presentation(moyenne: bool) -> str:
    if moyenne:
        return "Une présentation plus courte, réservée aux sociétés de taille moyenne."
    return "La présentation complète est demandée."


def _lignes_portail(categorie: str, debut: str, fin: str) -> tuple[LignePortail, ...]:
    micro = categorie == "micro"
    petite = categorie == "petite"
    moyenne = categorie == "moyenne"
    return (
        LignePortail(
            "Type de dépôt",
            "Comptes sociaux",
            "Les comptes de votre société, pas ceux d'un groupe.",
        ),
        LignePortail("Dépôt rectificatif", "Non", "Premier dépôt de cet exercice."),
        LignePortail("Début de l'exercice", debut, "Le premier jour de l'année comptable."),
        LignePortail("Clôture de l'exercice", fin, "Le dernier jour de l'année comptable."),
        LignePortail(
            "Dispensée de déposer les annexes",
            "Oui" if micro else "Non",
            _detail_annexe(micro),
        ),
        LignePortail(
            "Confidentialité des comptes",
            "Oui" if micro else "Non",
            _detail_confidentialite_comptes(micro),
        ),
        LignePortail(
            "Confidentialité du compte de résultat",
            "Oui" if petite else "Non",
            _detail_confidentialite_resultat(petite),
        ),
        LignePortail(
            "Présentation simplifiée",
            "Oui" if moyenne else "Non",
            _detail_presentation(moyenne),
        ),
    )


def _pieces_greffe(acte: tuple[str, str], avec_annexe: bool) -> tuple[PieceGreffe, ...]:
    pieces = [
        PieceGreffe(
            "Bilan actif / passif",
            "Ce que la société possède et ce qu'elle doit. Le portail demande ce nom.",
            "bilan.pdf",
        ),
        PieceGreffe(
            "Compte de résultat",
            "Ce que vous avez gagné et dépensé sur l'année. Le portail demande ce nom.",
            "compte-resultat.pdf",
        ),
        PieceGreffe(acte[0], acte[1], None),
    ]
    if avec_annexe:
        pieces.append(
            PieceGreffe(
                "Annexe comptable",
                "Le texte qui explique les chiffres. Il n'est pas encore produit ici.",
                None,
            )
        )
    return tuple(pieces)


def guide_greffe(liasse: LiassePivot) -> GuideGreffe:
    """Ce que le chauffeur reporte sur le portail INPI, et les pièces au nom
    demandé par le guichet. Rien n'est déposé depuis ici."""
    vide = GuideGreffe(depose=False, lien=LIEN_PORTAIL_INPI, lignes=(), pieces=())
    acte = _acte(liasse)
    if acte is None:
        return vide

    bilan = _entier(liasse.cases, "2033A.180")
    ca = _entier(liasse.cases, "CA_HT")
    effectif = _entier(liasse.cases, "2033E.376")
    categorie = _categorie(bilan, ca, effectif)
    debut = liasse.exercice_debut.strftime("%d/%m/%Y") if liasse.exercice_debut else ""
    fin = liasse.exercice_fin.strftime("%d/%m/%Y") if liasse.exercice_fin else ""
    return GuideGreffe(
        depose=True,
        lien=LIEN_PORTAIL_INPI,
        lignes=_lignes_portail(categorie, debut, fin),
        pieces=_pieces_greffe(acte, categorie != "micro"),
    )


def construire_payload_comptes_annuels(liasse: LiassePivot) -> dict[str, Any]:
    """Le bloc `content.comptesAnnuels` du contrat d'interface INPI (doc 20
    §3). Valeurs par défaut les plus prudentes (pas de confidentialité, pas
    de dépôt simplifié, pas de comptes consolidés) — pas un choix
    arbitraire, à reconfigurer par dossier une fois le dictionnaire de
    données INPI dépouillé (doc 20 §6)."""
    return {
        "comptesConsolides": False,
        "dateCloture": liasse.exercice_fin.isoformat() if liasse.exercice_fin else None,
        "dateDebutExerciceComptable": (
            liasse.exercice_debut.isoformat() if liasse.exercice_debut else None
        ),
        "dateFinExerciceComptable": liasse.exercice_fin.isoformat()
        if liasse.exercice_fin
        else None,
        "dispenseDepotAnnexes": False,
        "depotSimplifie": False,
        "compteBilan": {"confidentiel": False},
        "compteResultat": {"confidentiel": False},
    }


def _ligne(dessin: canvas.Canvas, x: int, y: int, libelle: str, centimes: int) -> None:
    dessin.drawString(x, y, f"{libelle} : {centimes / 100:.2f} €")


def _entete(dessin: canvas.Canvas, liasse: LiassePivot) -> None:
    dessin.setFont("Helvetica-Bold", 16)
    dessin.drawString(50, 800, "Dépôt des comptes annuels — Guichet Unique INPI")
    dessin.setFillColorRGB(0.7, 0, 0)
    dessin.setFont("Helvetica-Bold", 11)
    dessin.drawString(50, 782, MENTION_FICTIVE)
    dessin.setFillColorRGB(0, 0, 0)
    dessin.setFont("Helvetica", 9)
    dessin.drawString(
        50,
        768,
        "Tient lieu du document de synthèse généré par le Guichet Unique "
        "après un vrai dépôt (doc 20 §4) — jamais appelé ici.",
    )
    dessin.setFont("Helvetica", 11)
    dessin.drawString(50, 744, f"Dossier {liasse.dossier_id} — exercice {liasse.exercice}")


def _corps_comptable(dessin: canvas.Canvas, liasse: LiassePivot) -> int:
    y = 710
    dessin.setFont("Helvetica-Bold", 13)
    dessin.drawString(50, y, "Compte de résultat")
    dessin.setFont("Helvetica", 11)
    for libelle, cle in (
        ("Chiffre d'affaires HT", "CA_HT"),
        ("Charges", "CHARGES"),
        ("Résultat de l'exercice", "RESULTAT"),
    ):
        y -= 20
        _ligne(dessin, 60, y, libelle, liasse.cases.get(cle, 0))

    y -= 35
    dessin.setFont("Helvetica-Bold", 13)
    dessin.drawString(50, y, "Bilan")
    dessin.setFont("Helvetica", 11)
    for libelle, cle in (
        ("Actif — Trésorerie", "TRESORERIE"),
        ("Passif — Résultat", "RESULTAT"),
        ("Passif — TVA à payer", "TVA_A_PAYER"),
    ):
        y -= 20
        _ligne(dessin, 60, y, libelle, liasse.cases.get(cle, 0))
    return y


def _zone_signature(dessin: canvas.Canvas, y: int) -> None:
    y -= 50
    dessin.setFont("Helvetica-Bold", 12)
    dessin.drawString(50, y, "Zone de signature")
    dessin.rect(50, y - 90, 495, 75, stroke=1, fill=0)
    dessin.setFont("Helvetica", 9)
    dessin.drawString(60, y - 20, "En attente de signature — dépôt non finalisé.")


class PdfDepotInpiRenderer(FilingRenderer):
    def rendre(self, liasse: LiassePivot) -> bytes:
        tampon = io.BytesIO()
        dessin = canvas.Canvas(tampon, pagesize=A4)
        _entete(dessin, liasse)
        y_fin = _corps_comptable(dessin, liasse)
        _zone_signature(dessin, y_fin)
        dessin.showPage()
        dessin.save()
        return tampon.getvalue()
