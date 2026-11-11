"""Le modèle de catégorisation, gardé hors du poste (AXE-847).

Le 05/11, `tfidf_logreg_v2.joblib` a disparu du seul poste qui l'avait
(fichier gitignoré), sans que personne ne le voie (AXE-825). Il vit
désormais dans un bucket **privé** du stockage S3 (Supabase Storage en mode
S3, ou MinIO en local), un dossier par version :

    modeles/<version>/<version>.joblib
    modeles/<version>/<version>.joblib.sha256
    modeles/<version>/<version>.calibration.json   (si le modèle en a une)
    modeles/<version>/rapport.txt                  (si publié avec)

Au démarrage du worker, de la synchro, des tâches planifiées et de l'API,
`assurer_modele()` télécharge la version attendue (`AXELCOMPTA_MODELE_VERSION`)
si elle manque sur le poste, ou si le fichier local ne correspond plus à son
empreinte, puis vérifie l'empreinte **avant** de l'écrire. Une version
publiée ne se remplace jamais : une nouvelle version porte un nouveau nom.

Composition root, comme `nouveaux_contacts.py` : `categorize` ne fait aucun
appel réseau, il lit seulement le fichier posé ici.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from axelcompta.categorize.ml_fallback import (
    DOSSIER_MODELES,
    ModeleMlCorrompu,
    chemin_empreinte,
    chemin_modele,
    verifier_empreinte,
    version_attendue,
)
from axelcompta.categorize.modele_requis import signaler

BUCKET_PAR_DEFAUT = "modeles"
RAPPORT = "rapport.txt"


class DepotModeles(Protocol):
    """Le stockage, réduit à ce qu'il faut : lire et écrire un objet."""

    def lire(self, cle: str) -> bytes | None:
        """Le contenu, ou `None` si l'objet n'existe pas."""

    def ecrire(self, cle: str, contenu: bytes) -> None: ...


class ModeleDistantIntrouvable(RuntimeError):
    """La version demandée n'est pas dans le stockage (ou sans empreinte)."""


class VersionDejaPubliee(RuntimeError):
    """Une version publiée ne se remplace pas : choisir un nouveau nom."""


@dataclass(frozen=True, slots=True)
class Fichiers:
    """Les noms d'une version, sur le poste comme dans le stockage."""

    version: str

    @property
    def modele(self) -> str:
        return f"{self.version}.joblib"

    @property
    def empreinte(self) -> str:
        return f"{self.modele}.sha256"

    @property
    def calibration(self) -> str:
        return f"{self.version}.calibration.json"

    def cle(self, nom: str) -> str:
        return f"{self.version}/{nom}"


def _empreinte_attendue(contenu: bytes) -> str:
    return contenu.decode("utf-8").split()[0].strip().lower()


def _ecrire_atomiquement(chemin: Path, contenu: bytes) -> None:
    """Jamais de fichier à moitié écrit là où le chargeur le lirait."""
    temporaire = chemin.with_name(chemin.name + ".partiel")
    temporaire.write_bytes(contenu)
    os.replace(temporaire, chemin)


def present_et_intact(version: str, dossier: Path = DOSSIER_MODELES) -> bool:
    """Le modèle est sur le poste, avec son empreinte, et la respecte."""
    chemin = chemin_modele(version, dossier)
    if not chemin.is_file() or not chemin_empreinte(chemin).is_file():
        return False
    try:
        verifier_empreinte(chemin)
    except ModeleMlCorrompu:
        return False
    return True


def recuperer(version: str, depot: DepotModeles, dossier: Path = DOSSIER_MODELES) -> bool:
    """Télécharge la version si elle manque ou si le fichier local est
    altéré. `True` si quelque chose a été écrit. L'empreinte est vérifiée
    sur le contenu téléchargé, avant toute écriture sur le poste."""
    if present_et_intact(version, dossier):
        return False
    fichiers = Fichiers(version)
    empreinte = depot.lire(fichiers.cle(fichiers.empreinte))
    modele = depot.lire(fichiers.cle(fichiers.modele)) if empreinte is not None else None
    if empreinte is None or modele is None:
        raise ModeleDistantIntrouvable(
            f"Version {version} absente du stockage (ou sans empreinte)."
        )
    attendue = _empreinte_attendue(empreinte)
    reelle = hashlib.sha256(modele).hexdigest()
    if reelle != attendue:
        raise ModeleMlCorrompu(
            f"{fichiers.modele} téléchargé : empreinte {reelle[:12]}…, attendue {attendue[:12]}…"
        )
    dossier.mkdir(parents=True, exist_ok=True)
    calibration = depot.lire(fichiers.cle(fichiers.calibration))
    if calibration is not None:
        _ecrire_atomiquement(dossier / fichiers.calibration, calibration)
    _ecrire_atomiquement(dossier / fichiers.modele, modele)
    _ecrire_atomiquement(dossier / fichiers.empreinte, empreinte)
    return True


def a_publier(
    version: str, dossier: Path = DOSSIER_MODELES, rapport: Path | None = None
) -> dict[str, Path]:
    """Ce qui partirait dans le stockage, clé par clé. Refuse un modèle sans
    empreinte ou qui ne la respecte pas."""
    fichiers = Fichiers(version)
    chemin = chemin_modele(version, dossier)
    if not chemin.is_file() or not chemin_empreinte(chemin).is_file():
        raise ModeleDistantIntrouvable(f"{chemin} ou son empreinte .sha256 manque sur ce poste.")
    verifier_empreinte(chemin)
    envoi = {
        fichiers.cle(fichiers.modele): chemin,
        fichiers.cle(fichiers.empreinte): chemin_empreinte(chemin),
    }
    calibration = dossier / fichiers.calibration
    if calibration.is_file():
        envoi[fichiers.cle(fichiers.calibration)] = calibration
    if rapport is not None and rapport.is_file():
        envoi[fichiers.cle(RAPPORT)] = rapport
    return envoi


def publier(version: str, depot: DepotModeles, envoi: Mapping[str, Path]) -> None:
    """Envoie une version. Une version déjà publiée ne se remplace pas.
    L'empreinte part en dernier : tant qu'elle manque, `recuperer` ignore
    la version (un envoi interrompu ne se télécharge pas)."""
    fichiers = Fichiers(version)
    cle_empreinte = fichiers.cle(fichiers.empreinte)
    if depot.lire(cle_empreinte) is not None:
        raise VersionDejaPubliee(f"La version {version} est déjà publiée.")
    for cle, chemin in envoi.items():
        if cle != cle_empreinte:
            depot.ecrire(cle, chemin.read_bytes())
    depot.ecrire(cle_empreinte, envoi[cle_empreinte].read_bytes())


class DepotS3:
    """Un bucket S3 privé, par `boto3` (doc 03 : jamais le SDK Storage de
    Supabase ; Supabase Storage expose un point d'accès S3)."""

    def __init__(self, client: Any, bucket: str) -> None:
        # `Any` : boto3 n'est pas typé (pas de stubs dans les dépendances).
        self._client = client
        self._bucket = bucket

    def lire(self, cle: str) -> bytes | None:
        try:
            reponse = self._client.get_object(Bucket=self._bucket, Key=cle)
        except self._client.exceptions.NoSuchKey:
            return None
        contenu: bytes = reponse["Body"].read()
        return contenu

    def ecrire(self, cle: str, contenu: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=cle, Body=contenu)


def depot_depuis_env(environ: Mapping[str, str] | None = None) -> DepotS3 | None:
    """`None` si le stockage n'est pas configuré (poste de développement)."""
    valeurs = os.environ if environ is None else environ
    endpoint = valeurs.get("S3_ENDPOINT", "").strip()
    cle = valeurs.get("S3_ACCESS_KEY", "").strip()
    secret = valeurs.get("S3_SECRET_KEY", "").strip()
    if not (endpoint and cle and secret):
        return None
    import boto3  # import tardif : seuls les points d'entrée s'en servent

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=cle,
        aws_secret_access_key=secret,
        region_name=valeurs.get("S3_REGION", "").strip() or "eu-west-1",
    )
    return DepotS3(client, valeurs.get("MODELES_BUCKET", "").strip() or BUCKET_PAR_DEFAUT)


def assurer_modele(
    environ: Mapping[str, str] | None = None, dossier: Path = DOSSIER_MODELES
) -> None:
    """Au démarrage : récupère la version attendue si elle manque. Ne lève
    jamais. Si elle reste absente, la synchro s'arrête d'elle-même (AXE-825)."""
    version = version_attendue(environ)
    if present_et_intact(version, dossier):
        return
    depot = depot_depuis_env(environ)
    if depot is None:
        print(f"Modèle {version} absent et stockage S3 non configuré.", file=sys.stderr)
        return
    try:
        recuperer(version, depot, dossier)
    except Exception as exc:  # noqa: BLE001 — signalé, la synchro décide ensuite
        signaler(f"Modèle {version} non récupéré du stockage : {exc}")
        return
    print(f"Modèle {version} récupéré du stockage, empreinte vérifiée.", file=sys.stderr)
