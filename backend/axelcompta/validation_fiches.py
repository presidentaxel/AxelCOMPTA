"""Les critères pour qu'un chauffeur soit importé (AXE-989).

Un chauffeur importé est un chauffeur dont les données sont à jour à tout
moment pour l'exercice en cours, et complètes pour l'exercice clos que nous
devons déclarer. Deux sections ont des critères à elles, au-delà des champs
et des documents attendus :

**Banque**, compte par compte (comptes Digifactory retenus, et ce qui leur
est rattaché) :

* exercice clos à déclarer : aucune période manquante ni en écart. Des
  relevés seuls suffisent ;
* exercice en cours, du début à aujourd'hui : pareil, et Digifactory doit
  être relié et à jour (dernier relevé de solde de moins de
  `DELAI_DIGIFACTORY` jours). Des relevés seuls ne suffisent pas : ils
  comblent seulement les mois d'avant Digifactory.

**Plateformes**, plateforme par plateforme (déclarées sur la fiche, ou vues
en banque ou chez Rollee) :

* exercice clos à déclarer : chaque mois couvert par Rollee ou par un
  document ; aucun mois « à compléter » ni « ni banque ni Rollee » ;
* exercice en cours : pareil, et Rollee doit être relié et à jour (dernier
  jour gagné de moins de `DELAI_ROLLEE` jours). Des documents comblent les
  mois d'avant Rollee.

Un mois « Rollee sans banque » n'échoue pas ici : c'est la banque qui le
fait échouer. Pur : prend les couvertures déjà calculées.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from axelcompta.couverture_bancaire_fiche import CompteCouvert
from axelcompta.couverture_plateformes import NOMS, PlateformeCouverte, libelle_mois
from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.tenants.couverture_bancaire import phrase
from axelcompta.tenants.fiches_import_etat import Exercice
from axelcompta.tenants.fiches_import_validation import SECTIONS_VALIDEES

DELAI_DIGIFACTORY = 3  # jours : la synchro passe chaque heure
DELAI_ROLLEE = 10  # jours : Rollee remonte les jours avec quelques jours de retard


@dataclass(frozen=True, slots=True)
class Critere:
    section: str  # banque | plateformes
    libelle: str
    ok: bool
    detail: str = ""


def _jj(jour: date) -> str:
    return f"{jour:%d/%m/%Y}"


def _tenus(exercices: Sequence[Exercice]) -> tuple[list[Exercice], Exercice | None]:
    a_declarer = [e for e in exercices if e.role == "a_declarer"]
    en_cours = next((e for e in exercices if e.role == "en_cours"), None)
    return a_declarer, en_cours


def _manques_compte(compte: CompteCouvert, debut: date, fin: date) -> list[str]:
    return [
        phrase(p)
        for p in compte.couverture.periodes
        if p.etat in ("manquant", "ecart") and p.fin >= debut and p.debut <= fin
    ]


def valider_banque(
    exercices: Sequence[Exercice],
    comptes: Sequence[CompteBancaire],
    couverts: Sequence[CompteCouvert],
    aujourd_hui: date,
) -> list[Critere]:
    a_declarer, en_cours = _tenus(exercices)
    if not a_declarer and en_cours is None:
        return [Critere("banque", "Exercices connus", False, "Dates d'exercice à compléter.")]
    retenus = [c for c in comptes if c.retenu is True]
    criteres = [
        Critere(
            "banque",
            "Digifactory relié",
            bool(retenus),
            ""
            if retenus
            else "Aucun compte Digifactory retenu : il faut Digifactory pour l'exercice en cours.",
        )
    ]
    for compte in retenus:
        nom = compte.nom or compte.compte_comptable
        dernier = compte.solde_releve_le.date() if compte.solde_releve_le else None
        a_jour = dernier is not None and dernier >= aujourd_hui - timedelta(days=DELAI_DIGIFACTORY)
        criteres.append(
            Critere(
                "banque",
                f"{nom} à jour sur Digifactory",
                a_jour,
                ""
                if a_jour
                else (
                    f"Dernier relevé Digifactory le {_jj(dernier)}."
                    if dernier
                    else "Jamais relevé par Digifactory."
                ),
            )
        )
    suivis = [c for c in couverts if c.suivi]
    for exercice in a_declarer:
        criteres += _couverture_exercice(
            suivis, exercice.debut, exercice.fin, f"Exercice clos le {_jj(exercice.fin)}"
        )
    if en_cours is not None:
        criteres += _couverture_exercice(
            suivis, en_cours.debut, aujourd_hui, "Exercice en cours, jusqu'à aujourd'hui"
        )
    return criteres


def _couverture_exercice(
    suivis: Sequence[CompteCouvert], debut: date, fin: date, titre: str
) -> list[Critere]:
    criteres = []
    for compte in suivis:
        manques = _manques_compte(compte, debut, fin)
        criteres.append(
            Critere(
                "banque",
                f"{titre} : {compte.libelle} complet",
                not manques,
                " ; ".join(manques),
            )
        )
    return criteres


def plateformes_declarees(champs: Mapping[str, str]) -> set[str]:
    valeur = champs.get("plateformes") or ""
    return {p.strip() for p in valeur.split(",") if p.strip() and p.strip() != "autre"}


def valider_plateformes(
    exercices: Sequence[Exercice],
    couvertes: Sequence[PlateformeCouverte],
    jours: Iterable[tuple[str, date]],
    declarees: set[str],
    aujourd_hui: date,
) -> list[Critere]:
    a_declarer, en_cours = _tenus(exercices)
    if not a_declarer and en_cours is None:
        return [Critere("plateformes", "Exercices connus", False, "Dates d'exercice à compléter.")]
    derniers: dict[str, date] = {}
    for plateforme, jour in jours:
        derniers[plateforme] = max(jour, derniers.get(plateforme, jour))
    par_cle = {c.plateforme: c for c in couvertes}
    toutes = sorted(declarees | set(par_cle))
    if not toutes:
        return [
            Critere(
                "plateformes",
                "Plateformes connues",
                False,
                "Aucune plateforme déclarée, ni vue en banque ou chez Rollee.",
            )
        ]
    criteres = []
    for plateforme in toutes:
        nom = NOMS.get(plateforme, plateforme.capitalize())
        couverte = par_cle.get(plateforme)
        for exercice in a_declarer:
            criteres.append(
                _mois_couverts(nom, couverte, exercice.debut, exercice.fin, exercice.fin)
            )
        if en_cours is not None:
            criteres.append(_mois_couverts(nom, couverte, en_cours.debut, aujourd_hui, None))
            dernier = derniers.get(plateforme)
            a_jour = dernier is not None and dernier >= aujourd_hui - timedelta(days=DELAI_ROLLEE)
            criteres.append(
                Critere(
                    "plateformes",
                    f"{nom} à jour sur Rollee",
                    a_jour,
                    ""
                    if a_jour
                    else (
                        f"Dernier jour Rollee le {_jj(dernier)}."
                        if dernier
                        else "Aucun jour Rollee : relier le compte dans Rollee."
                    ),
                )
            )
    return criteres


def _mois_couverts(
    nom: str, couverte: PlateformeCouverte | None, debut: date, fin: date, cloture: date | None
) -> Critere:
    titre = f"Exercice clos le {_jj(cloture)}" if cloture else "Exercice en cours"
    if couverte is None:
        return Critere("plateformes", f"{titre} : {nom} couvert", False, "Aucune donnée.")
    premier, dernier = f"{debut.year}-{debut.month:02d}", f"{fin.year}-{fin.month:02d}"
    manquants = [
        libelle_mois(m.mois)
        for m in couverte.mois
        if premier <= m.mois <= dernier and m.etat in ("a_completer", "inconnu")
    ]
    detail = f"À compléter : {', '.join(manquants)}." if manquants else ""
    return Critere("plateformes", f"{titre} : {nom} couvert", not manquants, detail)


@dataclass(frozen=True, slots=True)
class Validation:
    criteres: tuple[Critere, ...]
    le: datetime

    def section_ok(self, section: str) -> bool:
        return all(c.ok for c in self.criteres if c.section == section)

    @property
    def importe(self) -> bool:
        return all(c.ok for c in self.criteres)

    def manques(self, section: str) -> list[str]:
        return [
            f"{c.libelle}" + (f" : {c.detail}" if c.detail else "")
            for c in self.criteres
            if c.section == section and not c.ok
        ]

    def json(self) -> str:
        """Ce que garde la fiche (champ `validation_import`) : les manques de
        chaque section, pour son statut et ses catégories."""
        return json.dumps(
            {
                "le": self.le.isoformat(timespec="minutes"),
                **{s: self.manques(s) for s in SECTIONS_VALIDEES},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
