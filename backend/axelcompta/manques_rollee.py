"""Ce qui manque pour rapprocher Rollee et la banque d'une entreprise (AXE-934). Pur.

Le mode expert le dit en tête des rapprochements, pour chaque entreprise
reliée, même sans aucune écriture bancaire : un compte Rollee à reconnecter,
une plateforme pas prise en charge, une banque absente ou trop courte, une
plateforme payée sans jour Rollee ou gagnée sans virement, et les semaines
qui restent à vérifier.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import date

from axelcompta.explication_semaines import MOTIF_EN_COURS, MOTIF_SANS_BANQUE, SemaineVue
from axelcompta.ingestion.comptes_rollee import CompteRelie
from axelcompta.packs.vtc_demo import Plateforme, plateforme_de


def euros(centimes: int) -> str:
    """« 1 234,56 € »."""
    texte = f"{abs(centimes) / 100:,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if centimes < 0 else ''}{texte} €"


def _nom(plateforme: str) -> str:
    return plateforme.capitalize()


def _retenus(comptes: Sequence[CompteRelie]) -> list[CompteRelie]:
    return [c for c in comptes if c.retenu and not c.titulaire_autre]


def _compte(nom: str, nombre: int) -> str:
    return f"{nom} ({nombre} comptes)" if nombre > 1 else nom


def _comptes(comptes: Sequence[CompteRelie], plateformes: tuple[Plateforme, ...]) -> list[str]:
    retenus = _retenus(comptes)
    if not retenus:
        return ["Aucun compte Rollee n'est relié à cette entreprise : rien à rapprocher."]
    inconnus = Counter(c.nom for c in retenus if plateforme_de(c.nom, plateformes) is None)
    eteints = Counter(
        c.nom
        for c in retenus
        if plateforme_de(c.nom, plateformes) is not None and c.etat == "a_reconnecter"
    )
    return [
        f"{_compte(nom, n)} : plateforme pas encore prise en charge, "
        "ses jours Rollee sont mis de côté."
        for nom, n in sorted(inconnus.items())
    ] + [
        f"{_compte(nom, n)} : compte Rollee à reconnecter, ses revenus ne sont plus lus."
        for nom, n in sorted(eteints.items())
    ]


Lien = str  # « lue » (connecté), « eteinte » (à reconnecter) ou « absente »


def liens_par_plateforme(
    comptes: Sequence[CompteRelie], plateformes: tuple[Plateforme, ...]
) -> dict[str, Lien]:
    """Pour chaque plateforme reliée : lue si un de ses comptes est connecté."""
    liens: dict[str, Lien] = {}
    for c in _retenus(comptes):
        p = plateforme_de(c.nom, plateformes)
        if p is not None and liens.get(p.nom) != "lue":
            liens[p.nom] = "lue" if c.connecte else "eteinte"
    return liens


def _conseil(nom: str, lien: Lien) -> str:
    if lien == "lue":
        return (
            f"Le compte {_nom(nom)} est relié, mais Rollee ne remonte aucun jour pour ces "
            "semaines : à signaler à Rollee."
        )
    if lien == "eteinte":
        return f"Reconnectez {_nom(nom)} dans Rollee."
    return f"Reliez {_nom(nom)} dans Rollee."


def _banque(vues: Sequence[SemaineVue], debut: date | None) -> list[str]:
    avant = [v for v in vues if v.motif == MOTIF_SANS_BANQUE]
    if not avant:
        return []
    du = euros(sum(v.du_cts for v in avant))
    if debut is None:
        return [
            f"Aucun relevé bancaire : {len(avant)} semaine(s) Rollee ({du} dus) ne peuvent "
            "pas être rapprochées. Reliez le compte qui reçoit les virements des plateformes."
        ]
    return [
        f"La banque commence le {debut:%d/%m/%Y} : les {len(avant)} semaine(s) Rollee "
        f"d'avant ({du} dus) ne peuvent pas être rapprochées."
    ]


def _plateforme(nom: str, siennes: Sequence[SemaineVue], lien: Lien) -> list[str]:
    # Une semaine encore attendue (virement pas arrivé) n'est pas un manque.
    jugees = [
        v
        for v in siennes
        if v.etat == "a_verifier" and v.motif not in (MOTIF_SANS_BANQUE, MOTIF_EN_COURS)
    ]
    sans_jour = [v for v in jugees if not v.jours and v.paye_cts]
    sans_virement = [v for v in jugees if v.jours and not v.paye_cts and v.du_cts > 0]
    manques = []
    if sans_jour:
        paye = euros(sum(v.paye_cts for v in sans_jour))
        manques.append(
            f"{_nom(nom)} : {len(sans_jour)} semaine(s) payée(s) en banque ({paye}) sans "
            f"aucun jour Rollee. {_conseil(nom, lien)}"
        )
    if sans_virement:
        du = euros(sum(v.du_cts for v in sans_virement))
        manques.append(
            f"{_nom(nom)} : aucun virement trouvé en banque pour {len(sans_virement)} "
            f"semaine(s) ({du} dus). Le compte bancaire qui reçoit {_nom(nom)} manque "
            "peut-être."
        )
    restantes = [v for v in jugees if v not in sans_jour and v not in sans_virement]
    if restantes:
        ecart = euros(sum(v.ecart_cts for v in restantes))
        manques.append(
            f"{_nom(nom)} : {len(restantes)} semaine(s) à vérifier, écart total {ecart}."
        )
    return manques


def manques(
    vues: Sequence[SemaineVue],
    comptes: Sequence[CompteRelie],
    plateformes: tuple[Plateforme, ...],
    debut_banque: date | None,
) -> list[str]:
    """Les phrases à montrer, de la plus bloquante à la plus fine ; vide si
    tout est rapproché."""
    resultat = _comptes(comptes, plateformes) + _banque(vues, debut_banque)
    liens = liens_par_plateforme(comptes, plateformes)
    for nom in sorted({v.plateforme for v in vues}):
        siennes = [v for v in vues if v.plateforme == nom]
        resultat += _plateforme(nom, siennes, liens.get(nom, "absente"))
    return resultat
