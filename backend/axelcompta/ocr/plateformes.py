"""OCR de la section Plateformes (AXE-943). Pur.

Un récapitulatif Uber en PDF texte se lit déjà sans modèle (AXE-987) ;
l'OCR prend le reste : Bolt, Heetch, Free Now, Allocab, et les scans ou
captures. Contrôle : courses + autres revenus − frais = net, au centime.
Un récapitulatif d'un mois calendaire accepté compte dans la couverture des
plateformes comme celui du lecteur exact (mêmes données).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from .categories import Categorie, Contexte
from .controles import controle_date, controle_siren, date_lue, euros, montants, texte

MONTANTS = ("courses_cts", "autres_cts", "frais_cts", "net_cts", "tva_cts")
PLATEFORMES = ("uber", "bolt", "heetch", "freenow", "allocab", "autre")


def mois_calendaire(lu: Mapping[str, object]) -> str:
    """« AAAA-MM » si la période est un mois entier, sinon ""."""
    debut, fin = date_lue(texte(lu, "periode_debut")), date_lue(texte(lu, "periode_fin"))
    if debut is None or fin is None or debut.day != 1:
        return ""
    lendemain = fin + timedelta(days=1)
    if (fin.year, fin.month) != (debut.year, debut.month) or lendemain.day != 1:
        return ""
    return f"{debut.year}-{debut.month:02d}"


def _recap(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    erreurs = controle_siren(lu, ctx.siren)
    erreurs += controle_date(lu, "periode_debut", "Début de période", True)
    erreurs += controle_date(lu, "periode_fin", "Fin de période", True)
    if texte(lu, "plateforme") not in PLATEFORMES:
        erreurs.append("Plateforme : non lue.")
    m = montants(lu)
    courses, net = m.get("courses_cts"), m.get("net_cts")
    if courses is None or net is None:
        return [*erreurs, "Courses et net versé : non lus."]
    autres, frais = m.get("autres_cts", 0), m.get("frais_cts", 0)
    if courses + autres - frais != net:
        erreurs.append(
            f"Courses {euros(courses)} + autres {euros(autres)} − frais {euros(frais)} "
            f"≠ net {euros(net)}."
        )
    return erreurs


def _donnees(lu: Mapping[str, object]) -> dict[str, object]:
    """Comme le lecteur exact (AXE-987) ; un relevé qui n'est pas d'un mois
    entier garde sa période mais ne compte pas comme récapitulatif mensuel."""
    m = montants(lu)
    mois = mois_calendaire(lu)
    return {
        "type": "recap_plateforme" if mois else "releve_plateforme_periode",
        "plateforme": texte(lu, "plateforme"),
        "mois": mois,
        "periode_debut": texte(lu, "periode_debut"),
        "periode_fin": texte(lu, "periode_fin"),
        "siren": texte(lu, "siren") or None,
        **{
            c: m.get(c, 0) for c in ("courses_cts", "autres_cts", "frais_cts", "net_cts", "tva_cts")
        },
    }


RELEVE_PLATEFORME = Categorie(
    "releve_plateforme",
    """Document : un récapitulatif ou relevé de revenus d'une plateforme VTC (Uber, Bolt, Heetch,
Free Now, Allocab), mensuel, hebdomadaire ou annuel.
- plateforme : uber, bolt, heetch, freenow, allocab, ou autre.
- siren (du chauffeur ou de sa société, s'il est imprimé), periode_debut et periode_fin.
- montants, tous positifs : courses_cts (revenus des courses, TTC, péages et pourboires compris),
  autres_cts (autres revenus : bonus, primes, remboursements), frais_cts (commission et frais de
  service de la plateforme), net_cts (le montant net versé ou à verser), tva_cts (la TVA comprise
  dans les courses, 0 si aucune).""",
    textes=("plateforme", "siren", "periode_debut", "periode_fin"),
    montants=MONTANTS,
    controler=_recap,
    resumer=lambda lu: (
        f"Récapitulatif {texte(lu, 'plateforme').capitalize()} du {texte(lu, 'periode_debut')} "
        f"au {texte(lu, 'periode_fin')} : courses {euros(montants(lu).get('courses_cts', 0))}, "
        f"net {euros(montants(lu).get('net_cts', 0))}."
    ),
    donnees=_donnees,
)

PLATEFORMES_OCR: dict[str, Categorie] = {RELEVE_PLATEFORME.cle: RELEVE_PLATEFORME}
