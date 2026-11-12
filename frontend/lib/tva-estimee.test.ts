import assert from "node:assert/strict";
import { test } from "node:test";

import { phraseTva } from "./tva-estimee";

const ESPACE = / | /gu;

test("une petite dépense montre la TVA estimée seule", () => {
  assert.equal(phraseTva(1000, null, -6000, true)?.replace(ESPACE, " "), "Dont TVA estimée : 10,00 €.");
});

test("une grosse dépense sans ticket invite à le joindre", () => {
  assert.match(phraseTva(5000, null, -30000, true) ?? "", /Joignez le ticket/u);
});

test("un ticket déjà joint laisse l'estimation visible", () => {
  assert.equal(phraseTva(1000, null, -30000, false)?.replace(ESPACE, " "), "Dont TVA estimée : 10,00 €.");
});

test("un montant relevé remplace l'estimation", () => {
  assert.equal(phraseTva(1000, 800, -6000, true)?.replace(ESPACE, " "), "TVA : 8,00 €.");
});

test("rien sans aucun montant", () => {
  assert.equal(phraseTva(null, null, -6000, true), null);
  assert.equal(phraseTva(0, 0, -6000, true), null);
});
