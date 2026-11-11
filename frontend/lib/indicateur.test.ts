import assert from "node:assert/strict";
import test from "node:test";

import {
  DUREE_GLISSEMENT_MS,
  dureeGlissement,
  positionIndicateur,
  positionIndicateurVertical,
} from "./indicateur";

test("la position verticale est relative au conteneur, au demi-pixel", () => {
  assert.deepEqual(positionIndicateurVertical({ top: 80 }, { top: 130.26, height: 39.8 }), { y: 50.5, hauteur: 40 });
});

test("la position est relative au conteneur", () => {
  assert.deepEqual(positionIndicateur({ left: 100 }, { left: 260, width: 88 }), { x: 160, largeur: 88 });
});

test("la position est arrondie au demi-pixel", () => {
  assert.deepEqual(positionIndicateur({ left: 0 }, { left: 10.26, width: 87.8 }), { x: 10.5, largeur: 88 });
});

test("aucun glissement au premier placement", () => {
  assert.equal(dureeGlissement(true, false), 0);
});

test("aucun glissement si l'utilisateur réduit les animations", () => {
  assert.equal(dureeGlissement(false, true), 0);
});

test("sinon l'indicateur glisse pendant la durée du design", () => {
  assert.equal(dureeGlissement(false, false), DUREE_GLISSEMENT_MS);
});
