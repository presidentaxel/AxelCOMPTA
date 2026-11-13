"""Implémentation Postgres de ProvisionsClotureRepository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from axelcompta.closing.immobilisations import Cession, Immobilisation
from axelcompta.closing.loa import ContratLoa
from axelcompta.closing.models import ProvisionCloture
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .orm import cessions_immobilisations, contrats_loa, immobilisations
from .orm import provisions_cloture as table
from .provisions_cloture import ImmobilisationConnue, ProvisionsClotureRepository


class PostgresProvisionsClotureRepository(ProvisionsClotureRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(
        self, tenant_id: TenantId, dossier_id: DossierId, annee: int
    ) -> tuple[ProvisionCloture, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table)
                .where(
                    table.c.tenant_id == tenant_id,
                    table.c.dossier_id == dossier_id,
                    table.c.annee == annee,
                )
                .order_by(table.c.position)
            ).all()
        return tuple(
            ProvisionCloture(
                nature=ligne.nature,
                compte_charge=ligne.compte_charge,
                centimes=ligne.centimes,
                libelle=ligne.libelle,
            )
            for ligne in lignes
        )

    def remplacer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        annee: int,
        provisions: tuple[ProvisionCloture, ...],
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                delete(table).where(
                    table.c.tenant_id == tenant_id,
                    table.c.dossier_id == dossier_id,
                    table.c.annee == annee,
                )
            )
            if not provisions:
                return
            connexion.execute(
                table.insert(),
                [
                    {
                        "tenant_id": tenant_id,
                        "dossier_id": dossier_id,
                        "annee": annee,
                        "position": position,
                        "nature": provision.nature,
                        "compte_charge": provision.compte_charge,
                        "centimes": provision.centimes,
                        "libelle": provision.libelle,
                    }
                    for position, provision in enumerate(provisions)
                ],
            )

    def lister_immobilisations(
        self, tenant_id: TenantId, dossier_id: DossierId
    ) -> tuple[Immobilisation, ...]:
        requete = (
            select(
                immobilisations, cessions_immobilisations.c.le, cessions_immobilisations.c.prix_cts
            )
            .outerjoin(
                cessions_immobilisations,
                cessions_immobilisations.c.immobilisation_id == immobilisations.c.id,
            )
            .where(immobilisations.c.tenant_id == tenant_id)
            .where(immobilisations.c.dossier_id == dossier_id)
            .order_by(immobilisations.c.mise_en_service, immobilisations.c.id)
        )
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(requete).all()
        return tuple(
            Immobilisation(
                id=ligne.id,
                designation=ligne.designation,
                compte=ligne.compte,
                mise_en_service=ligne.mise_en_service,
                base_cts=ligne.base_cts,
                duree_mois=ligne.duree_mois,
                ecriture_acquisition=ligne.ecriture_acquisition,
                cession=Cession(ligne.le, ligne.prix_cts) if ligne.le is not None else None,
            )
            for ligne in lignes
        )

    def ajouter_immobilisation(
        self, tenant_id: TenantId, dossier_id: DossierId, immobilisation: Immobilisation
    ) -> None:
        try:
            with self._engine.begin() as connexion:
                appliquer_rls(connexion)
                connexion.execute(
                    immobilisations.insert().values(
                        id=immobilisation.id,
                        tenant_id=tenant_id,
                        dossier_id=dossier_id,
                        designation=immobilisation.designation,
                        compte=immobilisation.compte,
                        mise_en_service=immobilisation.mise_en_service,
                        base_cts=immobilisation.base_cts,
                        duree_mois=immobilisation.duree_mois,
                        ecriture_acquisition=immobilisation.ecriture_acquisition,
                        cree_le=datetime.now(UTC),
                    )
                )
        except IntegrityError as erreur:
            raise ImmobilisationConnue("Ce bien est déjà au registre.") from erreur

    def enregistrer_cession(
        self, tenant_id: TenantId, dossier_id: DossierId, immobilisation_id: str, cession: Cession
    ) -> None:
        connues = {i.id for i in self.lister_immobilisations(tenant_id, dossier_id)}
        if immobilisation_id not in connues:
            raise ImmobilisationConnue("Ce bien est inconnu ou déjà cédé.")
        try:
            with self._engine.begin() as connexion:
                appliquer_rls(connexion)
                connexion.execute(
                    cessions_immobilisations.insert().values(
                        immobilisation_id=immobilisation_id,
                        dossier_id=dossier_id,
                        le=cession.le,
                        prix_cts=cession.prix_cts,
                        cree_le=datetime.now(UTC),
                    )
                )
        except IntegrityError as erreur:
            raise ImmobilisationConnue("Ce bien est inconnu ou déjà cédé.") from erreur

    def lister_contrats_loa(
        self, tenant_id: TenantId, dossier_id: DossierId
    ) -> tuple[ContratLoa, ...]:
        requete = (
            select(contrats_loa)
            .where(contrats_loa.c.tenant_id == tenant_id, contrats_loa.c.dossier_id == dossier_id)
            .order_by(contrats_loa.c.debut, contrats_loa.c.id)
        )
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(requete).all()
        return tuple(
            ContratLoa(
                id=ligne.id,
                loueur=ligne.loueur,
                vehicule=ligne.vehicule,
                debut=ligne.debut,
                duree_mois=ligne.duree_mois,
                loyer_mensuel_cts=ligne.loyer_mensuel_cts,
                premier_loyer_cts=ligne.premier_loyer_cts,
                prix_levee_cts=ligne.prix_levee_cts,
                co2_g_km=ligne.co2_g_km,
            )
            for ligne in lignes
        )

    def ajouter_contrat_loa(
        self, tenant_id: TenantId, dossier_id: DossierId, contrat: ContratLoa
    ) -> None:
        try:
            with self._engine.begin() as connexion:
                appliquer_rls(connexion)
                connexion.execute(
                    contrats_loa.insert().values(
                        id=contrat.id,
                        tenant_id=tenant_id,
                        dossier_id=dossier_id,
                        loueur=contrat.loueur,
                        vehicule=contrat.vehicule,
                        debut=contrat.debut,
                        duree_mois=contrat.duree_mois,
                        loyer_mensuel_cts=contrat.loyer_mensuel_cts,
                        premier_loyer_cts=contrat.premier_loyer_cts,
                        prix_levee_cts=contrat.prix_levee_cts,
                        co2_g_km=contrat.co2_g_km,
                        cree_le=datetime.now(UTC),
                    )
                )
        except IntegrityError as erreur:
            raise ImmobilisationConnue("Ce contrat est déjà enregistré.") from erreur
