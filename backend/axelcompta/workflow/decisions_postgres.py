"""Implémentation Postgres de DecisionRepository (doc 17 §9 bloc A). Seul
endroit du module qui fait de l'I/O — `decisions.py` reste pur, comme
`ledger/repository.py` vis-à-vis de `ledger/models.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine, Row

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.rls import appliquer_rls

from .audit import noter
from .decisions import AnnotationDev, ContexteDecision, DecisionHumaine, DecisionRepository
from .orm import annotations_dev, decisions_humaines


class PostgresDecisionRepository(DecisionRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer_decision(self, decision: DecisionHumaine) -> None:
        self.enregistrer_decisions([decision])

    def enregistrer_decisions(self, decisions: Sequence[DecisionHumaine]) -> None:
        """Une seule transaction : toutes les décisions et leurs lignes de
        journal d'audit, ou aucune."""
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            for decision in decisions:
                inserer_decision(connexion, decision)

    def decision_courante(
        self, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> DecisionHumaine | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            resultat = connexion.execute(
                select(decisions_humaines)
                .where(
                    decisions_humaines.c.dossier_id == dossier_id,
                    decisions_humaines.c.ecriture_id == ecriture_id,
                )
                .order_by(decisions_humaines.c.decide_le.desc())
                .limit(1)
            ).fetchone()
        return _ligne_vers_decision(resultat) if resultat is not None else None

    def lister_decisions(self, dossier_id: DossierId) -> tuple[DecisionHumaine, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            resultat = connexion.execute(
                select(decisions_humaines)
                .where(decisions_humaines.c.dossier_id == dossier_id)
                .order_by(decisions_humaines.c.decide_le)
            )
            return tuple(_ligne_vers_decision(ligne) for ligne in resultat)

    def enregistrer_annotation(self, annotation: AnnotationDev) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                annotations_dev.insert().values(
                    id=str(uuid.uuid4()),
                    dossier_id=annotation.dossier_id,
                    ecriture_id=annotation.ecriture_id,
                    juste=annotation.juste,
                    note=annotation.note,
                    annote_par=annotation.annote_par,
                    annote_le=annotation.annote_le,
                )
            )

    def lister_annotations(self, dossier_id: DossierId) -> tuple[AnnotationDev, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            resultat = connexion.execute(
                select(annotations_dev)
                .where(annotations_dev.c.dossier_id == dossier_id)
                .order_by(annotations_dev.c.annote_le)
            )
            return tuple(
                AnnotationDev(
                    dossier_id=DossierId(ligne.dossier_id),
                    ecriture_id=EcritureId(ligne.ecriture_id),
                    juste=ligne.juste,
                    note=ligne.note,
                    annote_par=UserId(ligne.annote_par),
                    annote_le=ligne.annote_le,
                )
                for ligne in resultat
            )


def inserer_decision(connexion: Connection, decision: DecisionHumaine) -> None:
    """La décision et sa ligne de journal d'audit, dans la transaction de
    l'appelant (contexte RLS déjà posé)."""
    identifiant = str(uuid.uuid4())
    connexion.execute(
        decisions_humaines.insert().values(
            id=identifiant,
            dossier_id=decision.dossier_id,
            ecriture_id=decision.ecriture_id,
            categorie=decision.categorie,
            etage_origine=decision.etage_origine.name,
            confiance_origine=decision.confiance_origine,
            decide_par=decision.decide_par,
            decide_le=decision.decide_le,
            contexte=decision.contexte.en_dict() if decision.contexte is not None else None,
        )
    )
    noter(
        connexion,
        decision.dossier_id,
        "decision",
        identifiant,
        decision.decide_par,
        decision.decide_le,
    )


def _ligne_vers_decision(ligne: Row[tuple[object, ...]]) -> DecisionHumaine:
    return DecisionHumaine(
        dossier_id=DossierId(ligne.dossier_id),
        ecriture_id=EcritureId(ligne.ecriture_id),
        categorie=ligne.categorie,
        etage_origine=Etage[ligne.etage_origine],
        confiance_origine=ligne.confiance_origine,
        decide_par=UserId(ligne.decide_par),
        decide_le=ligne.decide_le,
        contexte=ContexteDecision.depuis_dict(ligne.contexte) if ligne.contexte else None,
    )
