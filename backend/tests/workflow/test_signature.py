from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from axelcompta.core.ids import DossierId, UserId
from axelcompta.workflow.signature_demo import SignatureDemoProvider
from axelcompta.workflow.signature_memory import InMemorySignatureRepository

DOSSIER = DossierId("d1")
GESTIONNAIRE = UserId("gestionnaire_demo")


def _pdf_factice() -> bytes:
    tampon = io.BytesIO()
    dessin = canvas.Canvas(tampon, pagesize=A4)
    dessin.drawString(50, 800, "Document de test")
    dessin.save()
    return tampon.getvalue()


def test_signature_demo_produit_un_pdf_valide_non_qualifie() -> None:
    """doc 20 §4 : jamais une vraie signature qualifiée RGS en démo —
    `qualifie` doit rester explicitement False."""
    resultat = SignatureDemoProvider().signer(_pdf_factice(), GESTIONNAIRE)
    assert resultat.contenu_pdf.startswith(b"%PDF-")
    assert resultat.qualifie is False
    assert resultat.provider == "demo"
    assert resultat.signataire == GESTIONNAIRE


def test_signature_demo_produit_un_pdf_different_de_loriginal() -> None:
    """Le tampon doit réellement être appliqué, pas juste un pass-through."""
    original = _pdf_factice()
    resultat = SignatureDemoProvider().signer(original, GESTIONNAIRE)
    assert resultat.contenu_pdf != original
    assert len(resultat.contenu_pdf) > len(original)


def test_repository_memoire_absent_tant_que_rien_nest_signe() -> None:
    repo = InMemorySignatureRepository()
    assert repo.dernier(DOSSIER, "greffe_inpi") is None
    assert repo.lister(DOSSIER, "greffe_inpi") == ()


def test_repository_memoire_enregistre_puis_retourne_le_document() -> None:
    repo = InMemorySignatureRepository()
    document = SignatureDemoProvider().signer(_pdf_factice(), GESTIONNAIRE)
    repo.enregistrer(DOSSIER, "greffe_inpi", document)
    assert repo.dernier(DOSSIER, "greffe_inpi") == document


def test_repository_memoire_nouvelle_signature_devient_derniere_sans_effacer_historique() -> None:
    """Append-only depuis le 2026-09-11 (preuve légale, doc 20 §4bis) —
    même principe que DecisionRepository : `dernier` reflète la plus
    récente, `lister` garde tout, rien n'est jamais écrasé."""
    repo = InMemorySignatureRepository()
    provider = SignatureDemoProvider()
    premiere = provider.signer(_pdf_factice(), GESTIONNAIRE)
    repo.enregistrer(DOSSIER, "greffe_inpi", premiere)

    seconde = provider.signer(_pdf_factice(), UserId("gestionnaire_autre"))
    repo.enregistrer(DOSSIER, "greffe_inpi", seconde)

    assert repo.dernier(DOSSIER, "greffe_inpi") == seconde
    assert repo.lister(DOSSIER, "greffe_inpi") == (premiere, seconde)


def test_repository_memoire_isole_par_dossier() -> None:
    repo = InMemorySignatureRepository()
    autre_dossier = DossierId("d2")
    document = SignatureDemoProvider().signer(_pdf_factice(), GESTIONNAIRE)
    repo.enregistrer(DOSSIER, "greffe_inpi", document)

    assert repo.dernier(autre_dossier, "greffe_inpi") is None


def test_repository_memoire_isole_par_type_document() -> None:
    """Le même dossier pourra avoir plusieurs types de documents signés
    (greffe/INPI aujourd'hui, d'autres en V1) — pas de collision de clé."""
    repo = InMemorySignatureRepository()
    document = SignatureDemoProvider().signer(_pdf_factice(), GESTIONNAIRE)
    repo.enregistrer(DOSSIER, "greffe_inpi", document)

    assert repo.dernier(DOSSIER, "autre_type_document") is None


def test_types_presents_regroupe_un_portefeuille_et_ignore_les_autres_types() -> None:
    repo = InMemorySignatureRepository()
    autre = DossierId("d2")
    document = SignatureDemoProvider().signer(_pdf_factice(), GESTIONNAIRE)
    repo.enregistrer(DOSSIER, "cloture", document)
    repo.enregistrer(DOSSIER, "cloture", document)  # un historique ne compte qu'une fois
    repo.enregistrer(DOSSIER, "hors_frise", document)

    presents = repo.types_presents([DOSSIER, autre], ["cloture", "greffe_inpi"])

    assert presents == {DOSSIER: {"cloture"}, autre: set()}
