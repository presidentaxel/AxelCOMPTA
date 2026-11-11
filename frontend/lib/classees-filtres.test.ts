import assert from "node:assert/strict";
import test from "node:test";

import { lireEtat } from "./classees";
import { filtresActifs, sansFiltres, versFileATraiter } from "./classees-filtres";

test("la vue, le tri et la page ne sont pas des filtres", () => {
  assert.equal(filtresActifs(lireEtat("?vue=auto&tri=confiance&page=2")), false);
  assert.equal(filtresActifs(lireEtat("?vue=auto&sens=entree")), true);
});

test("réinitialiser garde la vue et le tri, retire les filtres", () => {
  const etat = sansFiltres(lireEtat("?vue=auto&tri=confiance&origine=regle&categorie=carburant&page=3"));
  assert.equal(etat.vue, "auto");
  assert.equal(etat.tri, "confiance");
  assert.equal(etat.origine, "");
  assert.equal(etat.categorie, "");
  assert.equal(etat.page, "1");
});

test("revenir à la file à traiter", () => {
  assert.equal(versFileATraiter(lireEtat("?vue=auto&page=2")).vue, "a_traiter");
});
