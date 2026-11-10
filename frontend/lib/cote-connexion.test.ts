import assert from "node:assert/strict";
import test from "node:test";

import { coteDemandee, coteOuverte } from "./cote-connexion";

const CHAUFFEUR = { dossier_id: "DIGI_1" };
const GESTIONNAIRE = { tenant_id: "TENANT_DEMO" };
const TEST = { role_test: "lecteur_tous_dossiers", tenant_id: "TENANT_DEMO" };
const MONO = { dossier_id: "DIGI_1", tenant_id: "TENANT_DEMO" };

test("le côté demandé est lu dans l'adresse du lien", () => {
  assert.equal(coteDemandee("?cote=chauffeur"), "chauffeur");
  assert.equal(coteDemandee("cote=gestionnaire"), "gestionnaire");
  assert.equal(coteDemandee("?retour=/portefeuille"), null);
});

test("un chauffeur sans portefeuille n'ouvre pas le gestionnaire", () => {
  assert.equal(coteOuverte(CHAUFFEUR, "gestionnaire"), "interdit");
  assert.equal(coteOuverte(CHAUFFEUR, "chauffeur"), "chauffeur");
});

test("le compte de test ouvre le côté d'où part la demande", () => {
  assert.equal(coteOuverte(TEST, "gestionnaire"), "gestionnaire");
  assert.equal(coteOuverte(TEST, "chauffeur"), "chauffeur");
  assert.equal(coteOuverte(TEST, null), "chauffeur");
  assert.equal(coteOuverte({ role_test: "lecteur_tous_dossiers" }, "gestionnaire"), "interdit");
});

test("un gestionnaire n'ouvre pas l'espace chauffeur", () => {
  assert.equal(coteOuverte(GESTIONNAIRE, "chauffeur"), "interdit");
  assert.equal(coteOuverte(GESTIONNAIRE, "gestionnaire"), "gestionnaire");
  assert.equal(coteOuverte(GESTIONNAIRE, null), "gestionnaire");
});

test("un compte aux deux liens n'ouvre que le côté du formulaire", () => {
  assert.equal(coteOuverte(MONO, "chauffeur"), "chauffeur");
  assert.equal(coteOuverte(MONO, "gestionnaire"), "gestionnaire");
  assert.equal(coteOuverte({}, null), "sans_lien");
});
