"""Les rappels partent par l'e-mail ou le SMS du gestionnaire (AXE-808).

Décision du 26/09 : AxeLCompta n'a pas de SMTP. L'e-mail et le SMS sont des
**intégrations du gestionnaire** : il branche son SMTP (ou un fournisseur de
SMS par HTTP), ses identifiants sont chiffrés (`core.chiffrement`).

Chaque rappel déclenché crée un **envoi** par canal branché. Le worker les
envoie : trois essais, puis « échec » avec la raison, sans bloquer les
autres. Le contenu ne porte jamais de montant ni de libellé (doc 19) :
le nombre d'opérations qui attendent et un lien vers l'espace chauffeur.
Chaque message porte un lien de désinscription, respecté à l'envoi.
"""

from __future__ import annotations

import json
import smtplib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from email.message import EmailMessage
from typing import Literal, Protocol

import httpx

from axelcompta.core.chiffrement import chiffrer, dechiffrer, signature_valide, signer
from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, TenantId

Canal = Literal["mail", "sms"]
CANAUX_ENVOI: tuple[Canal, ...] = ("mail", "sms")
FOURNISSEURS = {"mail": ("smtp",), "sms": ("http",)}
TENTATIVES_MAX = 3
DELAI_RESEAU_S = 15.0
_CHAMPS = {
    "smtp": ("hote", "port", "utilisateur", "mot_de_passe", "expediteur"),
    "http": ("url", "cle_api", "expediteur"),
}


class IntegrationInvalide(SaisieInvalide):
    """Fournisseur inconnu pour ce canal, ou champ manquant."""


@dataclass(frozen=True, slots=True)
class Integration:
    tenant_id: TenantId
    canal: Canal
    fournisseur: str
    parametres_chiffres: str  # JSON des paramètres, chiffré


@dataclass(frozen=True, slots=True)
class EnvoiRappel:
    id: str
    rappel_id: str
    tenant_id: TenantId
    dossier_id: DossierId
    canal: Canal
    message: str  # celui de la règle, au déclenchement
    statut: str  # en_attente | envoye | echec | ignore
    tentatives: int = 0
    raison: str | None = None
    maj_le: datetime | None = None


class Expediteur(Protocol):
    def envoyer(self, destinataire: str, sujet: str, texte: str) -> None:
        """Lève une exception si le fournisseur refuse ou ne répond pas."""
        ...


def preparer_integration(
    tenant_id: TenantId, canal: str, fournisseur: str, parametres: dict[str, str]
) -> Integration:
    """Vérifie les champs et chiffre les paramètres. Lève `IntegrationInvalide`."""
    if canal not in CANAUX_ENVOI or fournisseur not in FOURNISSEURS[canal]:
        raise IntegrationInvalide(f"Fournisseur « {fournisseur} » inconnu pour {canal}.")
    manquants = [c for c in _CHAMPS[fournisseur] if not str(parametres.get(c, "")).strip()]
    if manquants:
        raise IntegrationInvalide(f"Champs manquants : {', '.join(manquants)}.")
    utiles = {c: str(parametres[c]).strip() for c in _CHAMPS[fournisseur]}
    return Integration(
        tenant_id, "mail" if canal == "mail" else "sms", fournisseur, chiffrer(json.dumps(utiles))
    )


class ExpediteurSmtp:
    """SMTP du gestionnaire, STARTTLS sur le port 587 (TLS direct sur 465)."""

    def __init__(self, parametres: dict[str, str]) -> None:
        self._p = parametres

    def envoyer(self, destinataire: str, sujet: str, texte: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = (
            self._p["expediteur"],
            destinataire,
            sujet,
        )
        message.set_content(texte)
        port = int(self._p["port"])
        classe = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with classe(self._p["hote"], port, timeout=DELAI_RESEAU_S) as serveur:
            if port != 465:
                serveur.starttls()
            serveur.login(self._p["utilisateur"], self._p["mot_de_passe"])
            serveur.send_message(message)


class ExpediteurSmsHttp:
    """Fournisseur de SMS par HTTP : POST JSON {from, to, text}, clé en Bearer."""

    def __init__(self, parametres: dict[str, str]) -> None:
        self._p = parametres

    def envoyer(self, destinataire: str, sujet: str, texte: str) -> None:
        reponse = httpx.post(
            self._p["url"],
            json={"from": self._p["expediteur"], "to": destinataire, "text": texte},
            headers={"Authorization": f"Bearer {self._p['cle_api']}"},
            timeout=DELAI_RESEAU_S,
        )
        reponse.raise_for_status()


def expediteur_de(integration: Integration) -> Expediteur:
    parametres: dict[str, str] = json.loads(dechiffrer(integration.parametres_chiffres))
    if integration.fournisseur == "smtp":
        return ExpediteurSmtp(parametres)
    return ExpediteurSmsHttp(parametres)


def lien_desinscription(base_url: str, dossier_id: DossierId, canal: str) -> str:
    message = f"{dossier_id}|{canal}"
    return f"{base_url}/desinscription?d={dossier_id}&c={canal}&j={signer(message)}"


def desinscription_valide(dossier_id: str, canal: str, jeton: str) -> bool:
    return signature_valide(f"{dossier_id}|{canal}", jeton)


def contenu(
    message_regle: str, nb_a_traiter: int, lien_espace: str, lien_stop: str, canal: Canal
) -> tuple[str, str]:
    """(sujet, texte). Jamais de montant ni de libellé d'opération (doc 19)."""
    attente = (
        ""
        if nb_a_traiter == 0
        else (
            "1 opération vous attend."
            if nb_a_traiter == 1
            else f"{nb_a_traiter} opérations vous attendent."
        )
    )
    corps = " ".join(p for p in (message_regle.strip(), attente) if p)
    if canal == "sms":
        return "", f"{corps} {lien_espace} — STOP : {lien_stop}"
    texte = (
        f"{corps}\n\nOuvrir votre espace : {lien_espace}\n\n"
        f"Ne plus recevoir ces rappels par e-mail : {lien_stop}\n"
    )
    return "Votre comptabilité vous attend", texte


def apres_essai(envoi: EnvoiRappel, erreur: str | None, maintenant: datetime) -> EnvoiRappel:
    """L'envoi après un essai : envoyé, ou un essai de plus ; au troisième,
    « échec » avec la raison."""
    if erreur is None:
        return replace(envoi, statut="envoye", tentatives=envoi.tentatives + 1, maj_le=maintenant)
    tentatives = envoi.tentatives + 1
    statut = "echec" if tentatives >= TENTATIVES_MAX else "en_attente"
    return replace(
        envoi, statut=statut, tentatives=tentatives, raison=erreur[:200], maj_le=maintenant
    )


def ignore(envoi: EnvoiRappel, raison: str, maintenant: datetime) -> EnvoiRappel:
    return replace(envoi, statut="ignore", raison=raison, maj_le=maintenant)


class EnvoisRepository(Protocol):
    def integration(self, tenant_id: TenantId, canal: str) -> Integration | None: ...

    def canaux_branches(self, tenant_id: TenantId) -> dict[str, datetime]:
        """Canal branché → date du dernier réglage. Rien de secret."""
        ...

    def brancher(self, integration: Integration, par: str, le: datetime) -> None: ...

    def creer(self, envois: Sequence[EnvoiRappel]) -> None: ...

    def en_attente(self, limite: int) -> list[EnvoiRappel]:
        """Tous portefeuilles (worker, rôle propriétaire)."""
        ...

    def enregistrer(self, envoi: EnvoiRappel) -> None:
        """Statut, essais et raison après un essai."""
        ...

    def desinscrits(self, dossier_ids: Sequence[DossierId]) -> set[tuple[str, str]]: ...

    def desinscrire(self, dossier_id: DossierId, canal: str) -> None: ...

    def du_dossier(self, dossier_id: DossierId, limite: int) -> list[EnvoiRappel]: ...


@dataclass
class EnvoisMemoire:
    integrations: dict[tuple[str, str], Integration] = field(default_factory=dict)
    envois: dict[str, EnvoiRappel] = field(default_factory=dict)
    stop: set[tuple[str, str]] = field(default_factory=set)

    def integration(self, tenant_id: TenantId, canal: str) -> Integration | None:
        return self.integrations.get((tenant_id, canal))

    def canaux_branches(self, tenant_id: TenantId) -> dict[str, datetime]:
        return {c: datetime.min for (t, c) in self.integrations if t == tenant_id}

    def brancher(self, integration: Integration, par: str, le: datetime) -> None:
        self.integrations[(integration.tenant_id, integration.canal)] = integration

    def creer(self, envois: Sequence[EnvoiRappel]) -> None:
        for envoi in envois:
            self.envois[envoi.id] = envoi

    def en_attente(self, limite: int) -> list[EnvoiRappel]:
        return [e for e in self.envois.values() if e.statut == "en_attente"][:limite]

    def enregistrer(self, envoi: EnvoiRappel) -> None:
        self.envois[envoi.id] = envoi

    def desinscrits(self, dossier_ids: Sequence[DossierId]) -> set[tuple[str, str]]:
        voulus = set(dossier_ids)
        return {(d, c) for d, c in self.stop if d in voulus}

    def desinscrire(self, dossier_id: DossierId, canal: str) -> None:
        self.stop.add((dossier_id, canal))

    def du_dossier(self, dossier_id: DossierId, limite: int) -> list[EnvoiRappel]:
        return [e for e in self.envois.values() if e.dossier_id == dossier_id][:limite]


@dataclass(frozen=True, slots=True)
class Contexte:
    """Ce que le worker sait de chaque dossier au moment d'envoyer."""

    destinataire: Callable[[DossierId, str], str | None]  # e-mail ou numéro, ou None
    nb_a_traiter: Callable[[DossierId], int]
    base_url: str


def envoyer_en_attente(
    depot: EnvoisRepository,
    contexte: Contexte,
    expediteur: Callable[[Integration], Expediteur],
    maintenant: datetime,
    limite: int = 500,
) -> dict[str, int]:
    """Une passe : chaque envoi en attente est tenté une fois. Un fournisseur
    en panne n'arrête pas les autres envois."""
    bilan = {"envoye": 0, "echec": 0, "en_attente": 0, "ignore": 0}
    attente = depot.en_attente(limite)
    stop = depot.desinscrits(sorted({e.dossier_id for e in attente}))
    for envoi in attente:
        suite = _un_envoi(envoi, depot, contexte, expediteur, stop, maintenant)
        depot.enregistrer(suite)
        bilan[suite.statut] = bilan.get(suite.statut, 0) + 1
    return bilan


def _un_envoi(
    envoi: EnvoiRappel,
    depot: EnvoisRepository,
    contexte: Contexte,
    expediteur: Callable[[Integration], Expediteur],
    stop: set[tuple[str, str]],
    maintenant: datetime,
) -> EnvoiRappel:
    if (envoi.dossier_id, envoi.canal) in stop:
        return ignore(envoi, "désinscrit", maintenant)
    integration = depot.integration(envoi.tenant_id, envoi.canal)
    if integration is None:
        return ignore(envoi, "intégration retirée", maintenant)
    destinataire = contexte.destinataire(envoi.dossier_id, envoi.canal)
    if not destinataire:
        quoi = "e-mail" if envoi.canal == "mail" else "numéro de téléphone"
        return ignore(envoi, f"{quoi} du chauffeur inconnu", maintenant)
    sujet, texte = contenu(
        envoi.message,
        contexte.nb_a_traiter(envoi.dossier_id),
        f"{contexte.base_url}/chauffeur/{envoi.dossier_id}",
        lien_desinscription(contexte.base_url, envoi.dossier_id, envoi.canal),
        envoi.canal,
    )
    try:
        expediteur(integration).envoyer(destinataire, sujet, texte)
    except Exception as exc:  # noqa: BLE001 — l'erreur devient la raison affichée
        return apres_essai(envoi, f"{type(exc).__name__} : {exc}", maintenant)
    return apres_essai(envoi, None, maintenant)


def envois_du_rappel(
    rappel_id: str,
    tenant_id: TenantId,
    dossier_id: DossierId,
    message: str,
    canaux: Sequence[str],
    branches: Sequence[str],
    maintenant: datetime,
) -> list[EnvoiRappel]:
    """Un envoi par canal de la règle qui est branché (l'appel reste à faire)."""
    return [
        EnvoiRappel(
            id=f"{rappel_id}:{canal}",
            rappel_id=rappel_id,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            canal="mail" if canal == "mail" else "sms",
            message=message,
            statut="en_attente",
            maj_le=maintenant,
        )
        for canal in dict.fromkeys(canaux)
        if canal in CANAUX_ENVOI and canal in branches
    ]
