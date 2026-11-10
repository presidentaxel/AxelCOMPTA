"""Tenant et dossier. Les valeurs fiscales restent en texte ici ; leur
validation et leur lecture dans la matrice doc 06 §7 sont dans `statuts.py`,
appelé par les repositories avant toute écriture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from axelcompta.core.identite import IdentiteEntreprise
from axelcompta.core.ids import DossierId, TenantId

MODES_RELANCE = ("auto", "manuel")


def verifier_mode_relance(mode: str) -> None:
    if mode not in MODES_RELANCE:
        raise ValueError(f"mode de relance inconnu : {mode}")


@dataclass(frozen=True, slots=True)
class Tenant:
    """Mode portefeuille (1 → N dossiers) ou mono-entreprise (1 → 1), doc 01 §1."""

    id: TenantId
    nom: str = ""
    # Relances de connexion bancaire (doc 14 §2.3) : "auto", AxeLCompta
    # prévient le chauffeur dans l'application ; "manuel", seul le
    # gestionnaire est prévenu et contacte ses chauffeurs lui-même.
    relance_consentement: str = "auto"


@dataclass(frozen=True, slots=True)
class Dossier:
    """Un dossier comptable indépendant : sa config ne s'hérite jamais du tenant
    au-delà du pré-remplissage à la création (doc 03 §3bis).
    """

    id: DossierId
    tenant_id: TenantId
    forme_juridique: str  # FormeJuridique (statuts.py) : SASU, SAS, EURL, SARL, EI
    regime_imposition: str  # RegimeImposition : IS, option_IR, IR, micro
    regime_tva: str  # "reel_normal" | "reel_simplifie" | "franchise"
    nom: str
    tva_recettes_regime: str  # "assujetti_taux_reduit" | "franchise" (doc 14 §1.2)
    exercice_debut: date
    plateformes: tuple[str, ...] = ()
    # "gestionnaire" | "chauffeur_direct" (doc 19 §4) : qui connecte la banque.
    mode_acces_bancaire: str = "gestionnaire"
    # Numéro de contact Digifactory (doc 16 §9 point 5) : la table de
    # correspondance `contact_nr -> dossier_id` qui manquait pour brancher
    # `fetch_transactions`. Nullable : un dossier sans canal bancaire branché.
    contact_nr: str | None = None
    # Clôture de l'exercice en cours. `None` : douze mois après
    # `exercice_debut` (`fin_exercice`). Les deux bornes sont celles déclarées
    # sur la liasse, pas les dates de la première et de la dernière écriture.
    exercice_fin: date | None = None
    # Dénomination, SIREN, siège, associés (liasse fiscale, FEC). `None` pour
    # un dossier sans identité connue : on n'en invente pas (doc 07 §2.2).
    identite: IdentiteEntreprise | None = None
    # Retiré du portefeuille : les écritures restent, le dossier n'apparaît plus
    # dans la liste du gestionnaire.
    retire_le: date | None = None
    # Pack métier (règles, templates, taxonomie) : "vtc" seul aujourd'hui.
    pack_metier: str = "vtc"
    # Année du premier exercice couvert par l'option IR temporaire (art. 239
    # bis AB CGI). Obligatoire au régime option_IR, vide sinon.
    option_ir_debut: int | None = None
    # Exception au mode de relance du portefeuille pour ce dossier ; `None`
    # suit le portefeuille (doc 14 §2.3, « configuration par dossier »).
    relance_consentement: str | None = None
    # Activité principale Sirene (NAF), par exemple 49.32Z pour un VTC
    # (AXE-834). `None` : jamais lue.
    code_naf: str | None = None
    # Éléments de configuration proposés sans certitude (Sirene ne distingue
    # pas SAS et SASU, ni SARL et EURL ; premier exercice déduit de la date
    # de création) : « forme_juridique », « exercice ». Le dirigeant les
    # confirme (AXE-730) ; le gestionnaire voit « à confirmer ».
    a_confirmer: tuple[str, ...] = ()
    # TVA en cours d'année (AXE-805) : « mensuelle » ou « trimestrielle », et
    # le jour du mois suivant où tombe l'échéance (calendrier DGFiP, selon
    # le SIREN et la forme). `None` : pas encore réglé, rien n'est rappelé.
    tva_periodicite: str | None = None
    tva_jour_echeance: int | None = None

    def fin_exercice(self) -> date:
        if self.exercice_fin is not None:
            return self.exercice_fin
        debut = self.exercice_debut
        # Ouvert un 29/02 : l'anniversaire tombe le 01/03, on clôt la veille.
        if (debut.month, debut.day) == (2, 29):
            return date(debut.year + 1, 2, 28)
        return date(debut.year + 1, debut.month, debut.day) - timedelta(days=1)
