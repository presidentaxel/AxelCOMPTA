"""AXE-888 : Claude derrière LLMProvider, sans appel réseau (client factice)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from axelcompta.core.ids import DossierId
from axelcompta.pseudonymize.fournisseur_anthropic import (
    BudgetDepasse,
    FournisseurAnthropic,
    ReponseInutilisable,
    WorkspaceRequis,
    cout,
    entetes_anthropic,
    modele_configure,
)
from axelcompta.pseudonymize.llm import JournalPrompts
from axelcompta.pseudonymize.prompt import PseudonymizedPrompt

PROMPT = PseudonymizedPrompt(DossierId("d1"), "Classe : CB TOTAL", ())


class ClientFactice:
    def __init__(self, stop_reason: str = "end_turn", sortie: int = 1_000) -> None:
        self.appels: list[dict[str, Any]] = []
        self._stop_reason = stop_reason
        self._sortie = sortie

    def create(self, **kwargs: Any) -> Any:
        self.appels.append(kwargs)
        return SimpleNamespace(
            stop_reason=self._stop_reason,
            usage=SimpleNamespace(
                input_tokens=2_000,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
                output_tokens=self._sortie,
            ),
            content=[
                SimpleNamespace(type="thinking"),
                SimpleNamespace(type="text", text='{"propositions": []}'),
            ],
        )


def test_un_appel_part_pseudonymise_avec_schema_effort_bas_et_repli() -> None:
    client, journal = ClientFactice(), JournalPrompts()
    fournisseur = FournisseurAnthropic({"type": "object"}, journal, 1.0, messages=client)
    assert fournisseur.completer(PROMPT) == '{"propositions": []}'
    (appel,) = client.appels
    assert appel["model"] == "claude-fable-5-2"
    assert appel["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": {"type": "object"}},
    }
    assert appel["fallbacks"] == "default"
    assert appel["messages"] == [{"role": "user", "content": "Classe : CB TOTAL"}]
    assert [e.prompt for e in journal.entrees] == ["Classe : CB TOTAL"]
    assert fournisseur.depense_usd == pytest.approx(cout("claude-fable-5-2", 2_000, 1_000))


def test_le_cout_suit_le_prix_de_fable() -> None:
    assert cout("claude-fable-5-2", 1_000_000, 1_000_000) == pytest.approx(48.0)
    assert cout("modele-inconnu", 1_000_000, 0) == pytest.approx(8.0)  # surestimé, jamais l'inverse


def test_au_dela_du_plafond_plus_aucun_appel() -> None:
    client = ClientFactice(sortie=100_000)  # 4 $ de sortie
    fournisseur = FournisseurAnthropic({}, JournalPrompts(), 1.0, messages=client)
    fournisseur.completer(PROMPT)
    with pytest.raises(BudgetDepasse):
        fournisseur.completer(PROMPT)
    assert len(client.appels) == 1


@pytest.mark.parametrize("raison", ["refusal", "max_tokens"])
def test_un_refus_ou_une_reponse_coupee_reste_a_l_humain(raison: str) -> None:
    fournisseur = FournisseurAnthropic({}, JournalPrompts(), 1.0, messages=ClientFactice(raison))
    with pytest.raises(ReponseInutilisable):
        fournisseur.completer(PROMPT)


def test_le_modele_vient_de_l_environnement_sauf_si_on_le_precise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    assert modele_configure(None) == "claude-fable-5-2"
    monkeypatch.setenv("ANTHROPIC_MODEL", " claude-haiku-5-5 ")
    assert modele_configure(None) == "claude-haiku-5-5"
    assert modele_configure("claude-sonnet-5-5") == "claude-sonnet-5-5"


def test_le_workspace_part_en_en_tete_quand_il_est_defini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    assert entetes_anthropic() == {}
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", " wrkspc_axe ")
    assert entetes_anthropic() == {"anthropic-workspace-id": "wrkspc_axe"}


def test_une_cle_sans_workspace_dit_quelle_variable_manque() -> None:
    class ClientSansWorkspace:
        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError(
                "This API key is not scoped to a workspace, so this request must include "
                "the anthropic-workspace-id header"
            )

    fournisseur = FournisseurAnthropic({}, JournalPrompts(), 1.0, messages=ClientSansWorkspace())
    with pytest.raises(WorkspaceRequis, match="ANTHROPIC_WORKSPACE_ID"):
        fournisseur.completer(PROMPT)
