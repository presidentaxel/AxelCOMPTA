import assert from "node:assert/strict";
import test from "node:test";

import {
  etapeBloquante,
  etapePasEncorePassee,
  impotsNonDeclares,
  rangEtape,
} from "./filtres-portefeuille";

test("rang d'étape : compte ouvert, suivi et signé", () => {
  assert.equal(rangEtape("Compte", false), -1);
  assert.equal(rangEtape("Compte", true), 0);
  assert.equal(rangEtape("Suivi", false), 0);
  assert.equal(rangEtape("Signé", false), 3);
  assert.equal(rangEtape("Impôts", false), 4);
});

test("étape pas encore passée", () => {
  assert.equal(etapePasEncorePassee("Sans exercice", false, "Clôture"), false);
  assert.equal(etapePasEncorePassee("Compte", false, "Clôture"), true);
  assert.equal(etapePasEncorePassee("Clôture", true, "Clôture"), true);
  assert.equal(etapePasEncorePassee("Greffe", true, "Clôture"), false);
  assert.equal(etapePasEncorePassee("Clôture", true, "inconnue"), false);
});

test("impôts non déclarés", () => {
  assert.equal(impotsNonDeclares("Sans exercice", false), false);
  assert.equal(impotsNonDeclares("Compte", false), true);
  assert.equal(impotsNonDeclares("Greffe", true), true);
  assert.equal(impotsNonDeclares("Impôts", true), false);
});

test("étape bloquante", () => {
  assert.equal(etapeBloquante("Sans exercice", false), "Sans exercice");
  assert.equal(etapeBloquante("Compte", false), "Compte");
  assert.equal(etapeBloquante("Compte", true), "Clôture");
  assert.equal(etapeBloquante("Signature légale", true), "À jour");
});
