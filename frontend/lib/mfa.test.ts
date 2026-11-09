import assert from "node:assert/strict";
import test from "node:test";

import { codeNormalise, facteurVerifie } from "./mfa-code";

test("un code se lit sur six chiffres, espaces tolérés", () => {
  assert.equal(codeNormalise("123456"), "123456");
  assert.equal(codeNormalise(" 123 456 "), "123456");
  assert.equal(codeNormalise("12345"), null);
  assert.equal(codeNormalise("12345a"), null);
});

test("seul un facteur TOTP vérifié compte", () => {
  assert.equal(facteurVerifie([]), null);
  assert.equal(facteurVerifie([{ id: "a", factor_type: "totp", status: "unverified" }]), null);
  assert.equal(facteurVerifie([{ id: "b", factor_type: "totp", status: "verified" }])?.id, "b");
});
