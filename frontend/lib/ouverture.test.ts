import assert from "node:assert/strict";
import test from "node:test";

import { correspondanceJson, lireDeficits, phraseOuverture } from "./ouverture";

test("seules les correspondances remplies partent", () => {
  assert.equal(correspondanceJson({ CARBU: " 6061 ", AUTRE: "" }), '{"CARBU":"6061"}');
  assert.equal(correspondanceJson({}), "{}");
});

test("déficits : vide vaut 0, euros entiers seulement", () => {
  assert.deepEqual(lireDeficits(""), { euros: 0, message: null });
  assert.deepEqual(lireDeficits("12 500"), { euros: 12500, message: null });
  assert.equal(lireDeficits("12,50").euros, null);
  assert.equal(lireDeficits("-3").euros, null);
});

test("qui a repris le bilan", () => {
  assert.equal(phraseOuverture({ faite: false }), null);
  assert.equal(
    phraseOuverture({ faite: true, role: "expert_comptable", auteur: "Claire Expert", nom_fichier: "x.txt" }),
    "Bilan d'ouverture repris par l'expert-comptable Claire Expert (x.txt).",
  );
  assert.equal(phraseOuverture({ faite: true, role: "dirigeant" }), "Bilan d'ouverture repris par le dirigeant.");
});
