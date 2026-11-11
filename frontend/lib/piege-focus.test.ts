import assert from "node:assert/strict";
import test from "node:test";

import { indexFocusPiege } from "./piege-focus";

test("Tab sur le dernier élément reboucle sur le premier", () => {
  assert.equal(indexFocusPiege(3, 2, false), 0);
});

test("Maj+Tab sur le premier élément reboucle sur le dernier", () => {
  assert.equal(indexFocusPiege(3, 0, true), 2);
});

test("au milieu de la fenêtre, le navigateur suit son ordre", () => {
  assert.equal(indexFocusPiege(3, 1, false), null);
  assert.equal(indexFocusPiege(3, 1, true), null);
  assert.equal(indexFocusPiege(3, 0, false), null);
  assert.equal(indexFocusPiege(3, 2, true), null);
});

test("focus hors de la liste (la fenêtre elle-même) : on entre par le bon bout", () => {
  assert.equal(indexFocusPiege(3, -1, false), 0);
  assert.equal(indexFocusPiege(3, -1, true), 2);
});

test("un seul élément : le focus y reste", () => {
  assert.equal(indexFocusPiege(1, 0, false), 0);
  assert.equal(indexFocusPiege(1, 0, true), 0);
});

test("aucun élément focalisable : rien à forcer", () => {
  assert.equal(indexFocusPiege(0, -1, false), null);
});
