import assert from "node:assert/strict";
import test from "node:test";

import { lireMontantEuros } from "./montant";

test("une saisie vide est refusée", () => {
  assert.deepEqual(lireMontantEuros(""), {
    centimes: null,
    message: "Indiquez un montant.",
  });
  assert.equal(lireMontantEuros("   ").centimes, null);
  assert.equal(lireMontantEuros("\u00a0").centimes, null);
});

test("la virgule et les espaces insécables sont acceptés", () => {
  assert.equal(lireMontantEuros("1 000,50").centimes, 100_050);
  assert.equal(lireMontantEuros("1\u00a0000,50").centimes, 100_050);
  assert.equal(lireMontantEuros("1\u202f000,50").centimes, 100_050);
  assert.equal(lireMontantEuros("1000,5").centimes, 100_050);
  assert.equal(lireMontantEuros("0").centimes, 0);
});

test("un montant illisible est refusé", () => {
  assert.equal(lireMontantEuros("1,234").centimes, null);
  assert.equal(lireMontantEuros("1.000,50").centimes, null);
  assert.equal(lireMontantEuros("abc").message, "Écrivez le montant comme 1 000,50.");
  assert.equal(lireMontantEuros("-1").centimes, null);
});
