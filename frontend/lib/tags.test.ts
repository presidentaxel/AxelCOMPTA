import assert from "node:assert/strict";
import test from "node:test";

import {
  basculerExclusion,
  gardeTag,
  ecrireFiltreTag,
  libelleTag,
  lireFiltreTag,
  SANS_TAG,
  TOUS_LES_TAGS,
  tagsPresents,
  totauxPortefeuille,
} from "./tags";

test("libellé des tags proposés et des tags créés", () => {
  assert.equal(libelleTag("societe_du_gestionnaire"), "Société du gestionnaire");
  assert.equal(libelleTag("flotte_nord"), "flotte nord");
});

test("filtre par tag", () => {
  const chauffeur = { tags: ["chauffeur"] };
  const sans = { tags: [] };
  assert.equal(gardeTag(chauffeur, TOUS_LES_TAGS), true);
  assert.equal(gardeTag(chauffeur, "chauffeur"), true);
  assert.equal(gardeTag(chauffeur, "test"), false);
  assert.equal(gardeTag(sans, SANS_TAG), true);
  assert.equal(gardeTag(chauffeur, SANS_TAG), false);
});

test("un dossier exclu des compteurs n'entre pas dans les totaux", () => {
  const totaux = totauxPortefeuille([
    { exclu_compteurs: false, statut_invitation: null, resultat_cts: 1_000 },
    { exclu_compteurs: false, statut_invitation: "actif", resultat_cts: -300 },
    { exclu_compteurs: true, statut_invitation: null, resultat_cts: 99_999 },
  ]);
  assert.deepEqual(totaux, { nombre: 2, sansCompte: 1, resultat: 700 });
});

test("basculer une exclusion", () => {
  assert.deepEqual(basculerExclusion(["test"], "hors_perimetre"), ["hors_perimetre", "test"]);
  assert.deepEqual(basculerExclusion(["hors_perimetre", "test"], "test"), ["hors_perimetre"]);
});

test("tags présents dans la file", () => {
  assert.deepEqual(tagsPresents({ a: ["test", "chauffeur"], b: ["chauffeur"] }), ["chauffeur", "test"]);
  assert.deepEqual(tagsPresents({}), []);
});

test("filtre de tag dans l'URL", () => {
  assert.equal(lireFiltreTag(""), TOUS_LES_TAGS);
  assert.equal(lireFiltreTag("?tag=chauffeur&x=1"), "chauffeur");
  assert.equal(ecrireFiltreTag("/expert", "?x=1", "chauffeur"), "/expert?x=1&tag=chauffeur");
  assert.equal(ecrireFiltreTag("/expert", "?tag=chauffeur", TOUS_LES_TAGS), "/expert");
});
