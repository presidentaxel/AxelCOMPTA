import assert from "node:assert/strict";
import test from "node:test";

import { estRetrait, REPONSE_NE_SAIT_PLUS, REPONSE_PERSONNELLE, suiteDeLaReponse } from "./retrait-especes";

test("un retrait se reconnaît à sa proposition", () => {
  assert.equal(estRetrait("retrait_especes"), true);
  assert.equal(estRetrait("carburant"), false);
  assert.equal(estRetrait(null), false);
});

test("la suite de chaque réponse", () => {
  assert.equal(suiteDeLaReponse(REPONSE_PERSONNELLE), null);
  assert.equal(suiteDeLaReponse(REPONSE_NE_SAIT_PLUS), "Votre comptable s'en occupe.");
  assert.match(suiteDeLaReponse("carburant") ?? "", /ticket/);
});
