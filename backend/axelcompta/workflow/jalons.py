"""Jalons réglementaires d'un exercice terminé, dans l'ordre de la frise.

Chaque jalon après le compte est une preuve dans `documents_signes`
(`type_document`). La frise s'arrête au premier jalon absent : une
signature greffe sans clôture ne coche pas la clôture. Ajouter ou retirer
une preuve déplace l'étape, rien n'est figé par dossier.
"""

from __future__ import annotations

# (type_document, nom affiché). L'ordre est celui de la frise.
JALONS_EXERCICE: tuple[tuple[str, str], ...] = (
    ("cloture", "Clôture"),
    ("validation_comptes", "Signature"),
    ("greffe_inpi", "Greffe"),
    ("depot_impots", "Impôts"),
    ("signature_legale", "Signature légale"),
)


def etape_depuis_preuves(statut_invitation: str | None, preuves: set[str]) -> str:
    """Dernière étape atteinte d'un exercice terminé.

    « Compte » : le compte n'est pas ouvert. « Suivi » : il l'est, et aucun
    jalon réglementaire n'est enregistré. Ensuite, le nom du dernier jalon
    dont tous les précédents sont aussi présents.
    """
    if statut_invitation != "actif":
        return "Compte"
    etape = "Suivi"
    for type_document, nom in JALONS_EXERCICE:
        if type_document not in preuves:
            return etape
        etape = nom
    return etape
