import assert from "node:assert/strict";
import test from "node:test";

import { avecDossierDeTest, cheminDuDossier, liensDuJeton } from "./compte-de-test";

test("le jeton dit chauffeur, compte de test, ou rien", () => {
  assert.deepEqual(liensDuJeton({ dossier_id: "DIGI_1" }), { dossierId: "DIGI_1", lecteurTest: false });
  assert.deepEqual(liensDuJeton({ role_test: "lecteur_tous_dossiers", tenant_id: "T" }), {
    dossierId: "",
    lecteurTest: true,
  });
  assert.equal(liensDuJeton({ tenant_id: "T" }), null);
  assert.equal(liensDuJeton(undefined), null);
});

test("le compte de test choisit son dossier avant d'entrer", () => {
  assert.equal(cheminDuDossier({ dossierId: "", lecteurTest: true }), "/chauffeur/test");
  assert.equal(cheminDuDossier({ dossierId: "DIGI_1", lecteurTest: true }), "/chauffeur/DIGI_1");
  assert.equal(cheminDuDossier({ dossierId: "DIGI_2" }), "/chauffeur/DIGI_2");
});

test("X-Dossier n'est envoyé que par le compte de test", () => {
  const chauffeur = avecDossierDeTest({}, { dossierId: "DIGI_1", lecteurTest: false });
  assert.equal(new Headers(chauffeur.headers).get("X-Dossier"), null);
  const lecteur = avecDossierDeTest(
    { headers: { Accept: "application/json" } },
    { dossierId: "DIGI_1", lecteurTest: true },
  );
  const entetes = new Headers(lecteur.headers);
  assert.equal(entetes.get("X-Dossier"), "DIGI_1");
  assert.equal(entetes.get("Accept"), "application/json");
  assert.equal(avecDossierDeTest({}, null).headers, undefined);
});
