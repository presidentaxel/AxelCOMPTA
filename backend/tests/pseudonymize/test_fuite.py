from __future__ import annotations

import pytest

from axelcompta.core.ids import DossierId
from axelcompta.pseudonymize import (
    AvisMl,
    Correspondance,
    FournisseurMemoire,
    FuiteDetectee,
    JournalPrompts,
    PartieConnue,
    PseudonymizedPrompt,
    faut_interroger_llm,
    peut_auto_valider,
    pseudonymiser,
)

DOSSIER = DossierId("d1")
PARTIES = (
    PartieConnue("Jean Martin", "personne"),
    PartieConnue("VTC Martin", "societe"),
)


def _prompt(texte: str) -> PseudonymizedPrompt:
    return pseudonymiser(DOSSIER, texte, PARTIES, Correspondance())


def test_un_libelle_brut_ne_sort_pas() -> None:
    texte = "VIR M. Jean Martin LOC VEHICULE FR76 3000 4000 5000 6000 7000 189 jean.martin@mail.fr"
    prompt = _prompt(texte)
    assert isinstance(prompt, PseudonymizedPrompt)
    assert "Jean Martin" not in prompt.texte
    assert "FR76" not in prompt.texte
    assert "jean.martin@mail.fr" not in prompt.texte
    assert "{PERSONNE_1}" in prompt.texte
    assert "{IBAN_1}" in prompt.texte
    assert "{EMAIL_1}" in prompt.texte


def test_les_jetons_sont_stables_dans_le_dossier() -> None:
    table = Correspondance()
    premier = pseudonymiser(DOSSIER, "Jean Martin paie Jean Martin", PARTIES, table)
    second = pseudonymiser(DOSSIER, "encore Jean Martin", PARTIES, table)
    assert premier.texte.count("{PERSONNE_1}") == 2
    assert "{PERSONNE_1}" in second.texte
    assert "{PERSONNE_2}" not in second.texte


def test_un_prompt_avec_iban_est_refuse() -> None:
    with pytest.raises(FuiteDetectee):
        PseudonymizedPrompt(
            dossier_id=DOSSIER,
            texte="payer FR76 3000 4000 5000 6000 7000 189",
            secrets=(),
        )


def test_le_journal_ne_garde_que_le_texte_pseudonymise() -> None:
    prompt = _prompt("Jean Martin IBAN FR76 3000 4000 5000 6000 7000 189")
    journal = JournalPrompts()
    FournisseurMemoire(journal).completer(prompt)
    assert len(journal.entrees) == 1
    assert "Jean Martin" not in journal.entrees[0].prompt
    assert "FR76" not in journal.entrees[0].prompt


def test_le_llm_ne_valide_pas_seul() -> None:
    faible = AvisMl("carburant", 0.4)
    assert faut_interroger_llm(faible)
    assert not peut_auto_valider(faible)
    assert not peut_auto_valider(None)
    assert peut_auto_valider(AvisMl("peage_stationnement", 0.95))
