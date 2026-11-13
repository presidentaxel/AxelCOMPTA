import assert from "node:assert/strict";
import test from "node:test";

import { resumeBudgetLlm } from "./budget-llm";

test("la ligne de l'IA dit la dépense du mois et le budget", () => {
  const texte = resumeBudgetLlm({ depense_usd: 1.2, plafond_usd: 5 });
  assert.match(texte, /1,20/);
  assert.match(texte, /5,00/);
  assert.match(texte, /ni règle ni modèle/);
});
