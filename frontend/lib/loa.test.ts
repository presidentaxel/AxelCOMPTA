import assert from "node:assert/strict";
import { test } from "node:test";

import { lireDureeMois, phraseEngagement } from "./loa";

test("la durée d'un contrat se lit en mois entiers", () => {
  assert.equal(lireDureeMois("36"), 36);
  assert.equal(lireDureeMois("3"), null);
  assert.equal(lireDureeMois("36,5"), null);
});

test("l'engagement se dit en clair", () => {
  assert.equal(phraseEngagement(0), "Contrat terminé");
  assert.match(phraseEngagement(100), /Reste à payer/u);
});
