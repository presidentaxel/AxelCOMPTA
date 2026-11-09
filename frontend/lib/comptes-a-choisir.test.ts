import assert from "node:assert/strict";
import test from "node:test";

import {
  attendUnChoixDeCompte,
  bandeauComptesAChoisir,
  phraseComptesAChoisir,
} from "./comptes-a-choisir";

test("aucun compte à choisir : rien à dire", () => {
  assert.equal(phraseComptesAChoisir({}), null);
  assert.equal(phraseComptesAChoisir({ comptes_a_choisir: 0 }), null);
  assert.equal(bandeauComptesAChoisir([{}, { comptes_a_choisir: 0 }]), null);
  assert.equal(attendUnChoixDeCompte({}), false);
});

test("la ligne donne le nombre, la date et les opérations retenues", () => {
  assert.equal(
    phraseComptesAChoisir({
      comptes_a_choisir: 2,
      comptes_a_choisir_depuis: "2026-11-09",
      operations_en_attente_de_choix: 34,
    }),
    "2 comptes bancaires attendent le choix du dirigeant depuis le 09/11/2026 : " +
      "34 opérations n'entrent pas en comptabilité.",
  );
  assert.equal(
    phraseComptesAChoisir({ comptes_a_choisir: 1, operations_en_attente_de_choix: 1 }),
    "Un compte bancaire attend le choix du dirigeant : 1 opération n'entre pas en comptabilité.",
  );
});

test("le bandeau compte les entreprises, pas les comptes", () => {
  const bandeau = bandeauComptesAChoisir([
    { comptes_a_choisir: 3 },
    { comptes_a_choisir: 1 },
    { comptes_a_choisir: 0 },
  ]);
  assert.ok(bandeau?.startsWith("2 entreprises ont un compte bancaire"));
});
