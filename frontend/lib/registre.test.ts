import assert from "node:assert/strict";
import test from "node:test";

import { ecartsOrdonnes, peutRetenirRegistre, questionEcart } from "./registre";

const forme = { champ: "forme_juridique", declare: "SASU", officiel: "SAS", phrase: "…" };
const cessee = { champ: "etat", declare: "active", officiel: "cessée", phrase: "…" };

test("la société cessée passe en premier", () => {
  assert.deepEqual(
    ecartsOrdonnes([forme, cessee]).map((e) => e.champ),
    ["etat", "forme_juridique"],
  );
});

test("une société cessée ne se « retient » pas depuis l'écran", () => {
  assert.equal(peutRetenirRegistre("etat"), false);
  assert.equal(peutRetenirRegistre("forme_juridique"), true);
});

test("un champ inconnu garde son nom", () => {
  assert.equal(questionEcart("capital"), "Votre capital");
  assert.equal(questionEcart("autre"), "autre");
});
