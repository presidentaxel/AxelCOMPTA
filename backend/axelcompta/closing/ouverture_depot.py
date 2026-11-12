"""Bilan d'ouverture repris d'un FEC : écriture d'à-nouveaux, trace de
l'import et déficits du dossier, tout ou rien (AXE-804)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from axelcompta.core.errors import Conflit
from axelcompta.core.ids import DossierId, UserId
from axelcompta.core.rls import appliquer_rls
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import inserer_ecriture
from axelcompta.ledger.service import LedgerService
from axelcompta.tenants.orm import dossiers, ouvertures_importees
from axelcompta.tenants.repository import DossierRepository
from axelcompta.workflow.audit import ACTE_OUVERTURE_FEC, noter

ROLE_DIRIGEANT = "dirigeant"
ROLE_EXPERT = "expert_comptable"


class OuvertureDejaFaite(Conflit):
    """L'ouverture est verrouillée : une correction passe par une OD."""

    def __init__(self) -> None:
        super().__init__(
            "Le bilan d'ouverture de ce dossier est déjà repris. "
            "Une correction passe par une écriture d'opérations diverses."
        )


@dataclass(frozen=True, slots=True)
class OuvertureImportee:
    dossier_id: DossierId
    nom_fichier: str
    empreinte: str
    cloture: date
    ouverture: date
    role: str  # dirigeant | expert_comptable
    par: UserId
    auteur_nom: str | None
    motif: str | None
    attestation: str
    correspondance: dict[str, str]
    deficits_euros: int
    ecriture_id: str
    le: datetime


class OuverturesRepository(Protocol):
    def importer(self, ouverture: OuvertureImportee, a_nouveaux: Ecriture) -> None:
        """Lève `OuvertureDejaFaite` si le dossier a déjà son ouverture."""

    def obtenir(self, dossier_id: DossierId) -> OuvertureImportee | None: ...


class OuverturesMemoire:
    """Pour les tests : écrit l'à-nouveaux dans le ledger en mémoire."""

    def __init__(self, ledger: LedgerService, dossiers: DossierRepository) -> None:
        self._ledger = ledger
        self._dossiers = dossiers
        self.ouvertures: dict[DossierId, OuvertureImportee] = {}

    def importer(self, ouverture: OuvertureImportee, a_nouveaux: Ecriture) -> None:
        deja = any(e.id == a_nouveaux.id for e in self._ledger.grand_livre(ouverture.dossier_id))
        if ouverture.dossier_id in self.ouvertures or deja:
            raise OuvertureDejaFaite
        self._ledger.enregistrer(a_nouveaux)
        self.ouvertures[ouverture.dossier_id] = ouverture
        dossier = self._dossiers.obtenir(ouverture.dossier_id)
        if dossier is not None:
            self._dossiers.reconfigurer_depuis_sirene(
                replace(dossier, deficits_anterieurs_euros=ouverture.deficits_euros)
            )

    def obtenir(self, dossier_id: DossierId) -> OuvertureImportee | None:
        return self.ouvertures.get(dossier_id)


class OuverturesPostgres:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def importer(self, ouverture: OuvertureImportee, a_nouveaux: Ecriture) -> None:
        try:
            with self._engine.begin() as connexion:
                appliquer_rls(connexion)
                connexion.execute(
                    ouvertures_importees.insert().values(
                        id=str(uuid.uuid4()),
                        dossier_id=ouverture.dossier_id,
                        nom_fichier=ouverture.nom_fichier,
                        empreinte=ouverture.empreinte,
                        cloture=ouverture.cloture,
                        ouverture=ouverture.ouverture,
                        role=ouverture.role,
                        par=ouverture.par,
                        auteur_nom=ouverture.auteur_nom,
                        motif=ouverture.motif,
                        attestation=ouverture.attestation,
                        correspondance=ouverture.correspondance,
                        deficits_euros=ouverture.deficits_euros,
                        ecriture_id=ouverture.ecriture_id,
                        le=ouverture.le,
                    )
                )
                inserer_ecriture(connexion, a_nouveaux)
                connexion.execute(
                    update(dossiers)
                    .where(dossiers.c.id == ouverture.dossier_id)
                    .values(deficits_anterieurs_euros=ouverture.deficits_euros)
                )
                reference = f"{ouverture.nom_fichier}:{ouverture.empreinte[:16]}"
                noter(
                    connexion,
                    ouverture.dossier_id,
                    ACTE_OUVERTURE_FEC,
                    reference,
                    ouverture.par,
                    ouverture.le,
                )
        except IntegrityError as erreur:  # une ouverture ou un AN déjà là
            raise OuvertureDejaFaite from erreur

    def obtenir(self, dossier_id: DossierId) -> OuvertureImportee | None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(ouvertures_importees).where(ouvertures_importees.c.dossier_id == dossier_id)
            ).first()
        if ligne is None:
            return None
        return OuvertureImportee(
            dossier_id=DossierId(ligne.dossier_id),
            nom_fichier=ligne.nom_fichier,
            empreinte=ligne.empreinte,
            cloture=ligne.cloture,
            ouverture=ligne.ouverture,
            role=ligne.role,
            par=UserId(ligne.par),
            auteur_nom=ligne.auteur_nom,
            motif=ligne.motif,
            attestation=ligne.attestation,
            correspondance=dict(ligne.correspondance or {}),
            deficits_euros=int(ligne.deficits_euros),
            ecriture_id=ligne.ecriture_id,
            le=ligne.le,
        )
