import assert from "node:assert/strict";
import { test } from "node:test";

import { dureeEnClair, lireDureeAnnees, phraseCession } from "./immobilisations";

test("la durée se dit en années quand elle tombe juste", () => {
  assert.equal(dureeEnClair(60), "5 ans");
  assert.equal(dureeEnClair(12), "1 an");
  assert.equal(dureeEnClair(18), "18 mois");
});

test("la durée saisie en années est bornée", () => {
  assert.equal(lireDureeAnnees("5"), 60);
  assert.equal(lireDureeAnnees("1,5"), 18);
  assert.equal(lireDureeAnnees("0"), null);
  assert.equal(lireDureeAnnees("abc"), null);
});

test("la cession dit plus ou moins-value", () => {
  assert.equal(phraseCession(null), null);
  assert.equal(phraseCession(150000), "Plus-value à la vente");
  assert.equal(phraseCession(-100), "Moins-value à la vente");
});
