import assert from "node:assert/strict";
import test from "node:test";

import { intituleProposition, libelleCategorie, questionSelonSigne } from "./langage-chauffeur";

test("l'origine de la proposition se dit sans parler du modèle", () => {
  assert.equal(intituleProposition("Carburant", "regle"), "Proposition : Carburant");
  assert.equal(intituleProposition("Carburant", "modele"), "Proposition : Carburant");
  assert.equal(intituleProposition("Carburant", "ia"), "Proposition de l'IA : Carburant");
  assert.equal(
    intituleProposition("Carburant", "appris"),
    "Comme une opération déjà classée : Carburant",
  );
  assert.equal(intituleProposition("Parking", "banque"), "D'après votre banque : Parking");
});

test("un virement interne a un libellé lisible, un code inconnu un défaut neutre", () => {
  assert.equal(libelleCategorie("virement_interne"), "Virement entre mes comptes");
  assert.equal(libelleCategorie("code_inconnu_xyz"), "À classer");
});

test("la question suit le sens de l'opération", () => {
  assert.equal(questionSelonSigne(-100, false), "À quoi correspond cette dépense ?");
  assert.equal(questionSelonSigne(100, false), "À quoi correspond cette entrée ?");
  assert.match(questionSelonSigne(0, true), /^Pas de proposition automatique\./);
});
