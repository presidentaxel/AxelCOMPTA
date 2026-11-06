import assert from "node:assert/strict";
import test from "node:test";

import { phraseResolution, resteATraiter, trierQuarantaine } from "./quarantaine";
import type { EntreeQuarantaine } from "./types";

const base: EntreeQuarantaine = {
  id: "q",
  motif: "modifiee_apres_comptabilisation",
  libelle_motif: "Montant changé",
  date: "2026-03-01",
  libelle: "CB TOTAL",
  montant_cts: -7500,
  resoluble: true,
  decision: null,
  resolue_par: null,
  resolue_le: null,
};

test("les entrées à traiter passent devant", () => {
  const traitee = { ...base, id: "a", decision: "ignorer" as const, resolue_le: "2026-03-05" };
  const ouverte = { ...base, id: "b" };
  assert.deepEqual(trierQuarantaine([traitee, ouverte]).map((e) => e.id), ["b", "a"]);
  assert.equal(resteATraiter([traitee, ouverte]), 1);
});

test("phrase de résolution", () => {
  assert.equal(phraseResolution(base, (d) => d), null);
  const acceptee = { ...base, decision: "accepter" as const, resolue_par: "louis@x.fr", resolue_le: "2026-03-05" };
  assert.equal(phraseResolution(acceptee, (d) => d), "Acceptée par louis@x.fr le 2026-03-05");
});
