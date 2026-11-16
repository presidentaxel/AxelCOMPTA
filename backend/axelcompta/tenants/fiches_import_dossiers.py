"""Une fiche d'import pour chaque entreprise déjà au portefeuille (AXE-952). Pur.

La synchro donne une fiche à chaque dossier, même vide, préremplie avec ce
qu'on en sait déjà (le dossier, son identité, ses comptes Rollee et
bancaires) : la fiche montre ce qui manque encore. Une fiche existante (même
dossier, ou même SIREN) est reprise et reliée au dossier, pas doublée ; seuls
ses champs vides se remplissent. Une fiche annulée ne revient pas.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId

from .fiches_import import FORMES, PLATEFORMES, FicheImport, valider
from .fiches_import_calculs import appliquer_deductions
from .fiches_import_listes import FONCTION_PAR_FORME
from .models import Dossier

PAR_SYNCHRO = "synchro"
PLATEFORMES_CONNUES = {cle for cle, _ in PLATEFORMES}


@dataclass(frozen=True, slots=True)
class CompteRolleeDuDossier:
    rollee_user_id: str
    nom: str  # le nom du user Rollee (carte), « » s'il n'est pas lu
    plateformes: tuple[str, ...]  # « uber », « bolt »…


@dataclass(frozen=True, slots=True)
class DonneesDossier:
    """Ce qu'on sait d'un dossier, hors de la fiche."""

    dossier: Dossier
    comptes_rollee: tuple[CompteRolleeDuDossier, ...] = ()
    comptes_bancaires: tuple[str, ...] = ()  # « Compte pro (retenu) »
    debut_historique: date | None = None  # première opération bancaire reçue


def id_fiche_du_dossier(dossier_id: DossierId) -> str:
    return f"dossier-{dossier_id}"


def _identite(dossier: Dossier) -> dict[str, str]:
    identite = dossier.identite
    if identite is None:
        return {}
    fonction = FONCTION_PAR_FORME.get(dossier.forme_juridique, "dirigeant")
    associes = [
        {"prenom": a.prenoms.split(" ")[0], "nom": a.nom, "fonction": fonction, "pourcentage": ""}
        for a in identite.associes
    ]
    valeurs = {
        "siege": identite.adresse_siege.sur_une_ligne(),
        "capital": f"{identite.capital_social_cts / 100:.2f}",
        "email": identite.email,
        "associes": json.dumps(associes, ensure_ascii=False) if associes else "",
    }
    if identite.associes:
        valeurs["nom"], valeurs["prenom"] = identite.dirigeant.nom, identite.dirigeant.prenoms
    if identite.nic:
        valeurs["siret"] = identite.siret
    return valeurs


def _dossier(dossier: Dossier) -> dict[str, str]:
    valeurs = {
        "denomination": dossier.nom,
        "siren": dossier.siren or (dossier.identite.siren if dossier.identite else ""),
        "forme_juridique": dossier.forme_juridique
        if dossier.forme_juridique in dict(FORMES)
        else "",
        "regime_imposition": dossier.regime_imposition,
        "option_ir_debut": str(dossier.option_ir_debut or ""),
        "regime_tva": dossier.regime_tva,
        "exercice_debut": dossier.exercice_debut.isoformat(),
        "exercice_fin": dossier.fin_exercice().isoformat(),
        "code_naf": dossier.code_naf or "",
        "contact_digifactory": dossier.contact_nr or "",
        "deficits": str(dossier.deficits_anterieurs_euros or ""),
    }
    return valeurs


def _rollee_et_banque(d: DonneesDossier) -> dict[str, str]:
    plateformes = sorted(
        {p for c in d.comptes_rollee for p in c.plateformes if p in PLATEFORMES_CONNUES}
        | {p for p in d.dossier.plateformes if p in PLATEFORMES_CONNUES}
    )
    comptes = [
        {"rollee_user_id": c.rollee_user_id, "nom": c.nom, "plateformes": list(c.plateformes)}
        for c in d.comptes_rollee
    ]
    return {
        "plateformes": ",".join(plateformes),
        "comptes_rollee": json.dumps(comptes, ensure_ascii=False) if comptes else "",
        "comptes_bancaires": "\n".join(d.comptes_bancaires),
        "debut_historique": d.debut_historique.isoformat() if d.debut_historique else "",
    }


def champs_du_dossier(d: DonneesDossier) -> dict[str, str]:
    """Les champs de la fiche que le dossier remplit ; une valeur que la
    fiche refuserait (format inattendu) est laissée de côté, pas inventée."""
    brutes = {**_dossier(d.dossier), **_identite(d.dossier), **_rollee_et_banque(d)}
    rangees: dict[str, str] = {}
    for cle, valeur in brutes.items():
        if not valeur:
            continue
        try:
            rangees.update(valider({cle: valeur}))
        except SaisieInvalide:
            continue
    return {k: v for k, v in rangees.items() if v}


def _sienne(d: DonneesDossier, fiches: Sequence[FicheImport]) -> FicheImport | None:
    """La fiche de ce dossier : reliée à lui (même annulée : elle ne revient
    pas), sinon une fiche ouverte au même SIREN, reliée à aucun dossier."""
    siren = d.dossier.siren
    for fiche in fiches:
        if fiche.dossier_id == d.dossier.id:
            return fiche
    for fiche in fiches:
        if (
            siren
            and fiche.dossier_id is None
            and fiche.annulee_le is None
            and fiche.champs.get("siren") == siren
        ):
            return fiche
    return None


def fiche_du_dossier(
    d: DonneesDossier, fiches: Sequence[FicheImport], le: datetime
) -> FicheImport | None:
    """La fiche à enregistrer pour ce dossier (créée, ou complétée) ; `None`
    s'il n'y a rien à changer, ou si sa fiche a été annulée."""
    connus = champs_du_dossier(d)
    existante = _sienne(d, fiches)
    if existante is None:
        champs = appliquer_deductions({}, connus, le.date())
        return FicheImport(
            id=id_fiche_du_dossier(d.dossier.id),
            tenant_id=d.dossier.tenant_id,
            nom=champs.get("nom", ""),
            prenom=champs.get("prenom", ""),
            cree_par=PAR_SYNCHRO,
            cree_le=le,
            champs=champs,
            dossier_id=d.dossier.id,
            maj_par=PAR_SYNCHRO,
            maj_le=le,
        )
    if existante.annulee_le is not None:
        return None
    vides = {k: v for k, v in connus.items() if not existante.champs.get(k)}
    if not vides and existante.dossier_id == d.dossier.id:
        return None
    champs = appliquer_deductions(existante.champs, {**existante.champs, **vides}, le.date())
    return replace(
        existante,
        champs=champs,
        nom=existante.nom or champs.get("nom", ""),
        prenom=existante.prenom or champs.get("prenom", ""),
        dossier_id=d.dossier.id,
        maj_par=PAR_SYNCHRO,
        maj_le=le,
    )


def completer_portefeuille(
    donnees: Sequence[DonneesDossier], fiches: Sequence[FicheImport], le: datetime
) -> tuple[list[FicheImport], int, int]:
    """Les fiches à enregistrer, et combien sont créées et complétées."""
    a_ecrire, creees, completees = [], 0, 0
    deja: Mapping[str, FicheImport] = {f.id: f for f in fiches}
    for d in donnees:
        if d.dossier.retire_le is not None:
            continue
        fiche = fiche_du_dossier(d, fiches, le)
        if fiche is None:
            continue
        a_ecrire.append(fiche)
        if fiche.id in deja:
            completees += 1
        else:
            creees += 1
    return a_ecrire, creees, completees
