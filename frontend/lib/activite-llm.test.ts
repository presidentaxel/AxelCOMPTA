import assert from "node:assert/strict";
import test from "node:test";

import { resumeActiviteLlm } from "./activite-llm";

test("la ligne de l'IA dit le nombre de libellés, pas un montant", () => {
  const texte = resumeActiviteLlm({ libelles: 12 });
  assert.match(texte, /12 libellés/);
  assert.match(texte, /ni règle ni modèle/);
  assert.doesNotMatch(texte, /\$|€|budget|USD/i);
});

test("zéro et un libellé s'accordent", () => {
  assert.match(resumeActiviteLlm({ libelles: 0 }), /aucun libellé/);
  assert.match(resumeActiviteLlm({ libelles: 1 }), /1 libellé\./);
});
