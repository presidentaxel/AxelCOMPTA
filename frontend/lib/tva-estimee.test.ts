import assert from "node:assert/strict";
import { test } from "node:test";

import { phraseTvaEstimee } from "./tva-estimee";

const ESPACE = / | /gu;

test("une petite dépense montre la TVA estimée seule", () => {
  assert.equal(phraseTvaEstimee(1000, -6000, false)?.replace(ESPACE, " "), "Dont TVA estimée : 10,00 €.");
});

test("une grosse dépense invite à joindre le ticket", () => {
  assert.match(phraseTvaEstimee(5000, -30000, false) ?? "", /Joignez le ticket/u);
});

test("rien sans TVA estimée ou avec un ticket joint", () => {
  assert.equal(phraseTvaEstimee(null, -6000, false), null);
  assert.equal(phraseTvaEstimee(0, -6000, false), null);
  assert.equal(phraseTvaEstimee(1000, -6000, true), null);
});
