import assert from "node:assert/strict";
import test from "node:test";

import { tonMontant } from "./ton-montant";

test("un montant négatif est toujours rouge", () => {
  assert.equal(tonMontant(-1, "signe"), "negatif");
  assert.equal(tonMontant(-1, "neutre"), "negatif");
});

test("un montant positif n'est vert que dans une liste d'opérations", () => {
  assert.equal(tonMontant(100, "signe"), "positif");
  assert.equal(tonMontant(100, "neutre"), "neutre");
});

test("zéro n'est jamais coloré", () => {
  assert.equal(tonMontant(0, "signe"), "neutre");
  assert.equal(tonMontant(0, "neutre"), "neutre");
});
