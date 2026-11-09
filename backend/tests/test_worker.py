"""AXE-845 : le worker crée les dossiers acceptés, propose les nouveaux
contacts Digifactory et synchronise, avec un résumé pour l'écran."""

from __future__ import annotations

from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.jobs.file import TYPE_SYNCHRO, FileMemoire
from axelcompta.synchro_digifactory import ResultatDossier
from axelcompta.tenants.contacts_proposes import ContactsProposesMemoire
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.sirene import FicheSirene
from axelcompta.tenants.tags import TAG_CHAUFFEUR
from axelcompta.tenants.tags_memoire import TagsMemoire
from axelcompta.worker import Dependances, detecter_portefeuilles, executer_job, resume
from axelcompta.workflow.synchro import RapportSynchro

T = TenantId("TENANT_DEMO")
AUJOURD_HUI = date(2026, 11, 6)
CONTACTS = {
    "10": {"nr": 10, "companyName": "VTC NORD", "siren": "111111111"},
    "11": {"nr": 11, "companyName": "CONSEIL SAS", "siren": "222222222"},
    "12": {"nr": 12, "companyName": "FERMEE", "siren": "333333333"},
    "13": {"nr": 13, "companyName": "DEJA LA", "siren": "444444444"},
}
FICHES = {
    "111111111": FicheSirene("111111111", "5710", "49.32Z", "A", date(2026, 3, 13)),
    "222222222": FicheSirene("222222222", "5710", "70.22Z", "A", date(2020, 1, 1)),
    "333333333": FicheSirene("333333333", "5710", "49.32Z", "C", date(2019, 1, 1)),
}


def _deps() -> tuple[Dependances, InMemoryDossierRepository, ContactsProposesMemoire, list[int]]:
    dossiers = InMemoryDossierRepository()
    dossiers.enregistrer_tenant(Tenant(id=T, nom="Serenity"))
    dossiers.enregistrer(
        Dossier(
            id=DossierId("DIGI_13"),
            tenant_id=T,
            forme_juridique="SAS",
            regime_imposition="IS",
            regime_tva="franchise",
            nom="DEJA LA",
            tva_recettes_regime="franchise",
            exercice_debut=date(2026, 1, 1),
            contact_nr="13",
        )
    )
    contacts = ContactsProposesMemoire()
    synchros: list[int] = []

    def synchroniser(d: tuple[Dossier, ...], _s: frozenset[DossierId]) -> list[ResultatDossier]:
        synchros.append(len(d))
        rapport = RapportSynchro(5, 1, 0, 0, 0, 0, None)
        return [ResultatDossier(x.id, rapport=rapport) for x in d]

    deps = Dependances(
        dossiers=dossiers,
        contacts_proposes=contacts,
        tags=TagsMemoire(),
        lire_contacts=lambda: CONTACTS,
        lire_fiche=lambda siren: FICHES.get(siren or ""),
        synchroniser=synchroniser,
        prechauffer=len,
    )
    return deps, dossiers, contacts, synchros


def test_les_contacts_sans_dossier_sont_proposes_sans_rien_creer() -> None:
    deps, dossiers, contacts, synchros = _deps()

    resultat = executer_job(FileMemoire().demander(T, TYPE_SYNCHRO), deps, AUJOURD_HUI)

    proposes = {p.contact_nr: p for p in contacts.propositions(T)}
    assert set(proposes) == {"10", "11", "12"}  # 13 a déjà son dossier
    assert proposes["10"].avertissements == () and proposes["10"].exercice_debut == date(
        2026, 3, 13
    )
    assert "pas un chauffeur" in proposes["11"].avertissements[0]
    assert proposes["12"].cessee
    assert len(dossiers.lister_par_tenant(T)) == 1  # rien sans clic
    assert synchros == [1]
    assert resultat == "2 nouveaux chauffeurs à valider, 5 opérations reçues"


def test_un_contact_accepte_devient_un_dossier_tague_chauffeur() -> None:
    deps, dossiers, contacts, _ = _deps()
    contacts.decider(T, "10", "ajouter", "louis@exemple.fr", datetime.now(UTC))
    contacts.decider(T, "11", "ignorer", "louis@exemple.fr", datetime.now(UTC))

    resultat = executer_job(FileMemoire().demander(T, TYPE_SYNCHRO), deps, AUJOURD_HUI)

    cree = dossiers.obtenir(DossierId("DIGI_10"))
    assert cree is not None and cree.tenant_id == T
    assert (cree.forme_juridique, cree.exercice_debut) == ("SAS", date(2026, 3, 13))
    assert TAG_CHAUFFEUR in deps.tags.tags_des_dossiers(T)[cree.id]
    assert dossiers.obtenir(DossierId("DIGI_11")) is None  # ignoré
    assert {p.contact_nr for p in contacts.propositions(T)} == {"11", "12"}
    assert resultat.startswith("1 dossier créé")


def test_resume() -> None:
    erreur = ResultatDossier(DossierId("x"), erreur="401")
    assert resume(0, [], [erreur]) == "0 opération reçue, 1 dossier en erreur"


def test_le_passage_planifie_propose_les_nouveaux_contacts() -> None:
    deps, _, contacts, synchros = _deps()
    assert detecter_portefeuilles(deps, AUJOURD_HUI) == [
        "TENANT_DEMO nouveaux chauffeurs à valider : 2"
    ]
    assert len(contacts.propositions(T)) == 3
    assert synchros == []  # la détection seule ne synchronise pas
