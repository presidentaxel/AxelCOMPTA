"""OCR de la section Reprise comptable (AXE-943). Pur.

Chaque catégorie a ses contrôles, arithmétiques ou par recoupement :

* liasse et comptes annuels : actif = passif (à l'euro près, ils sont
  imprimés en euros), clôture de l'exercice attendu, résultat égal à celui
  du FEC du même exercice s'il est déposé ;
* balance : les soldes se compensent ; grand livre : débit = crédit ;
* déclaration de TVA : collectée − déductible = nette ;
* pièce : HT + TVA = TTC ; tableau d'emprunt : chaque échéance = capital +
  intérêts + assurance.

La liasse de l'exercice source donne aussi les déficits reportables à la
fiche (critère d'import d'AXE-989), jamais par-dessus une saisie.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .categories import Categorie, Contexte, Resume
from .controles import (
    controle_date,
    controle_siren,
    date_lue,
    entier,
    euros,
    liste,
    montants,
    texte,
)

ARRONDI_EURO = 100  # une liasse, une CA3 sont imprimées en euros entiers


def _exercice(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    erreurs = controle_date(lu, "exercice_fin", "Clôture de l'exercice", True)
    fin = texte(lu, "exercice_fin")
    if not erreurs and ctx.exercice and fin[:4] != str(ctx.exercice):
        erreurs.append(f"Clôture lue {fin}, le document est rangé en {ctx.exercice}.")
    return erreurs


def _contre_fec(resultat: int | None, ctx: Contexte) -> list[str]:
    fec = ctx.fec or {}
    attendu = fec.get("resultat_cts")
    if resultat is None or not isinstance(attendu, int):
        return []
    if abs(resultat - attendu) >= ARRONDI_EURO:
        return [f"Résultat lu {euros(resultat)}, le FEC du même exercice dit {euros(attendu)}."]
    return []


def _bilan(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    m = montants(lu)
    erreurs = controle_siren(lu, ctx.siren) + _exercice(lu, ctx)
    if "resultat_cts" not in m:
        erreurs.append("Résultat : non lu.")
    actif, passif = m.get("total_actif_cts"), m.get("total_passif_cts")
    if actif is not None and passif is not None and abs(actif - passif) > ARRONDI_EURO:
        erreurs.append(f"Actif {euros(actif)} et passif {euros(passif)} ne tombent pas juste.")
    return erreurs + _contre_fec(m.get("resultat_cts"), ctx)


def _resume_bilan(nom: str) -> Resume:
    def resumer(lu: Mapping[str, object]) -> str:
        m = montants(lu)
        morceaux = [f"clôture {texte(lu, 'exercice_fin')}"]
        for cle, libelle in (
            ("chiffre_affaires_cts", "chiffre d'affaires"),
            ("resultat_cts", "résultat"),
            ("total_actif_cts", "total du bilan"),
            ("deficits_reportables_cts", "déficits reportables"),
        ):
            if cle in m:
                morceaux.append(f"{libelle} {euros(m[cle])}")
        return f"{nom} lue : " + ", ".join(morceaux) + "."

    return resumer


MONTANTS_BILAN = (
    "chiffre_affaires_cts",
    "resultat_cts",
    "capital_cts",
    "total_actif_cts",
    "total_passif_cts",
    "impot_societes_cts",
    "deficits_reportables_cts",
    "immobilisations_brutes_cts",
    "amortissements_cts",
    "emprunts_cts",
    "tresorerie_cts",
)
CONSIGNE_BILAN = """\
- siren, denomination, formulaire (2033, 2050, 2065, 2031…), exercice_debut, exercice_fin.
- montants de l'exercice (pas de l'exercice précédent) : chiffre_affaires_cts, resultat_cts,
  capital_cts, total_actif_cts et total_passif_cts (totaux du bilan : l'actif NET, colonne
  « Net » de l'exercice, après amortissements et dépréciations, jamais la colonne « Brut » ;
  il est égal au total du passif), impot_societes_cts,
  deficits_reportables_cts (déficits restant à reporter en fin d'exercice, 2033-B ou 2058-B),
  immobilisations_brutes_cts, amortissements_cts, emprunts_cts (emprunts et dettes auprès des
  établissements de crédit), tresorerie_cts (disponibilités)."""


def _deficits(lu: Mapping[str, object]) -> dict[str, str]:
    deficits = montants(lu).get("deficits_reportables_cts")
    return {} if deficits is None else {"deficits": f"{abs(deficits) / 100:.2f}"}


LIASSE = Categorie(
    "liasse",
    "Document : une liasse fiscale (2033, 2050 et suivants, 2065, 2031) ou sa synthèse.\n"
    + CONSIGNE_BILAN,
    textes=("siren", "denomination", "formulaire", "exercice_debut", "exercice_fin"),
    montants=MONTANTS_BILAN,
    controler=_bilan,
    resumer=_resume_bilan("Liasse"),
    champs_fiche=_deficits,
    exercice_source_seul=True,
)
COMPTES_ANNUELS = Categorie(
    "comptes_annuels",
    "Document : des comptes annuels (bilan, compte de résultat, annexe).\n" + CONSIGNE_BILAN,
    textes=("siren", "denomination", "formulaire", "exercice_debut", "exercice_fin"),
    montants=MONTANTS_BILAN,
    controler=_bilan,
    resumer=_resume_bilan("Comptes annuels"),
)


def _balance(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    erreurs = controle_siren(lu, ctx.siren)
    comptes = liste(lu, "comptes")
    if not comptes:
        return [*erreurs, "Aucun compte lu."]
    somme = sum(entier(c.get("solde_cts")) for c in comptes)
    if abs(somme) > len(comptes):  # un centime d'arrondi par ligne, au plus
        erreurs.append(f"Les soldes ne se compensent pas : écart de {euros(somme)}.")
    m = montants(lu)
    debit, credit = m.get("total_soldes_debit_cts"), m.get("total_soldes_credit_cts")
    if debit is not None and credit is not None and debit != credit:
        erreurs.append(f"Totaux des soldes : débit {euros(debit)}, crédit {euros(credit)}.")
    return erreurs


BALANCE = Categorie(
    "balance",
    """Document : une balance des comptes.
- siren, exercice_fin (la date d'arrêté de la balance).
- comptes : chaque compte, avec compte (le numéro tel qu'imprimé), libelle et solde_cts, le solde
  de fin de période en centimes, débit moins crédit (un solde créditeur est négatif).
- montants : total_soldes_debit_cts et total_soldes_credit_cts, les totaux des colonnes de soldes
  (pas des mouvements).""",
    textes=("siren", "exercice_fin"),
    montants=("total_soldes_debit_cts", "total_soldes_credit_cts"),
    listes={"comptes": {"compte": "string", "libelle": "string", "solde_cts": "integer"}},
    controler=_balance,
    resumer=lambda lu: (
        f"Balance lue : {len(liste(lu, 'comptes'))} comptes, arrêtée au "
        f"{texte(lu, 'exercice_fin') or 'date non lue'}."
    ),
    donnees=lambda lu: {
        "soldes_cts": {
            str(c.get("compte")): entier(c.get("solde_cts")) for c in liste(lu, "comptes")
        }
    },
    max_tokens=16_000,
)


def _grand_livre(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    m = montants(lu)
    debit, credit = m.get("total_debit_cts"), m.get("total_credit_cts")
    if debit is None or credit is None:
        return [*controle_siren(lu, ctx.siren), "Totaux du grand livre : non lus."]
    if debit != credit:
        return [f"Grand livre : débit {euros(debit)}, crédit {euros(credit)}."]
    return controle_siren(lu, ctx.siren)


GRAND_LIVRE = Categorie(
    "grand_livre",
    """Document : un grand livre.
- siren, exercice_debut, exercice_fin.
- montants : total_debit_cts et total_credit_cts, les totaux généraux des mouvements (le dernier
  total « Total général » ou « Total grand livre »). Tu ne vois que les dernières pages du
  document : c'est là que sont ces totaux.""",
    textes=("siren", "exercice_debut", "exercice_fin"),
    montants=("total_debit_cts", "total_credit_cts"),
    controler=_grand_livre,
    dernieres_pages=2,
    inutile_avec_fec=True,
    resumer=lambda lu: (
        f"Grand livre lu : du {texte(lu, 'exercice_debut')} au "
        f"{texte(lu, 'exercice_fin')}, "
        f"{euros(montants(lu).get('total_debit_cts', 0))} de mouvements."
    ),
)


def _tva(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    erreurs = controle_siren(lu, ctx.siren)
    # Un récapitulatif annuel n'imprime pas toujours sa période : rangé sur
    # un exercice, il en prend la période ; en vrac, elle est obligatoire.
    erreurs += controle_date(lu, "periode_fin", "Fin de période", ctx.exercice is None)
    m = montants(lu)
    collectee, deductible = m.get("tva_collectee_cts"), m.get("tva_deductible_cts")
    nette = m.get("tva_nette_cts")
    if nette is None:
        erreurs.append("TVA nette (due ou crédit) : non lue.")
    elif collectee is not None and deductible is not None:
        # Une CA12 rend souvent le solde après les acomptes de l'année.
        acomptes = m.get("acomptes_cts", 0)
        attendus = (collectee - deductible, collectee - deductible - acomptes)
        if all(abs(a - nette) > ARRONDI_EURO for a in attendus):
            erreurs.append(
                f"Collectée {euros(collectee)} − déductible {euros(deductible)} "
                f"≠ nette {euros(nette)}."
            )
    return erreurs


FORMULAIRES_ANNUELS = ("CA12", "3517")
JOURS_ANNUELS = 300  # un exercice de 10 mois ou plus : une déclaration annuelle


def _annuelle(lu: Mapping[str, object]) -> bool:
    """Une déclaration qui couvre l'exercice (CA12, 3517-S, récapitulatif sans
    période) : son solde est celui de la fin de l'exercice. Une CA3 mensuelle
    ne dit que son mois."""
    if any(f in texte(lu, "formulaire").upper() for f in FORMULAIRES_ANNUELS):
        return True
    debut, fin = date_lue(texte(lu, "periode_debut")), date_lue(texte(lu, "periode_fin"))
    if debut is None or fin is None:
        return not texte(lu, "periode_fin")
    return (fin - debut).days >= JOURS_ANNUELS


def _credit_tva(lu: Mapping[str, object]) -> dict[str, str]:
    """AXE-990 : le crédit de TVA à reporter, depuis la déclaration annuelle
    de l'exercice source : une TVA nette négative est un crédit, sinon 0."""
    nette = montants(lu).get("tva_nette_cts")
    if nette is None or not _annuelle(lu):
        return {}
    return {"credit_tva": f"{max(-nette, 0) / 100:.2f}"}


DECLARATION_TVA = Categorie(
    "declaration_tva",
    """Document : une déclaration de TVA (CA3 mensuelle ou trimestrielle, CA12 annuelle, 3517) ou
sa synthèse.
- siren, formulaire (CA3, CA12…), periode_debut, periode_fin. Si le document n'imprime ni SIREN
  ni période (un récapitulatif des montants de l'année), laisse-les vides : ne les déduis pas.
- montants : tva_collectee_cts (TVA brute due), tva_deductible_cts (total à déduire),
  tva_nette_cts (TVA nette due, positive, ou crédit de TVA, négatif), acomptes_cts (acomptes
  déjà versés, CA12).""",
    textes=("siren", "formulaire", "periode_debut", "periode_fin"),
    montants=("tva_collectee_cts", "tva_deductible_cts", "tva_nette_cts", "acomptes_cts"),
    controler=_tva,
    champs_fiche=_credit_tva,
    exercice_source_seul=True,
    resumer=lambda lu: (
        "Déclaration de TVA lue : "
        + (
            f"du {texte(lu, 'periode_debut')} au {texte(lu, 'periode_fin')}"
            if texte(lu, "periode_fin")
            else "période non imprimée, celle de l'exercice"
        )
        + f", nette {euros(montants(lu).get('tva_nette_cts', 0))}."
    ),
)


def _is(lu: Mapping[str, object], ctx: Contexte) -> list[str]:
    erreurs = controle_siren(lu, ctx.siren) + _exercice(lu, ctx)
    if "impot_societes_cts" not in montants(lu) and "montant_verse_cts" not in montants(lu):
        erreurs.append("Montant d'IS : non lu.")
    return erreurs


DECLARATION_IS = Categorie(
    "declaration_is",
    """Document : un relevé d'acompte ou de solde d'impôt sur les sociétés (2571, 2572) ou sa
synthèse.
- siren, formulaire (2571, 2572…), exercice_fin (clôture de l'exercice concerné).
- montants : impot_societes_cts (IS de l'exercice), acomptes_cts (acomptes déjà versés),
  montant_verse_cts (somme versée avec ce relevé).""",
    textes=("siren", "formulaire", "exercice_fin"),
    montants=("impot_societes_cts", "acomptes_cts", "montant_verse_cts"),
    controler=_is,
    resumer=lambda lu: (
        f"Déclaration d'IS lue ({texte(lu, 'formulaire')}) : exercice clos le "
        f"{texte(lu, 'exercice_fin')}."
    ),
)


def _accuse(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    erreurs = controle_date(lu, "date_depot", "Date de dépôt", True)
    return erreurs + ([] if texte(lu, "declaration") else ["Déclaration accusée : non lue."])


ACCUSE_RECEPTION = Categorie(
    "accuse_reception",
    """Document : un accusé de réception du dépôt d'une déclaration.
- declaration (la déclaration déposée : 2065, TVA, IS…), date_depot, numero (numéro de dépôt),
  periode (la période ou l'exercice concerné, tel qu'écrit), siren.""",
    textes=("declaration", "date_depot", "numero", "periode", "siren"),
    controler=_accuse,
    resumer=lambda lu: (
        f"Accusé de dépôt : {texte(lu, 'declaration')}, le {texte(lu, 'date_depot')}."
    ),
)


def _paiement(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    erreurs = controle_date(lu, "date_paiement", "Date du paiement", True)
    montant = montants(lu).get("montant_cts")
    if montant is None or montant <= 0:
        erreurs.append("Montant payé : non lu.")
    return erreurs


PAIEMENT_IMPOT = Categorie(
    "paiement_impot",
    """Document : un ordre ou un avis de paiement d'un impôt (IS, TVA, CFE…).
- impot (l'impôt payé), date_paiement, reference.
- montants : montant_cts (le montant payé, positif).""",
    textes=("impot", "date_paiement", "reference"),
    montants=("montant_cts",),
    controler=_paiement,
    resumer=lambda lu: (
        f"Paiement {texte(lu, 'impot') or 'd’impôt'} de "
        f"{euros(montants(lu).get('montant_cts', 0))} le {texte(lu, 'date_paiement')}."
    ),
)


def _piece(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    erreurs = controle_date(lu, "date_piece", "Date de la pièce", True)
    m = montants(lu)
    ttc, ht, tva = m.get("ttc_cts"), m.get("ht_cts"), m.get("tva_cts")
    if ttc is None or ttc <= 0:
        erreurs.append("Montant TTC : non lu.")
    elif ht is not None and tva is not None and abs(ht + tva - ttc) > 1:
        erreurs.append(f"HT {euros(ht)} + TVA {euros(tva)} ≠ TTC {euros(ttc)}.")
    if not texte(lu, "emetteur"):
        erreurs.append("Émetteur : non lu.")
    return erreurs


PIECE = Categorie(
    "piece",
    """Document : une pièce justificative (facture, reçu, ticket, note de frais).
- emetteur (le fournisseur ou le client), date_piece, numero, nature (achat ou vente),
  objet (ce qui est acheté ou vendu, en quelques mots).
- montants : ht_cts, tva_cts, ttc_cts, taux_tva_pour_mille (20 % -> 200, 10 % -> 100,
  5,5 % -> 55).""",
    textes=("emetteur", "date_piece", "numero", "nature", "objet"),
    montants=("ht_cts", "tva_cts", "ttc_cts", "taux_tva_pour_mille"),
    controler=_piece,
    resumer=lambda lu: (
        f"Pièce lue : {texte(lu, 'emetteur')}, {texte(lu, 'date_piece')}, "
        f"{euros(montants(lu).get('ttc_cts', 0))} TTC."
    ),
)


def _emprunt(lu: Mapping[str, object], _ctx: Contexte) -> list[str]:
    erreurs = []
    capital = montants(lu).get("capital_emprunte_cts")
    if capital is None or capital <= 0:
        erreurs.append("Capital emprunté : non lu.")
    echeances = liste(lu, "echeances")
    if not echeances:
        return [*erreurs, "Aucune échéance lue."]
    for e in echeances:
        total = entier(e.get("echeance_cts"))
        parts = sum(entier(e.get(c)) for c in ("capital_cts", "interets_cts", "assurance_cts"))
        if abs(total - parts) > 1:
            erreurs.append(
                f"Échéance du {e.get('date')} : {euros(total)} ≠ capital + intérêts + assurance."
            )
            break
    amorti = sum(entier(e.get("capital_cts")) for e in echeances)
    if capital and amorti > capital + ARRONDI_EURO:
        erreurs.append(f"Capital remboursé {euros(amorti)} > capital emprunté {euros(capital)}.")
    return erreurs


def _emprunt_a_la_cloture(lu: Mapping[str, object], cloture: date) -> dict[str, str]:
    """AXE-990 : le capital restant dû à la clôture de l'exercice source,
    lu sur la dernière échéance payée à cette date. Rien si le prêt commence
    après, ou si aucune échéance ne se lit."""
    payees = [
        (jour, entier(e.get("capital_restant_cts")))
        for e in liste(lu, "echeances")
        if (jour := date_lue(str(e.get("date") or ""))) is not None and jour <= cloture
    ]
    if not payees:
        return {}
    _jour, restant = max(payees)
    preteur = texte(lu, "preteur") or "Prêt"
    if restant <= 0:
        return {"emprunts": f"{preteur} : remboursé au {cloture:%d/%m/%Y}."}
    return {
        "emprunts": (
            f"{preteur} : capital restant dû {euros(restant)} au {cloture:%d/%m/%Y} "
            "(tableau d'amortissement)."
        )
    }


EMPRUNT = Categorie(
    "emprunt",
    """Document : un tableau d'amortissement ou un échéancier de prêt.
- preteur (la banque), date_debut, taux (tel qu'écrit).
- montants : capital_emprunte_cts.
- echeances : chaque échéance, avec date (AAAA-MM-JJ), echeance_cts (montant total),
  capital_cts, interets_cts, assurance_cts (0 si aucune), capital_restant_cts (après
  l'échéance).""",
    textes=("preteur", "date_debut", "taux"),
    montants=("capital_emprunte_cts",),
    listes={
        "echeances": {
            "date": "string",
            "echeance_cts": "integer",
            "capital_cts": "integer",
            "interets_cts": "integer",
            "assurance_cts": "integer",
            "capital_restant_cts": "integer",
        }
    },
    controler=_emprunt,
    champs_a_la_cloture=_emprunt_a_la_cloture,
    resumer=lambda lu: (
        f"Emprunt lu : {texte(lu, 'preteur')}, "
        f"{euros(montants(lu).get('capital_emprunte_cts', 0))}, "
        f"{len(liste(lu, 'echeances'))} échéances."
    ),
    max_tokens=16_000,
)

REPRISE: dict[str, Categorie] = {
    c.cle: c
    for c in (
        LIASSE,
        COMPTES_ANNUELS,
        BALANCE,
        GRAND_LIVRE,
        DECLARATION_TVA,
        DECLARATION_IS,
        ACCUSE_RECEPTION,
        PAIEMENT_IMPOT,
        PIECE,
        EMPRUNT,
    )
}
