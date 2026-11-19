"""OCR de la section Banque (AXE-943). Pur.

* Relevé de compte (PDF ou image) : période, IBAN, soldes de début et de
  fin, chaque opération. Contrôle : solde de début + opérations = solde de
  fin, au centime. Accepté, il sert comme un QIF : la couverture bancaire
  (AXE-973) le prend comme source, ses deux soldes comme preuves, et
  « Écrire les relevés » (AXE-833) passe ses opérations en comptabilité.
* RIB : titulaire, IBAN (clé vérifiée), BIC, banque.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import product

from .categories import Categorie, Contexte
from .controles import controle_date, date_lue, entier, euros, iban_valide, liste, montants, texte

TYPE_RELEVE = "releve"


def _operations(lu: Mapping[str, object]) -> list[tuple[str, int, str]]:
    return [
        (str(o.get("date") or ""), entier(o.get("montant_cts")), str(o.get("libelle") or ""))
        for o in liste(lu, "operations")
    ]


def _signes_des_soldes(lu: dict[str, object]) -> dict[str, object]:
    """Un solde débiteur lu en positif (colonne Débit, mention « débiteur ») :
    si les opérations ne tombent pas juste et qu'**un seul** jeu de signes des
    deux soldes les fait tomber juste au centime, c'est celui-là. Sinon, rien
    ne change et le contrôle signale l'écart."""
    m = montants(lu)
    debut, fin = m.get("solde_debut_cts"), m.get("solde_fin_cts")
    if debut is None or fin is None:
        return lu
    somme = sum(montant for _j, montant, _l in _operations(lu))
    if debut + somme == fin:
        return lu
    justes = {
        (sd * debut, sf * fin)
        for sd, sf in product((1, -1), repeat=2)
        if sd * debut + somme == sf * fin
    }
    if len(justes) != 1:
        return lu
    ((nouveau_debut, nouvelle_fin),) = justes
    corriges = {"solde_debut_cts": nouveau_debut, "solde_fin_cts": nouvelle_fin}
    return {
        **lu,
        "montants": [
            {**m_, "valeur_cts": corriges.get(str(m_.get("nom")), m_.get("valeur_cts"))}
            for m_ in liste(lu, "montants")
        ],
    }


def _releve(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    erreurs = controle_date(lu, "periode_debut", "Début de période", True)
    erreurs += controle_date(lu, "periode_fin", "Fin de période", True)
    iban = texte(lu, "iban")
    if iban and not iban_valide(iban):
        erreurs.append(f"IBAN lu invalide ({iban}).")
    m = montants(lu)
    debut, fin = m.get("solde_debut_cts"), m.get("solde_fin_cts")
    if debut is None or fin is None:
        return [*erreurs, "Soldes de début et de fin : non lus."]
    operations = _operations(lu)
    if any(date_lue(j) is None for j, _m, _l in operations):
        erreurs.append("Une opération a une date illisible.")
    somme = sum(montant for _j, montant, _l in operations)
    if debut + somme != fin:
        erreurs.append(
            f"Solde de début {euros(debut)} + opérations {euros(somme)} ≠ solde de fin "
            f"{euros(fin)} (écart {euros(fin - debut - somme)})."
        )
    return erreurs


def _donnees_releve(lu: Mapping[str, object]) -> dict[str, object]:
    """Comme un QIF lu (AXE-973), avec la période et les deux soldes."""
    m = montants(lu)
    return {
        "type": TYPE_RELEVE,
        "periode_debut": texte(lu, "periode_debut"),
        "periode_fin": texte(lu, "periode_fin"),
        "solde_debut_cts": m.get("solde_debut_cts"),
        "solde_fin_cts": m.get("solde_fin_cts"),
        "mouvements": [[j, montant] for j, montant, _l in _operations(lu)],
    }


RELEVE_BANCAIRE = Categorie(
    "releve_bancaire",
    """Document : un relevé de compte bancaire (un ou plusieurs mois).
- banque, titulaire, iban (sans espace), periode_debut et periode_fin (les dates du relevé).
- montants : solde_debut_cts (ancien solde, au début de la période) et solde_fin_cts (nouveau
  solde, à la fin), créditeur positif, débiteur négatif. Un solde porté dans la colonne Débit,
  ou marqué « débiteur », « DB », « - », est négatif.
- operations : chaque opération, dans l'ordre, avec date (date d'opération), libelle (le libellé
  complet), montant_cts (crédit positif, débit négatif). N'oublie aucune ligne, et ne compte pas
  les lignes de total ni les soldes intermédiaires.""",
    textes=("banque", "titulaire", "iban", "periode_debut", "periode_fin"),
    montants=("solde_debut_cts", "solde_fin_cts"),
    listes={"operations": {"date": "string", "libelle": "string", "montant_cts": "integer"}},
    corriger=_signes_des_soldes,
    controler=_releve,
    resumer=lambda lu: (
        f"Relevé lu : {texte(lu, 'banque')}, du {texte(lu, 'periode_debut')} au "
        f"{texte(lu, 'periode_fin')}, {len(liste(lu, 'operations'))} opérations, solde de fin "
        f"{euros(montants(lu).get('solde_fin_cts', 0))} (prouvé par les opérations)."
    ),
    donnees=_donnees_releve,
    max_tokens=16_000,
)


def _rib(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    iban = texte(lu, "iban")
    erreurs = [] if iban_valide(iban) else [f"IBAN lu invalide ({iban or 'absent'})."]
    return erreurs + ([] if texte(lu, "titulaire") else ["Titulaire : non lu."])


RIB = Categorie(
    "rib",
    """Document : un relevé d'identité bancaire (RIB).
- titulaire, iban (sans espace), bic, banque.""",
    textes=("titulaire", "iban", "bic", "banque"),
    controler=_rib,
    resumer=lambda lu: (
        f"RIB lu : {texte(lu, 'titulaire')}, {texte(lu, 'banque')}, "
        f"IBAN se terminant par {texte(lu, 'iban')[-4:]}."
    ),
)

BANQUE: dict[str, Categorie] = {c.cle: c for c in (RELEVE_BANCAIRE, RIB)}
