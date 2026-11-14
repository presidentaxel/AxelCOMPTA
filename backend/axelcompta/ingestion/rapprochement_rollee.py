"""Relier un user Rollee au bon dossier (AXE-911). Pur : aucun appel, aucune base.

Indices comparés, chacun réduit à une empreinte (HMAC) dès la lecture : on
ne garde ni le profil Rollee, ni l'IBAN, ni le nom en clair.

* `metadata` : le dossier inscrit à la création du user (users créés par nous) ;
* IBAN de versement (Rollee) contre IBAN des comptes Digifactory ;
* nom et prénom, e-mail, téléphone.

Un user est relié seul seulement si un seul dossier correspond et que
l'indice est sûr : `metadata`, l'IBAN, le même e-mail ou le même
téléphone. Le nom n'est pas exigé : le même e-mail ou le même numéro,
c'est la même personne, même si l'autre contact diffère. Sinon il va au
gestionnaire (« à choisir »), ou il n'est pas trouvé. Un user déjà
relié n'est jamais touché. Un chauffeur peut être sur plusieurs comptes
Rollee : un second indice sûr se relie aussi, y compris par le téléphone
ou l'e-mail d'un compte déjà relié.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

INDICE_METADATA = "metadata"
INDICE_IBAN = "iban"
INDICE_NOM_EMAIL = "nom_email"
INDICE_NOM_TELEPHONE = "nom_telephone"

RAISON_IBAN = "même IBAN"
RAISON_NOM = "même nom"
RAISON_EMAIL = "même e-mail"
RAISON_TELEPHONE = "même téléphone"
RAISON_METADATA = "créé depuis ce dossier"
RAISON_RETIRE = "lien déjà retiré par le gestionnaire"

Etat = Literal["relie_auto", "a_choisir", "non_trouve"]


def normaliser_nom(*parties: str | None) -> str:
    """« Élodie  MARTIN-DUPONT » et « martin dupont elodie » donnent la même clé."""
    texte = " ".join(p for p in parties if p)
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    mots = re.findall(r"[A-Z]+", sans_accents.upper())
    return " ".join(sorted(mots))


def normaliser_iban(iban: str | None) -> str:
    return re.sub(r"\s+", "", iban or "").upper()


def normaliser_email(email: str | None) -> str:
    return (email or "").strip().lower()


def normaliser_telephone(telephone: str | None) -> str:
    """Chiffres seuls, au format national : +33 6… et 06… se comparent."""
    chiffres = re.sub(r"\D", "", telephone or "")
    if chiffres.startswith("33") and len(chiffres) == 11:
        return "0" + chiffres[2:]
    return chiffres


def empreinte(cle: bytes, valeur: str) -> str:
    """HMAC-SHA256 tronqué : comparable, pas réversible sans la clé."""
    if not valeur:
        return ""
    return hmac.new(cle, valeur.encode(), hashlib.sha256).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class Empreintes:
    ibans: frozenset[str] = frozenset()
    noms: frozenset[str] = frozenset()
    emails: frozenset[str] = frozenset()
    telephones: frozenset[str] = frozenset()


def empreintes(
    cle: bytes,
    ibans: Iterable[str | None] = (),
    noms: Iterable[str] = (),
    emails: Iterable[str | None] = (),
    telephones: Iterable[str | None] = (),
) -> Empreintes:
    """Valeurs en clair → empreintes. `noms` : déjà passés par `normaliser_nom`."""

    def jeu(valeurs: Iterable[str]) -> frozenset[str]:
        return frozenset(e for v in valeurs if (e := empreinte(cle, v)))

    return Empreintes(
        ibans=jeu(normaliser_iban(i) for i in ibans),
        noms=jeu(noms),
        emails=jeu(normaliser_email(e) for e in emails),
        telephones=jeu(normaliser_telephone(t) for t in telephones),
    )


@dataclass(frozen=True, slots=True)
class Apercu:
    """Ce que le gestionnaire voit d'un user Rollee : rien qui identifie en clair."""

    initiales: str = ""
    plateformes: tuple[str, ...] = ()
    iban_fin: str | None = None  # 4 derniers chiffres


def apercu(
    prenom: str | None, nom: str | None, plateformes: Iterable[str], iban: str | None
) -> Apercu:
    initiales = "".join(f"{p.strip()[0].upper()}." for p in (prenom, nom) if p and p.strip())
    fin = normaliser_iban(iban)[-4:] or None
    return Apercu(initiales, tuple(sorted(set(plateformes))), fin)


@dataclass(frozen=True, slots=True)
class UserRollee:
    user_id: str
    dossier_metadata: str | None
    empreintes: Empreintes
    apercu: Apercu = field(default_factory=Apercu)


@dataclass(frozen=True, slots=True)
class DossierIndices:
    dossier_id: str
    empreintes: Empreintes


@dataclass(frozen=True, slots=True)
class Candidat:
    dossier_id: str
    raisons: tuple[str, ...]
    sur: bool

    @property
    def indice(self) -> str:
        if RAISON_METADATA in self.raisons:
            return INDICE_METADATA
        if RAISON_IBAN in self.raisons:
            return INDICE_IBAN
        return INDICE_NOM_EMAIL if RAISON_EMAIL in self.raisons else INDICE_NOM_TELEPHONE


@dataclass(frozen=True, slots=True)
class Issue:
    user_id: str
    etat: Etat
    dossier_id: str | None = None  # relie_auto seulement
    indice: str | None = None
    candidats: tuple[Candidat, ...] = ()


def _raisons(user: Empreintes, dossier: Empreintes) -> tuple[str, ...]:
    raisons = []
    if user.ibans & dossier.ibans:
        raisons.append(RAISON_IBAN)
    if user.noms & dossier.noms:
        raisons.append(RAISON_NOM)
    if user.emails & dossier.emails:
        raisons.append(RAISON_EMAIL)
    if user.telephones & dossier.telephones:
        raisons.append(RAISON_TELEPHONE)
    return tuple(raisons)


def _sur(raisons: Sequence[str]) -> bool:
    if RAISON_IBAN in raisons or RAISON_METADATA in raisons:
        return True
    return RAISON_EMAIL in raisons or RAISON_TELEPHONE in raisons


def candidats(user: UserRollee, dossiers: Sequence[DossierIndices]) -> list[Candidat]:
    """Classés par force : sûrs d'abord, puis par nombre d'indices."""
    trouves = []
    for dossier in dossiers:
        raisons = _raisons(user.empreintes, dossier.empreintes)
        if user.dossier_metadata == dossier.dossier_id:
            raisons = (RAISON_METADATA, *raisons)
        if raisons:
            trouves.append(Candidat(dossier.dossier_id, raisons, _sur(raisons)))
    return sorted(trouves, key=lambda c: (not c.sur, -len(c.raisons), c.dossier_id))


def unir(a: Empreintes, b: Empreintes) -> Empreintes:
    """Les indices de deux sources du même chauffeur, sans en perdre."""
    return Empreintes(
        ibans=a.ibans | b.ibans,
        noms=a.noms | b.noms,
        emails=a.emails | b.emails,
        telephones=a.telephones | b.telephones,
    )


def _enrichir(
    dossiers: Sequence[DossierIndices],
    users: Sequence[UserRollee],
    liens: Mapping[str, str],
) -> list[DossierIndices]:
    """Le dossier reçoit aussi l'e-mail et le téléphone des comptes Rollee
    déjà reliés. Le suivant peut alors matcher l'un sans l'autre."""
    par_user = {user.user_id: user for user in users}
    par_dossier = {dossier.dossier_id: dossier.empreintes for dossier in dossiers}
    for user_id, dossier_id in liens.items():
        user = par_user.get(user_id)
        if user is not None and dossier_id in par_dossier:
            par_dossier[dossier_id] = unir(par_dossier[dossier_id], user.empreintes)
    return [
        DossierIndices(dossier_id, empreinte_) for dossier_id, empreinte_ in par_dossier.items()
    ]


def _affaibli(candidat: Candidat, raison: str) -> Candidat:
    return replace(candidat, raisons=(*candidat.raisons, raison), sur=False)


def trancher(
    user: UserRollee,
    dossiers: Sequence[DossierIndices],
    retires: frozenset[tuple[str, str]] = frozenset(),
) -> Issue:
    """`retires` : paires (user, dossier) déjà déliées par le gestionnaire,
    jamais reposées seules. Un dossier qui a déjà un compte Rollee peut
    en recevoir un second si l'indice est sûr."""
    trouves = []
    for c in candidats(user, dossiers):
        if (user.user_id, c.dossier_id) in retires:
            c = _affaibli(c, RAISON_RETIRE)
        trouves.append(c)
    if not trouves:
        return Issue(user.user_id, "non_trouve")
    surs = [c for c in trouves if c.sur]
    if len(surs) == 1:
        return Issue(user.user_id, "relie_auto", surs[0].dossier_id, surs[0].indice, tuple(trouves))
    return Issue(user.user_id, "a_choisir", candidats=tuple(trouves))


def rapprocher(
    users: Sequence[UserRollee],
    dossiers: Sequence[DossierIndices],
    liens: Mapping[str, str],
    retires: frozenset[tuple[str, str]] = frozenset(),
) -> list[Issue]:
    """`liens` : user Rollee → dossier, déjà posés (créés, auto ou à la main).
    Les users déjà reliés sont ignorés. Deux users sûrs du même chauffeur
    se relient tous les deux. Le second peut s'appuyer sur le téléphone ou
    l'e-mail du premier quand le dossier n'a que l'un des deux."""
    poses = dict(liens)
    restants = [user for user in users if user.user_id not in poses]
    decides: dict[str, Issue] = {}
    progres = True
    while restants and progres:
        progres = False
        enrichis = _enrichir(dossiers, users, poses)
        encore: list[UserRollee] = []
        for user in restants:
            issue = trancher(user, enrichis, retires)
            if issue.etat == "relie_auto" and issue.dossier_id:
                poses[user.user_id] = issue.dossier_id
                decides[user.user_id] = issue
                progres = True
            else:
                encore.append(user)
        restants = encore
    enrichis = _enrichir(dossiers, users, poses)
    for user in restants:
        decides[user.user_id] = trancher(user, enrichis, retires)
    return [decides[user.user_id] for user in users if user.user_id in decides]


def bilan(issues: Iterable[Issue]) -> dict[str, int]:
    compte = Counter(i.etat for i in issues)
    return {etat: compte.get(etat, 0) for etat in ("relie_auto", "a_choisir", "non_trouve")}
