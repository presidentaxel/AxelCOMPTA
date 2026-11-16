"""Tableau 2059-A-SD millésime 2026 : détermination des plus et
moins-values (notice 2032-NOT-SD), depuis le registre des
immobilisations (AXE-802).

Une ligne par immobilisation cédée dans l'exercice (lignes 1 à 12), en
euros entiers. Colonnes du formulaire :

2. valeur d'origine ; 3. valeur nette réévaluée (aucune réévaluation : 0) ;
4. amortissements pratiqués et admis en déduction ; 5. autres amortissements
(0) ; 6. valeur résiduelle ; 7. prix de vente ; 8. plus ou moins-value ;
9. court terme ; 10. long terme (taux 15 % ou 12,8 %) ; 11. plus-value
taxable à 19 % (0).

Qualification (notice 2032-NOT-SD et art. 39 duodecies du CGI) :

* à l'IS, le long terme ne concerne que les titres de participation ; une
  immobilisation du registre (véhicule, matériel) est à court terme ;
* à l'IR, un bien détenu moins de deux ans : court terme en entier ; détenu
  depuis deux ans au moins, la plus-value est à court terme à hauteur des
  amortissements déduits, le reste à long terme ; une moins-value sur un
  bien amortissable est à court terme.

Le tableau ne porte pas de code de case pour ces lignes : les cases sont
nommées `L<n>.C<colonne>`, et `TOTAL.C<colonne>` pour la somme. La nature
et la date d'acquisition (colonne 1) restent dans le registre.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from .immobilisations import Immobilisation, cumul, plus_ou_moins_value
from .impot_societes import arrondir_euros

LIGNES_MAX = 12


def _deux_ans_au_moins(acquise: date, cedee: date) -> bool:
    try:
        anniversaire = acquise.replace(year=acquise.year + 2)
    except ValueError:  # 29 février
        anniversaire = date(acquise.year + 2, 3, 1)
    return cedee >= anniversaire


def _qualifier(
    immo: Immobilisation, valeur: int, amortissements: int, soumis_is: bool
) -> tuple[int, int]:
    """(court terme, long terme), en centimes."""
    assert immo.cession is not None
    if soumis_is or valeur <= 0 or not _deux_ans_au_moins(immo.mise_en_service, immo.cession.le):
        return valeur, 0
    court = min(valeur, amortissements)
    return court, valeur - court


def plus_values_2059a(
    immobilisations: Sequence[Immobilisation], debut: date, fin: date, soumis_is: bool
) -> dict[str, int]:
    """Vide sans cession dans l'exercice."""
    cedees = sorted(
        (i for i in immobilisations if i.cession is not None and debut <= i.cession.le <= fin),
        key=lambda i: (i.cession.le if i.cession else fin, i.id),
    )[:LIGNES_MAX]
    cases: dict[str, int] = {}
    totaux = dict.fromkeys(range(2, 12), 0)
    for rang, immo in enumerate(cedees, 1):
        assert immo.cession is not None
        amortissements = cumul(immo, immo.cession.le)
        valeur = plus_ou_moins_value(immo) or 0
        court, long_ = _qualifier(immo, valeur, amortissements, soumis_is)
        colonnes = {
            2: immo.base_cts,
            3: 0,
            4: amortissements,
            5: 0,
            6: immo.base_cts - amortissements,
            7: immo.cession.prix_cts,
            8: valeur,
            9: court,
            10: long_,
            11: 0,
        }
        for colonne, centimes in colonnes.items():
            euros = arrondir_euros(centimes)
            cases[f"L{rang}.C{colonne}"] = euros
            totaux[colonne] += euros
    if cedees:
        cases |= {f"TOTAL.C{colonne}": montant for colonne, montant in totaux.items()}
    return cases
