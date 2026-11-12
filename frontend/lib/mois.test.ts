import assert from "node:assert/strict";
import test from "node:test";

import { libelleMois } from "./mois";

test("un mois de bulletin se lit en toutes lettres", () => {
  assert.equal(libelleMois("2026-01"), "janvier 2026");
  assert.equal(libelleMois("2025-12"), "décembre 2025");
});

test("une valeur illisible reste telle quelle", () => {
  assert.equal(libelleMois("2026-13"), "2026-13");
  assert.equal(libelleMois(""), "");
});
