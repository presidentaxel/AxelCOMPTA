import assert from "node:assert/strict";
import test from "node:test";

import {
  changer,
  formatConfiance,
  lireEtat,
  phraseCompteurs,
  versApi,
  versRecherche,
  VUE_A_TRAITER,
} from "./classees";

test("l'état se lit dans l'URL, avec des défauts", () => {
  const etat = lireEtat("?vue=auto&origine=regle&categorie=carburant");
  assert.equal(etat.vue, "auto");
  assert.equal(etat.origine, "regle");
  assert.equal(etat.tri, "recentes");
  assert.equal(lireEtat("?vue=inventee").vue, VUE_A_TRAITER);
  assert.equal(lireEtat("").page, "1");
});

test("changer un filtre ramène à la première page", () => {
  const etat = changer(lireEtat("?vue=auto&page=3"), "origine", "regle");
  assert.equal(etat.page, "1");
  assert.equal(changer(etat, "page", "2").page, "2");
});

test("l'URL ne garde que ce qui diffère du défaut", () => {
  assert.equal(versRecherche(lireEtat("")), "");
  assert.equal(versRecherche(lireEtat("?vue=auto&tri=confiance")), "?vue=auto&tri=confiance");
});

test("paramètres de l'API", () => {
  assert.equal(versApi(lireEtat("?vue=auto&origine=regle")).toString(), "statut=auto&origine=regle&tri=recentes&page=1");
  assert.equal(versApi(lireEtat("?vue=toutes")).get("statut"), null);
});

test("affichages", () => {
  assert.equal(formatConfiance(0.5), "0,50");
  assert.equal(formatConfiance(null), "—");
  assert.equal(
    phraseCompteurs({ auto: 140, justes: 12, fausses: 3 }),
    "140 classées automatiquement, 12 validées justes, 3 marquées fausses",
  );
});
