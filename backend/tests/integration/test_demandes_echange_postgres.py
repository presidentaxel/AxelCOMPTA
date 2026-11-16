"""AXE-949 : les demandes d'échange contre un vrai Postgres, et les droits du rôle web.

L'API écrit avec le rôle `axelcompta_web`, qui ne lit pas les noms ni les
messages : ces tests le prouvent avec les mêmes appels que la route.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

import axelcompta.prospection.orm  # noqa: F401
from axelcompta.prospection.models import DemandeEchange
from axelcompta.prospection.postgres import PostgresDemandes

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent
MAINTENANT = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)


def _migrer() -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")


def _demande(id: str, email: str, cree_le: datetime = MAINTENANT) -> DemandeEchange:  # noqa: A002
    return DemandeEchange(
        id=id,
        nom="Claire Martin",
        email=email,
        organisation="Cabinet Martin",
        role="cabinet",
        message="Bonjour",
        cree_le=cree_le,
    )


@pytest.fixture
def proprietaire(engine: Engine) -> PostgresDemandes:
    _migrer()
    return PostgresDemandes(engine)


@pytest.fixture
def web(engine: Engine) -> Iterator[PostgresDemandes]:
    """Les mêmes appels, avec le rôle de l'API."""
    _migrer()
    moteur = create_engine(engine.url)

    @event.listens_for(moteur, "connect")
    def _role_web(dbapi_connexion: Any, _enregistrement: Any) -> None:
        curseur = dbapi_connexion.cursor()
        curseur.execute("SET ROLE axelcompta_web")
        curseur.close()

    yield PostgresDemandes(moteur)
    moteur.dispose()


def test_une_demande_est_enregistree_puis_relue(proprietaire: PostgresDemandes) -> None:
    proprietaire.ajouter(_demande("d1", "claire@cabinet.fr"))
    (relue,) = proprietaire.non_notifiees(MAINTENANT + timedelta(minutes=10), 3, 10)
    assert relue == _demande("d1", "claire@cabinet.fr")


def test_le_doublon_et_le_plafond_se_comptent_depuis_une_date(
    proprietaire: PostgresDemandes,
) -> None:
    proprietaire.ajouter(_demande("d1", "claire@cabinet.fr"))
    avant = MAINTENANT - timedelta(minutes=1)
    apres = MAINTENANT + timedelta(minutes=1)
    assert proprietaire.email_recu_depuis("claire@cabinet.fr", avant) is True
    assert proprietaire.email_recu_depuis("claire@cabinet.fr", apres) is False
    assert proprietaire.email_recu_depuis("autre@cabinet.fr", avant) is False
    assert proprietaire.nombre_depuis(avant) == 1
    assert proprietaire.nombre_depuis(apres) == 0


def test_une_demande_notifiee_ou_epuisee_n_est_plus_relancee(
    proprietaire: PostgresDemandes,
) -> None:
    for id_, email in (("d1", "a@x.fr"), ("d2", "b@x.fr"), ("d3", "c@x.fr")):
        proprietaire.ajouter(_demande(id_, email))
    proprietaire.marquer_notifiee("d1", MAINTENANT)
    for _ in range(3):
        proprietaire.noter_echec("d2", "Slack a répondu 500")
    plus_tard = MAINTENANT + timedelta(minutes=10)
    assert [d.id for d in proprietaire.non_notifiees(plus_tard, 3, 10)] == ["d3"]
    assert [d.id for d in proprietaire.non_notifiees(MAINTENANT, 3, 10)] == []


def test_le_role_web_fait_tout_ce_que_fait_la_route(web: PostgresDemandes) -> None:
    web.ajouter(_demande("d1", "claire@cabinet.fr"))
    assert web.email_recu_depuis("claire@cabinet.fr", MAINTENANT - timedelta(minutes=1)) is True
    assert web.nombre_depuis(MAINTENANT - timedelta(minutes=1)) == 1
    web.noter_echec("d1", "ConnectTimeout")
    web.marquer_notifiee("d1", MAINTENANT)


def test_le_role_web_ne_lit_ni_les_noms_ni_les_messages(web: PostgresDemandes) -> None:
    web.ajouter(_demande("d1", "claire@cabinet.fr"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        web.non_notifiees(MAINTENANT + timedelta(minutes=10), 3, 10)
