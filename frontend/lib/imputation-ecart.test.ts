import assert from "node:assert/strict";
import test from "node:test";

import { AUTRE_BANQUE, compteAEnvoyer, comptesImputation, sensEcart } from "./imputation-ecart";

test("AXE-969 : un encore dû ne propose que des charges, l'associé ou une banque", () => {
  assert.deepEqual(
    comptesImputation(200).map((c) => c.value),
    ["658", "455", AUTRE_BANQUE],
  );
  assert.ok(comptesImputation(-200).some((c) => c.value === "758"));
  assert.deepEqual(comptesImputation(0), []);
});

test("AXE-969 : le sens de l'écart en clair", () => {
  assert.equal(sensEcart(493, "uber"), "encore dus par Uber");
  assert.equal(sensEcart(-200, "uber"), "versés en trop par Uber");
});

test("AXE-969 : un autre compte bancaire doit être un 512x", () => {
  assert.equal(compteAEnvoyer("658", ""), "658");
  assert.equal(compteAEnvoyer(AUTRE_BANQUE, " 5123 "), "5123");
  assert.equal(compteAEnvoyer(AUTRE_BANQUE, "512"), null);
  assert.equal(compteAEnvoyer(AUTRE_BANQUE, "6061"), null);
});
