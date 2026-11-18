"""La reprise comptable d'une fiche préremplie par le dernier FEC (AXE-976). Pur.

Ce que le FEC du dernier exercice clos dit sans OCR, à la clôture :

- **Crédit de TVA à reporter** : le solde débiteur des comptes 44567 ;
- **Véhicule** : « Acheté » s'il y a un matériel de transport (2182) à
  l'actif, « LOA » s'il n'y en a pas mais des loyers de crédit-bail (612) ;
- **Véhicule : détail** : valeur d'origine, amortissements, valeur nette et
  date d'achat si le FEC la montre ;
- **Emprunts en cours** : le capital restant dû des comptes 164.

Les **déficits reportables** sont un chiffre fiscal (2033-B, 2033-D) : ils
ne se lisent pas dans un FEC et restent à saisir (ou à lire par l'OCR). L'
**ancien expert-comptable** est sur la première page de la liasse.

Une valeur lue remplace un champ vide, ou la lecture précédente (un FEC plus
récent) ; jamais une saisie. Ce qui a été lu est gardé dans le champ
`reprise_lue` de la fiche, pour l'écran (« FEC 2024 ») et pour savoir ce
qu'une nouvelle lecture peut remplacer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date

from .fiches_import import DocumentImport, FicheImport

CHAMP_LU = "reprise_lue"


def _euros(centimes: int) -> str:
    texte = f"{abs(centimes) / 100:,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if centimes < 0 else ''}{texte} €"


def _somme(soldes: Mapping[str, object], prefixe: str) -> int:
    return sum(int(str(v)) for c, v in soldes.items() if c.startswith(prefixe))


def _dernier_fec(documents: Sequence[DocumentImport], aujourd_hui: date) -> DocumentImport | None:
    lus = [
        d
        for d in documents
        if d.categorie == "fec"
        and (d.donnees or {}).get("type") == "fec"
        and d.exercice is not None
        and str((d.donnees or {}).get("fin") or "") < aujourd_hui.isoformat()
    ]
    return (
        max(lus, key=lambda d: (d.exercice or 0, str((d.donnees or {}).get("fin"))))
        if lus
        else None
    )


def _vehicule(
    donnees: Mapping[str, object], soldes: Mapping[str, object], au: str
) -> dict[str, str]:
    brut = _somme(soldes, "2182")
    if brut > 0:
        amortis = -_somme(soldes, "28182")
        immobilisations = donnees.get("immobilisations")
        achat = ""
        if isinstance(immobilisations, dict):
            dates = sorted(
                str(v.get("achat_le"))
                for c, v in immobilisations.items()
                if c.startswith("2182") and isinstance(v, dict)
            )
            if dates:
                achat = f", acheté le {date.fromisoformat(dates[0]):%d/%m/%Y}"
        detail = (
            f"Valeur d'origine {_euros(brut)}{achat} ; amortissements {_euros(amortis)}, "
            f"valeur nette {_euros(brut - amortis)} au {au}."
        )
        return {"vehicule": "achat", "vehicule_detail": detail}
    loyers = _somme(soldes, "612")
    if loyers > 0:
        return {
            "vehicule": "loa",
            "vehicule_detail": f"Loyers de crédit-bail de l'exercice : {_euros(loyers)} (612).",
        }
    return {}


def lecture(documents: Sequence[DocumentImport], aujourd_hui: date) -> tuple[dict[str, str], str]:
    """Les valeurs que le dernier FEC clos donne, et sa source (« FEC 2024 »)."""
    fec = _dernier_fec(documents, aujourd_hui)
    if fec is None:
        return {}, ""
    donnees = fec.donnees or {}
    soldes = donnees.get("soldes_cts")
    if not isinstance(soldes, dict):
        return {}, ""
    cloture = str(donnees.get("cloture") or donnees.get("fin"))
    au = f"{date.fromisoformat(cloture):%d/%m/%Y}"
    valeurs: dict[str, str] = {}
    credit_tva = _somme(soldes, "44567")
    if credit_tva > 0:
        valeurs["credit_tva"] = f"{credit_tva / 100:.2f}"
    valeurs.update(_vehicule(donnees, soldes, au))
    emprunts = -_somme(soldes, "164")
    if emprunts > 0:
        valeurs["emprunts"] = f"Capital restant dû {_euros(emprunts)} au {au} (comptes 164)."
    return valeurs, f"FEC {fec.exercice}"


def lu(champs: Mapping[str, str]) -> dict[str, dict[str, str]]:
    try:
        valeur = json.loads(champs.get(CHAMP_LU) or "{}")
    except ValueError:
        return {}
    return valeur if isinstance(valeur, dict) else {}


def preremplir_reprise(
    fiche: FicheImport, documents: Sequence[DocumentImport], aujourd_hui: date
) -> FicheImport:
    """La fiche avec ce que le dernier FEC donne ; une saisie n'est jamais
    écrasée. Rend la même fiche si rien ne change."""
    valeurs, source = lecture(documents, aujourd_hui)
    if not valeurs:
        return fiche
    anciens = lu(fiche.champs)
    champs = dict(fiche.champs)
    nouveaux = dict(anciens)
    for cle, valeur in valeurs.items():
        actuel = champs.get(cle, "")
        precedent = (anciens.get(cle) or {}).get("valeur")
        if not actuel or actuel == precedent:
            champs[cle] = valeur
            nouveaux[cle] = {"valeur": valeur, "source": source}
    champs[CHAMP_LU] = json.dumps(nouveaux, sort_keys=True, ensure_ascii=False)
    if champs == dict(fiche.champs):
        return fiche
    return replace(fiche, champs=champs)


def champs_lus_dans_un_fec(fiche: FicheImport) -> dict[str, str]:
    """Champ → source (« FEC 2024 ») pour les champs qui ont encore la
    valeur lue : une saisie par-dessus fait disparaître la mention."""
    return {
        cle: str(detail.get("source", ""))
        for cle, detail in lu(fiche.champs).items()
        if isinstance(detail, dict) and fiche.champs.get(cle) == detail.get("valeur")
    }
