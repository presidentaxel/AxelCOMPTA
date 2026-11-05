import assert from "node:assert/strict";
import test from "node:test";

import { phraseAConfirmer } from "./configuration-dossier";

test("rien à confirmer, rien à dire", () => {
  assert.equal(phraseAConfirmer([]), null);
  assert.equal(phraseAConfirmer(["code_inconnu"]), null);
});

test("un ou deux éléments à confirmer", () => {
  assert.equal(
    phraseAConfirmer(["forme_juridique"]),
    "Forme juridique à confirmer par le dirigeant.",
  );
  assert.equal(
    phraseAConfirmer(["exercice", "forme_juridique"]),
    "Premier exercice et forme juridique à confirmer par le dirigeant.",
  );
});
