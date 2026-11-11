"""Les intégrations d'un portefeuille, plusieurs par type (AXE-872).

Un **branchement** est une intégration nommée : « SMTP agence Nord »,
« Digifactory compte 2 ». Un portefeuille peut en avoir plusieurs du même
type. Pour chaque type, un seul est **par défaut**. Un dossier peut en
choisir un autre ; sans choix, ou si son choix est désactivé, c'est celui
par défaut qui sert.

Les identifiants sont chiffrés (`core.chiffrement`, clé hors base) et ne
reviennent jamais à l'écran. Ce module ne fait aucun appel réseau : tester
un branchement est le travail du module qui sait lui parler (SMTP dans
`workflow`, Digifactory dans `ingestion`).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol

from axelcompta.core.chiffrement import chiffrer, dechiffrer
from axelcompta.core.errors import Conflit, Introuvable, SaisieInvalide
from axelcompta.core.ids import DossierId, TenantId

# Type → fournisseurs possibles. Un type est ce dont le reste du code a
# besoin (« un e-mail », « une banque ») ; le fournisseur dit comment.
FOURNISSEURS: dict[str, tuple[str, ...]] = {
    "mail": ("smtp",),
    "sms": ("http",),
    "digifactory": ("digifactory",),
    "rollee": ("rollee",),
}
# Champs obligatoires, puis facultatifs, par fournisseur.
CHAMPS: dict[str, tuple[str, ...]] = {
    "smtp": ("hote", "port", "utilisateur", "mot_de_passe", "expediteur"),
    "http": ("url", "cle_api", "expediteur"),
    "digifactory": ("jeton", "url"),
    # AXE-818 : JWT du tableau de bord Rollee (Settings → JWT Token). Les
    # jetons sandbox et production sont distincts.
    "rollee": ("jeton", "environnement"),
}
# Valeurs permises, quand un champ n'accepte qu'une liste.
VALEURS: dict[str, tuple[str, ...]] = {"environnement": ("sandbox", "production")}
CHAMPS_FACULTATIFS: dict[str, tuple[str, ...]] = {}
# Jamais renvoyés à l'écran. Un champ vide à la mise à jour garde la valeur
# déjà chiffrée : on retape le jeton seulement pour le remplacer.
SECRETS = frozenset({"mot_de_passe", "cle_api", "jeton"})
# Rollee : plusieurs comptes pour une même compta. Aucun n'est « le » compte.
# Tant qu'un compte pro n'est pas relié à l'un d'eux, on les interroge tous.
SANS_DEFAUT = frozenset({"rollee"})
NOM_MAX = 60


class BranchementInvalide(SaisieInvalide):
    """Type ou fournisseur inconnu, champ manquant, nom vide."""


class BranchementIntrouvable(Introuvable):
    """Aucun branchement de ce portefeuille ne porte cet identifiant."""


class BranchementEnConflit(Conflit):
    """Nom déjà pris, ou défaut qu'on ne peut pas retirer."""


@dataclass(frozen=True, slots=True)
class Branchement:
    id: str
    tenant_id: TenantId
    type: str
    fournisseur: str
    nom: str
    parametres_chiffres: str  # JSON des paramètres, chiffré
    par_defaut: bool = False
    actif: bool = True
    maj_le: datetime | None = None

    def parametres(self) -> dict[str, str]:
        """Déchiffrés : à n'utiliser qu'au moment d'appeler le fournisseur."""
        valeurs: dict[str, str] = json.loads(dechiffrer(self.parametres_chiffres))
        return valeurs


def chiffrer_parametres(fournisseur: str, parametres: dict[str, str]) -> str:
    """Garde les champs connus du fournisseur, vérifie les obligatoires,
    chiffre. Lève `BranchementInvalide`."""
    obligatoires = CHAMPS.get(fournisseur)
    if obligatoires is None:
        raise BranchementInvalide(f"Fournisseur « {fournisseur} » inconnu.")
    manquants = [c for c in obligatoires if not str(parametres.get(c, "")).strip()]
    if manquants:
        raise BranchementInvalide(f"Champs manquants : {', '.join(manquants)}.")
    for champ, permises in VALEURS.items():
        if champ in obligatoires and str(parametres[champ]).strip() not in permises:
            raise BranchementInvalide(f"{champ} : {' ou '.join(permises)}.")
    utiles = {
        c: str(parametres[c]).strip()
        for c in obligatoires + CHAMPS_FACULTATIFS.get(fournisseur, ())
        if str(parametres.get(c, "")).strip()
    }
    return chiffrer(json.dumps(utiles))


def fusionner_parametres(actuel: Branchement, saisis: dict[str, str]) -> str:
    """Rechiffre avec la clé d'environnement. Un secret vide garde l'ancien."""
    fusion = actuel.parametres()
    for cle, valeur in saisis.items():
        texte = str(valeur).strip()
        if cle in SECRETS:
            if texte:
                fusion[cle] = texte
            continue
        if texte:
            fusion[cle] = texte
        else:
            fusion.pop(cle, None)
    return chiffrer_parametres(actuel.fournisseur, fusion)


def lecture_publique(branchement: Branchement) -> tuple[dict[str, str], tuple[str, ...]]:
    """Champs lisibles, et les noms des secrets enregistrés. Pas leurs valeurs."""
    valeurs = branchement.parametres()
    publics = {cle: valeur for cle, valeur in valeurs.items() if cle not in SECRETS}
    return publics, tuple(cle for cle in valeurs if cle in SECRETS)


def _nom_valide(nom: str) -> str:
    propre = " ".join(nom.split())
    if not propre:
        raise BranchementInvalide("Donnez un nom à ce branchement.")
    if len(propre) > NOM_MAX:
        raise BranchementInvalide(f"Nom trop long ({NOM_MAX} caractères au plus).")
    return propre


def _nom_libre(existants: Sequence[Branchement], type_: str, nom: str, sauf: str) -> None:
    pris = {b.nom.casefold() for b in existants if b.type == type_ and b.id != sauf}
    if nom.casefold() in pris:
        raise BranchementEnConflit(f"Un branchement s'appelle déjà « {nom} ».")


def nouveau(
    existants: Sequence[Branchement],
    tenant_id: TenantId,
    type_: str,
    fournisseur: str,
    nom: str,
    parametres: dict[str, str],
) -> Branchement:
    """Le premier branchement actif d'un type devient celui par défaut.
    Rollee n'en a pas : chaque accès est un compte distinct."""
    if fournisseur not in FOURNISSEURS.get(type_, ()):
        raise BranchementInvalide(f"Fournisseur « {fournisseur} » inconnu pour {type_}.")
    nom = _nom_valide(nom)
    _nom_libre(existants, type_, nom, sauf="")
    deja_un_defaut = any(b.type == type_ and b.actif and b.par_defaut for b in existants)
    return Branchement(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        type=type_,
        fournisseur=fournisseur,
        nom=nom,
        parametres_chiffres=chiffrer_parametres(fournisseur, parametres),
        par_defaut=type_ not in SANS_DEFAUT and not deja_un_defaut,
    )


@dataclass(frozen=True, slots=True)
class Modification:
    """Ce que le gestionnaire change ; `None` : inchangé."""

    nom: str | None = None
    parametres: dict[str, str] | None = None
    par_defaut: bool | None = None
    actif: bool | None = None


def _oter_le_defaut(
    suite: Branchement, autres: list[Branchement], demande_un_defaut: bool
) -> list[Branchement] | None:
    """Rollee n'a pas de défaut : on l'ôte, y compris sur les autres accès."""
    if suite.type not in SANS_DEFAUT:
        return None
    if demande_un_defaut:
        raise BranchementInvalide("Ce type n'a pas de branchement par défaut.")
    suite = replace(suite, par_defaut=False)
    return [replace(b, par_defaut=False) for b in autres if b.par_defaut] + [suite]


def modifier(
    existants: Sequence[Branchement], id_: str, modification: Modification
) -> list[Branchement]:
    """Les branchements à enregistrer : le modifié, et l'ancien défaut s'il
    perd sa place. Le défaut ne se désactive pas tant qu'un autre branchement
    actif du même type pourrait le remplacer : on choisit d'abord le nouveau
    défaut, rien ne bascule en silence."""
    actuel = next((b for b in existants if b.id == id_), None)
    if actuel is None:
        raise BranchementIntrouvable(f"Branchement inconnu : {id_}")
    suite = actuel
    if modification.nom is not None:
        nom = _nom_valide(modification.nom)
        _nom_libre(existants, actuel.type, nom, sauf=actuel.id)
        suite = replace(suite, nom=nom)
    if modification.parametres is not None:
        suite = replace(
            suite, parametres_chiffres=fusionner_parametres(actuel, modification.parametres)
        )
    if modification.actif is not None:
        suite = replace(suite, actif=modification.actif)
    autres = [b for b in existants if b.type == actuel.type and b.id != actuel.id and b.actif]
    sans_defaut = _oter_le_defaut(suite, autres, bool(modification.par_defaut))
    if sans_defaut is not None:
        return sans_defaut
    if modification.par_defaut:
        suite = replace(suite, par_defaut=True, actif=True)
    if actuel.par_defaut and not suite.actif and autres:
        raise BranchementEnConflit(
            "C'est le branchement par défaut : choisissez d'abord celui qui le remplace."
        )
    if not suite.actif:
        suite = replace(suite, par_defaut=False)
    elif not any(b.par_defaut for b in autres):
        suite = replace(suite, par_defaut=True)  # seul actif du type : il sert par défaut
    retires = [replace(b, par_defaut=False) for b in autres if b.par_defaut and suite.par_defaut]
    return [*retires, suite]


def choisir(
    branchements: Sequence[Branchement], type_: str, choix_dossier: str | None
) -> Branchement | None:
    """Celui que le dossier a choisi s'il est actif, sinon celui par défaut."""
    actifs = [b for b in branchements if b.type == type_ and b.actif]
    if choix_dossier is not None:
        choisi = next((b for b in actifs if b.id == choix_dossier), None)
        if choisi is not None:
            return choisi
    return next((b for b in actifs if b.par_defaut), None)


def a_interroger(
    branchements: Sequence[Branchement], type_: str, choix_dossier: str | None
) -> list[Branchement]:
    """Où lire. Le branchement choisi pour le dossier, s'il est actif.
    Sinon, pour Rollee, tous les accès actifs : le compte peut venir de
    n'importe lequel tant qu'il n'est pas relié. Les autres types : le défaut."""
    actifs = [b for b in branchements if b.type == type_ and b.actif]
    if choix_dossier is not None:
        choisi = next((b for b in actifs if b.id == choix_dossier), None)
        if choisi is not None:
            return [choisi]
    if type_ in SANS_DEFAUT:
        return actifs
    defaut = next((b for b in actifs if b.par_defaut), None)
    return [defaut] if defaut is not None else []


def types_branches(branchements: Sequence[Branchement]) -> dict[str, datetime]:
    """Type branché → date du dernier réglage. Rien de secret.
    Un type sans défaut (Rollee) compte dès qu'un accès est actif."""
    vus: dict[str, datetime] = {}
    for b in branchements:
        if not b.actif or (b.type not in SANS_DEFAUT and not b.par_defaut):
            continue
        le = b.maj_le or datetime.min
        if b.type not in vus or le > vus[b.type]:
            vus[b.type] = le
    return vus


class BranchementsRepository(Protocol):
    def lister(self, tenant_id: TenantId) -> list[Branchement]: ...

    def enregistrer(self, branchements: Sequence[Branchement], par: str, le: datetime) -> None:
        """Ajoute ou remplace, dans une seule transaction. Ceux qui perdent
        leur place de défaut passent avant celui qui la prend."""
        ...

    def choix_du_dossier(self, tenant_id: TenantId, dossier_id: DossierId) -> dict[str, str]:
        """Type → identifiant du branchement choisi pour ce dossier."""
        ...

    def choisir_pour_dossier(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        type_: str,
        branchement_id: str | None,
    ) -> None:
        """`None` : le dossier revient au branchement par défaut."""
        ...


def pour_dossier(
    depot: BranchementsRepository, tenant_id: TenantId, dossier_id: DossierId, type_: str
) -> Branchement | None:
    choix = depot.choix_du_dossier(tenant_id, dossier_id).get(type_)
    return choisir(depot.lister(tenant_id), type_, choix)


def verifier_choix(
    branchements: Sequence[Branchement], type_: str, branchement_id: str | None
) -> None:
    """Un dossier ne choisit qu'un branchement actif du bon type."""
    if branchement_id is None:
        return
    if not any(b.id == branchement_id and b.type == type_ and b.actif for b in branchements):
        raise BranchementInvalide("Ce branchement n'existe pas pour ce type, ou il est désactivé.")


@dataclass
class BranchementsMemoire:
    branchements: dict[str, Branchement] = field(default_factory=dict)
    choix: dict[tuple[str, str], str] = field(default_factory=dict)

    def lister(self, tenant_id: TenantId) -> list[Branchement]:
        """Même ordre que Postgres : par type, puis par nom."""
        return sorted(
            (b for b in self.branchements.values() if b.tenant_id == tenant_id),
            key=lambda b: (b.type, b.nom),
        )

    def enregistrer(self, branchements: Sequence[Branchement], par: str, le: datetime) -> None:
        for branchement in branchements:
            self.branchements[branchement.id] = replace(branchement, maj_le=le)

    def choix_du_dossier(self, tenant_id: TenantId, dossier_id: DossierId) -> dict[str, str]:
        return {t: b for (d, t), b in self.choix.items() if d == dossier_id}

    def choisir_pour_dossier(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        type_: str,
        branchement_id: str | None,
    ) -> None:
        if branchement_id is None:
            self.choix.pop((dossier_id, type_), None)
        else:
            self.choix[(dossier_id, type_)] = branchement_id


def garder_parametre(
    depot: BranchementsRepository, branchement: Branchement, cle: str, par: str
) -> Callable[[str], None]:
    """Un fournisseur qui renouvelle un identifiant (le jeton Rollee, AXE-818) :
    la nouvelle valeur remplace l'ancienne dans le branchement, sinon le
    prochain appel repartirait d'une valeur périmée."""

    def garder(valeur: str) -> None:
        parametres = {**branchement.parametres(), cle: valeur}
        a_enregistrer = modifier(
            depot.lister(branchement.tenant_id), branchement.id, Modification(parametres=parametres)
        )
        depot.enregistrer(a_enregistrer, par, datetime.now(UTC))

    return garder
