"""Lectures des registres et écarts tranchés, en mémoire et en Postgres
(AXE-849). Les deux tables sont en ajout seul ; la dernière lecture et la
dernière résolution d'un champ font foi."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from axelcompta.core.errors import Introuvable
from axelcompta.core.ids import DossierId, UserId
from axelcompta.core.rls import appliquer_rls
from axelcompta.workflow.audit import ACTE_ECART_REGISTRE, noter

from .models import Dossier, EcartRegistre
from .orm import dossiers, lectures_registre, resolutions_ecart
from .registres import FicheOfficielle
from .registres_json import ecarts_vers_json, fiche_depuis_json, fiche_vers_json

MajDossier = Callable[[DossierId, Callable[[Dossier], Dossier]], None]

RETENUE_DECLAREE = "declaree"
RETENUE_OFFICIELLE = "officielle"


@dataclass(frozen=True, slots=True)
class ResolutionEcart:
    dossier_id: DossierId
    ecart: EcartRegistre
    retenue: str  # declaree | officielle
    par: UserId
    le: datetime


class RegistresRepository(Protocol):
    def enregistrer_lecture(
        self, dossier: Dossier, fiche: FicheOfficielle, ecarts: tuple[EcartRegistre, ...]
    ) -> None:
        """La lecture, et les écarts restants posés sur le dossier."""

    def derniere_lecture(
        self, dossier_id: DossierId
    ) -> tuple[FicheOfficielle, datetime] | None: ...

    def resolus(self, dossier_id: DossierId) -> dict[str, str]:
        """Par champ, la valeur du registre vue par la dernière résolution."""

    def resoudre(
        self, resolution: ResolutionEcart, restants: tuple[EcartRegistre, ...], forme: str | None
    ) -> None:
        """La résolution, les écarts restants, et la forme si celle du
        registre est retenue. Tracé au journal d'audit."""

    def poser_siren(self, dossier_id: DossierId, siren: str) -> None: ...


class RegistresMemoire:
    """Pour les tests. Écrit aussi dans le dépôt des dossiers en mémoire."""

    def __init__(self, maj_dossier: MajDossier) -> None:
        self._maj = maj_dossier
        self.lectures: list[tuple[DossierId, FicheOfficielle, datetime]] = []
        self.resolutions: list[ResolutionEcart] = []

    def enregistrer_lecture(
        self, dossier: Dossier, fiche: FicheOfficielle, ecarts: tuple[EcartRegistre, ...]
    ) -> None:
        self.lectures.append((dossier.id, fiche, datetime.now(UTC)))
        self._maj(dossier.id, lambda d: replace(d, ecarts_registre=ecarts))

    def derniere_lecture(self, dossier_id: DossierId) -> tuple[FicheOfficielle, datetime] | None:
        trouvees = [(f, le) for d, f, le in self.lectures if d == dossier_id]
        return trouvees[-1] if trouvees else None

    def resolus(self, dossier_id: DossierId) -> dict[str, str]:
        return {
            r.ecart.champ: r.ecart.officiel for r in self.resolutions if r.dossier_id == dossier_id
        }

    def resoudre(
        self, resolution: ResolutionEcart, restants: tuple[EcartRegistre, ...], forme: str | None
    ) -> None:
        self.resolutions.append(resolution)

        def appliquer(d: Dossier) -> Dossier:
            return replace(d, ecarts_registre=restants, forme_juridique=forme or d.forme_juridique)

        self._maj(resolution.dossier_id, appliquer)

    def poser_siren(self, dossier_id: DossierId, siren: str) -> None:
        self._maj(dossier_id, lambda d: replace(d, siren=siren))


class RegistresPostgres:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer_lecture(
        self, dossier: Dossier, fiche: FicheOfficielle, ecarts: tuple[EcartRegistre, ...]
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                lectures_registre.insert().values(
                    id=str(uuid.uuid4()),
                    dossier_id=dossier.id,
                    siren=fiche.siren,
                    sources=list(fiche.sources),
                    fiche=fiche_vers_json(fiche),
                    lu_le=datetime.now(UTC),
                )
            )
            connexion.execute(
                update(dossiers)
                .where(dossiers.c.id == dossier.id)
                .values(ecarts_registre=ecarts_vers_json(ecarts))
            )

    def derniere_lecture(self, dossier_id: DossierId) -> tuple[FicheOfficielle, datetime] | None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(lectures_registre.c.fiche, lectures_registre.c.lu_le)
                .where(lectures_registre.c.dossier_id == dossier_id)
                .order_by(lectures_registre.c.lu_le.desc())
                .limit(1)
            ).first()
        return None if ligne is None else (fiche_depuis_json(ligne.fiche), ligne.lu_le)

    def resolus(self, dossier_id: DossierId) -> dict[str, str]:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(resolutions_ecart.c.champ, resolutions_ecart.c.officiel)
                .where(resolutions_ecart.c.dossier_id == dossier_id)
                .order_by(resolutions_ecart.c.le)
            ).all()
        return {ligne.champ: ligne.officiel for ligne in lignes}

    def resoudre(
        self, resolution: ResolutionEcart, restants: tuple[EcartRegistre, ...], forme: str | None
    ) -> None:
        ecart = resolution.ecart
        valeurs: dict[str, object] = {"ecarts_registre": ecarts_vers_json(restants)}
        if forme is not None:
            valeurs["forme_juridique"] = forme
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                resolutions_ecart.insert().values(
                    id=str(uuid.uuid4()),
                    dossier_id=resolution.dossier_id,
                    champ=ecart.champ,
                    declare=ecart.declare,
                    officiel=ecart.officiel,
                    retenue=resolution.retenue,
                    par=resolution.par,
                    le=resolution.le,
                )
            )
            modifie = connexion.execute(
                update(dossiers).where(dossiers.c.id == resolution.dossier_id).values(**valeurs)
            ).rowcount
            if modifie != 1:
                raise Introuvable(f"Dossier introuvable : {resolution.dossier_id}.")
            reference = f"{ecart.champ}:{resolution.retenue}"
            noter(
                connexion,
                resolution.dossier_id,
                ACTE_ECART_REGISTRE,
                reference,
                resolution.par,
                resolution.le,
            )

    def poser_siren(self, dossier_id: DossierId, siren: str) -> None:
        with self._engine.begin() as connexion:
            connexion.execute(
                update(dossiers).where(dossiers.c.id == dossier_id).values(siren=siren)
            )
